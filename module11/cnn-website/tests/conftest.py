"""Fixtures for the whole suite: environment, database, fakes, client, factories."""

from __future__ import annotations

# Set before the `from news import ...` lines below, not in a fixture:
# news/settings.py builds a strict Settings() at import time, and real
# environment variables outrank .env -- so this also detaches the suite from
# whatever the developer happens to have in theirs.
import os

os.environ["NEWS_API_KEY"] = "test-news-api-key"
os.environ["SECRET_KEY"] = "test-secret-key-not-used-anywhere-real"
# 0 disables the rate limiter. Without it the second /api call in any test
# gets a 429 -- the whole suite arrives from one fake IP.
os.environ["RATE_LIMIT_WINDOW_SECONDS"] = "0"
os.environ["DEBUG"] = "false"

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from itertools import count
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from news import mail
from news.db import get_db
from news.main import app
from news.models import Article, Base, LikedArticle, Role, Source, User
from news.security import AuthService, auth_service
from news.settings import settings

DEFAULT_PASSWORD = "correct horse battery staple"


# --- the database ----------------------------------------------------------


@pytest.fixture
async def engine():
    """A fresh, empty SQLite database per test.

    StaticPool because ":memory:" is scoped to a connection, and the default
    pool would hand every query its own empty database. The cost of SQLite is
    that Postgres-only behaviour -- the user_role ENUM, real ON DELETE CASCADE,
    ILIKE collation -- is approximated here; see tests/e2e/ for the real thing.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def session(engine) -> AsyncSession:
    """The one session both the test and the app under test share, so a factory
    can write a row and the next request read it without committing."""
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session


# --- the fakes -------------------------------------------------------------


class FakeRedis:
    """A dict answering the four commands this app sends.

    A fake rather than a mock: the app degrades a cache failure to a miss, so a
    mock returning None would make every cache test pass for the wrong reason.
    Does not expire -- `ex=` is accepted and ignored.
    """

    def __init__(self) -> None:
        self.store: dict[str, Any] = {}

    async def get(self, key: str) -> Any:
        return self.store.get(key)

    async def set(self, key: str, value: Any, ex: int | None = None, nx: bool = False):
        if nx and key in self.store:
            return None  # what redis-py returns when SET NX declines
        self.store[key] = value
        return True

    async def delete(self, key: str) -> int:
        return int(self.store.pop(key, None) is not None)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch) -> FakeRedis:
    """Autouse because forgetting it is invisible: the real client would fail to
    reach localhost:6311 and news/cache.py would call that a miss."""
    fake = FakeRedis()
    monkeypatch.setattr("news.cache.redis_client", fake)
    return fake


@dataclass
class SentEmail:
    """One message the app tried to send, caught before it reached SMTP."""

    message: Any  # fastapi_mail.MessageSchema
    template_name: str

    @property
    def recipients(self) -> list[str]:
        """Flattened: fastapi-mail normalises these into pydantic NameEmail
        objects, which compare unequal to the plain strings a test writes."""
        return [getattr(to, "email", to) for to in self.message.recipients]

    @property
    def body(self) -> dict:
        """The template context -- where the verification token is."""
        return self.message.template_body


@pytest.fixture(autouse=True)
def outbox(monkeypatch) -> list[SentEmail]:
    """Every email the app sends during a test, in order.

    Patched as low as it goes before the socket, so the token in the message is
    a real one. Autouse because mailpit really is listening on :1011 when the
    stack is up -- an unpatched test would succeed at sending mail.
    """
    sent: list[SentEmail] = []

    async def capture(message, template_name: str = "") -> None:
        sent.append(SentEmail(message=message, template_name=template_name))

    monkeypatch.setattr(mail.mailer, "send_message", capture)
    return sent


# --- the HTTP client -------------------------------------------------------


@pytest.fixture
async def client(session) -> AsyncClient:
    """An httpx client wired into the ASGI app in-process -- no server, no port.

    The override is keyed on the `get_db` function object, so it covers
    news/security.py's own Depends(get_db) as well as the routes'.
    """

    async def override_get_db():
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    # `app` is a module-level singleton; an override left on it leaks.
    app.dependency_overrides.clear()


# --- factories -------------------------------------------------------------
#
# One call, one valid row, every field you did not care about filled in -- so a
# test names only what it is actually about: `await users.create(role=ADMIN)`.


class UserFactory:
    """Makes users. Confirmed and non-admin unless told otherwise."""

    def __init__(self, session: AsyncSession, password_hash: str) -> None:
        self.session = session
        self.password_hash = password_hash
        # A counter, not random data: "expected reader1, got reader2" says
        # something; two UUIDs do not.
        self._seq = count(1)

    async def create(self, **overrides) -> User:
        """One user, flushed so it has an id. Not committed."""
        n = next(self._seq)
        fields = {
            "username": f"reader{n}",
            # `.example` and not `.test`: UserCreate types this as EmailStr,
            # and email-validator refuses reserved TLDs.
            "email": f"reader{n}@readers.example",
            "hashed_password": self.password_hash,
            # Confirmed by default: an unconfirmed user cannot log in, so the
            # opposite would put a confirmed=True in almost every test.
            "confirmed": True,
            "subscribed": False,
            "role": Role.USER,
        }
        # `|` lets a caller override back to a falsy value, which setdefault
        # would not.
        user = User(**(fields | overrides))

        self.session.add(user)
        await self.session.flush()
        return user


class ArticleFactory:
    """Makes articles, and the sources they belong to."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._seq = count(1)

    async def source(self, slug: str = "cnn", name: str | None = None) -> Source:
        """Get-or-create, because `slug` is UNIQUE and articles share sources."""
        source = await self.session.scalar(select(Source).where(Source.slug == slug))
        if source is None:
            source = Source(slug=slug, name=name or slug.upper())
            self.session.add(source)
            await self.session.flush()
        return source

    async def create(self, *, source_slug: str = "cnn", **overrides) -> Article:
        """One article, flushed so it has an id."""
        n = next(self._seq)
        source = await self.source(source_slug)
        fields = {
            "source_id": source.id,
            "url": f"https://news.example/story-{n}",
            "title": f"Story number {n}",
            "description": f"What happened in story {n}.",
            "content": f"The full text of story {n}.",
            "image_url": None,
            "author": "A. Reporter",
            # An hour apart, so tests about ordering have a defined order
            # rather than a likely one.
            "published_at": datetime(2026, 1, 1, tzinfo=timezone.utc) - timedelta(hours=n),
        }
        article = Article(**(fields | overrides))

        self.session.add(article)
        await self.session.flush()
        return article

    async def create_many(self, n: int, **overrides) -> list[Article]:
        """`n` articles, newest first -- the order the API returns them in."""
        made = [await self.create(**overrides) for _ in range(n)]
        return sorted(made, key=lambda a: a.published_at, reverse=True)

    async def like(self, user: User, article: Article) -> LikedArticle:
        """Pre-existing like, for the tests that start from one."""
        like = LikedArticle(user_id=user.id, article_id=article.id)
        self.session.add(like)
        await self.session.flush()
        return like



@pytest.fixture(scope="session")
def password_hash() -> str:
    """The bcrypt hash of DEFAULT_PASSWORD, computed once for the whole run --
    a hash is roughly a quarter-second, and no test asserts on it.

    A plain `def`: the bcrypt call under the async wrapper is synchronous, so
    this needs no event loop at session scope.
    """
    return AuthService.pwd_context.hash(DEFAULT_PASSWORD)


@pytest.fixture
def users(session, password_hash) -> UserFactory:
    return UserFactory(session, password_hash)


@pytest.fixture
def articles(session) -> ArticleFactory:
    return ArticleFactory(session)


@pytest.fixture
async def reader(users) -> User:
    """A confirmed, ordinary user. The default protagonist."""
    return await users.create()


@pytest.fixture
async def admin(users) -> User:
    return await users.create(username="editor", email="editor@readers.example", role=Role.ADMIN)


@pytest.fixture
async def auth_headers(reader) -> dict[str, str]:
    token = await auth_service.create_access_token(reader.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def admin_headers(admin) -> dict[str, str]:
    token = await auth_service.create_access_token(admin.email)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def rate_limiter_on(monkeypatch):
    """Undo the environment block above, for the one test that is about the
    limiter -- so the switch is visible in the test that depends on it."""
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 1)
