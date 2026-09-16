"""
    uv sync --group e2e
    DEBUG=false docker compose up -d --wait
    uv run pytest -m e2e --no-cov
"""

from __future__ import annotations

import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from importlib.util import find_spec

import httpx
import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from news.models import Article, Source, User

from ..conftest import DEFAULT_PASSWORD

# Selenium lives in the `e2e` dependency group, so a plain `uv sync` does not
# have it. `-m "not e2e"` deselects these tests, but deselection happens after
# collection -- and collection imports test_liked_flow.py, which imports
# selenium at module level. Without this guard `uv run pytest` in a default
# install dies with a collection error instead of running the other suite.
collect_ignore_glob: list[str] = []
if find_spec("selenium") is None:
    collect_ignore_glob.append("test_*.py")

# --- configuration ---------------------------------------------------------
#
# Defaults describe the compose stack; each is overridable, so the same suite
# can be pointed at a deployment:
#
#   E2E_BASE_URL=https://staging.example uv run pytest -m e2e --no-cov

BASE_URL = os.environ.get("E2E_BASE_URL", "http://localhost:8011").rstrip("/")
MAILPIT_URL = os.environ.get("E2E_MAILPIT_URL", "http://localhost:8211").rstrip("/")

# Read directly rather than through news.settings: ../conftest.py has already
# overwritten half the environment Settings() reads, and the database here is
# the container's.
DATABASE_URL = os.environ.get(
    "E2E_DATABASE_URL",
    "postgresql+psycopg://{user}:{password}@{host}:{port}/{name}".format(
        user=os.environ.get("DB_USER", "admin"),
        password=os.environ.get("DB_PASSWORD", "admin"),
        host=os.environ.get("DB_HOST", "localhost"),
        port=os.environ.get("DB_PORT", "5411"),
        name=os.environ.get("DB_NAME", "cnn"),
    ),
)

# Seconds to pause after each thing a person would have done. 0 is full speed,
# which is about eight seconds for the whole flow -- too fast to read.
#
#   E2E_SLOWMO=1 uv run pytest -m e2e --no-cov -k browser_flow
SLOWMO_SECONDS = float(os.environ.get("E2E_SLOWMO", "0"))

# Slow motion implies a visible window; an explicit E2E_HEADLESS still wins.
HEADLESS = os.environ.get("E2E_HEADLESS", "0" if SLOWMO_SECONDS else "1") != "0"

# Generous: a cold container is slower than a warm one, and a too-short timeout
# buys a flaky suite nobody trusts.
TIMEOUT_SECONDS = float(os.environ.get("E2E_TIMEOUT", "20"))

# The unit suite's password, reused so the session-scoped `password_hash`
# fixture next door hashes the string this one types into the login form.
PASSWORD = DEFAULT_PASSWORD

# Quoted in each skip message below, so the fix is in the failure. The prefix
# goes on `docker compose`, never on `uv run pytest` -- these are the api
# container's settings, read at import time in another process. And it must be
# `up -d`: Compose bakes the environment in at create time, so a restarted
# container keeps whatever it booted with.
E2E_MODE = "DEBUG=false docker compose up -d api --wait  (`up -d`, not `restart`)"


# --- preconditions ---------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def live_stack() -> str:
    """The app is up, and configured in a way a browser can actually drive.

    Two development settings stop the front-end working, and both fail
    silently, which is why they are checked here rather than left to show up as
    a mystifying red:

    * The rate limiter allows one /api request per window per IP, and /liked
      asks for /api/auth/me and /api/me/liked from one DOMContentLoaded
      handler. The second gets a 429, auth.js swallows a failed fetch by
      design, and the page renders empty.
    * The debug toolbar wraps every request in a pyinstrument sampling
      profiler. Fifteen requests in a few seconds pile up sessions of a
      quarter-million samples and the worker stops answering mid-request -- a
      register that returns 201 and then never sends its email.
    """
    try:
        health = httpx.get(f"{BASE_URL}/healthz", timeout=5)
    except httpx.HTTPError as exc:
        pytest.skip(f"no app at {BASE_URL} ({exc}) -- `docker compose up -d --wait`")

    if health.status_code != 200 or health.json().get("db") != "ok":
        pytest.skip(f"{BASE_URL}/healthz says {health.text} -- is Postgres up?")

    try:
        httpx.get(f"{MAILPIT_URL}/api/v1/messages?limit=1", timeout=5).raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"no Mailpit at {MAILPIT_URL} ({exc}) -- `docker compose up -d mailpit`")

    # Both 401 (no token) if the limiter is off; the second is 429 if it is on
    # -- the limiter runs ahead of the router, so this probe costs nothing.
    probe = [httpx.get(f"{BASE_URL}/api/auth/me", timeout=5).status_code for _ in range(2)]
    if 429 in probe:
        pytest.skip(f"the /api rate limiter is on and the front-end cannot work with it: {E2E_MODE}")

    # Asking the app, because DEBUG is the container's setting and a local .env
    # may not be what it booted with.
    page = httpx.get(f"{BASE_URL}/login", timeout=30)
    if "_debug_toolbar" in page.text:
        pytest.skip(f"the debug toolbar is on and will stall the app mid-run: {E2E_MODE}")

    return BASE_URL


# --- the database ----------------------------------------------------------


@pytest.fixture(scope="session")
def engine():
    """A synchronous engine onto the container's Postgres.

    Sync because the Selenium API is blocking, so these tests are plain `def`.
    It is a seam the unit suite does not have, and some setup is far cheaper
    through it than over HTTP: the real path to an article is a page load that
    spends one of NewsAPI's hundred daily requests.
    """
    engine = create_engine(DATABASE_URL, future=True)
    try:
        with engine.connect():
            pass
    except Exception as exc:  # pragma: no cover - a skip, not a behaviour
        pytest.skip(f"cannot reach Postgres at {DATABASE_URL.rsplit('@', 1)[-1]}: {exc}")

    yield engine
    engine.dispose()


@pytest.fixture
def db(engine) -> Session:
    """A short session for setup and teardown, committed -- unlike the unit
    suite, the app is in another process and can only see committed rows."""
    with Session(engine) as session:
        yield session


@pytest.fixture
def run_id() -> str:
    """Eight hex characters carried by every row this suite creates.

    The database is real, shared and persistent: a fixed address would collide
    with the last run on UNIQUE, and rows a killed run left behind are
    identifiable rather than anonymous.
    """
    return uuid.uuid4().hex[:8]


@pytest.fixture
def new_user(db, run_id) -> dict[str, str]:
    """Credentials for an account that does not exist yet -- the test registers
    it through the browser, which is the step under test."""
    user = {
        # `.example` is RFC 2606's documentation TLD; email-validator refuses
        # the reserved `.test` and `.local`, so the obvious choice would 422.
        "email": f"e2e-{run_id}@readers.example",
        "username": f"e2e_{run_id}",
        "password": PASSWORD,
    }

    yield user

    # Runs on failure too, so a bad run cannot make the next one fail on
    # UNIQUE(email). Likes go with it: liked_articles.user_id is ON DELETE
    # CASCADE, which Postgres enforces without SQLite's PRAGMA.
    db.execute(delete(User).where(User.email == user["email"]))
    db.commit()


@pytest.fixture
def articles(db, run_id) -> list[Article]:
    """Three stories, inserted rather than fetched: leaning on `GET /` would
    cost NewsAPI quota, need the network, and assert against hourly headlines."""
    source = Source(slug=f"e2e-{run_id}", name="E2E Wire")
    db.add(source)
    db.flush()

    made = [
        Article(
            source_id=source.id,
            url=f"https://news.example/e2e-{run_id}/story-{n}",
            title=f"E2E story {n} ({run_id})",
            description=f"What happened in end-to-end story {n}.",
            content=f"The full text of end-to-end story {n}.",
            image_url=None,
            author="A. Reporter",
            # An hour apart, descending, so the order is defined rather than
            # merely likely.
            published_at=datetime.now(timezone.utc) - timedelta(hours=n),
        )
        for n in range(1, 4)
    ]
    db.add_all(made)
    db.commit()
    for article in made:
        db.refresh(article)

    yield made

    # Articles first: likes cascade from them, and articles.source_id would
    # block the source's delete.
    db.execute(delete(Article).where(Article.id.in_([a.id for a in made])))
    db.execute(delete(Source).where(Source.id == source.id))
    db.commit()


@pytest.fixture
def make_confirmed_user(db, run_id, password_hash):
    """Users created straight in the database, past the email step -- for tests
    about something after registration, which should not pay for it three times.

    `password_hash` is ../conftest.py's session-scoped fixture, so bcrypt runs
    once for the whole run rather than once per user.
    """
    created: list[int] = []

    def make(label: str) -> User:
        user = User(
            username=f"e2e_{label}_{run_id}",
            email=f"e2e-{label}-{run_id}@readers.example",
            hashed_password=password_hash,
            confirmed=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        created.append(user.id)
        return user

    yield make

    db.execute(delete(User).where(User.id.in_(created)))
    db.commit()


# --- mailpit ---------------------------------------------------------------


VERIFY_LINK = re.compile(r'href="([^"]*/verify-email\?token=[^"]+)"')


def verification_link(email: str, timeout: float = TIMEOUT_SECONDS) -> str:
    """The confirmation URL out of the message Mailpit actually received.

    Not a token minted here: that would hand the test a link that works and
    prove nothing. Polling, because the send is a BackgroundTask and
    POST /register returns before the SMTP conversation has happened.
    """
    deadline = time.monotonic() + timeout
    last_seen = 0

    while time.monotonic() < deadline:
        found = httpx.get(
            f"{MAILPIT_URL}/api/v1/search",
            params={"query": f"to:{email}"},
            timeout=10,
        ).json()
        last_seen = found.get("messages_count", 0)

        if found.get("messages"):
            message_id = found["messages"][0]["ID"]
            body = httpx.get(f"{MAILPIT_URL}/api/v1/message/{message_id}", timeout=10).json()
            match = VERIFY_LINK.search(body.get("HTML") or "")
            if match:
                return match.group(1)
            raise AssertionError(
                f"the mail to {email} has no verification link:\n{body.get('HTML')!r}"
            )

        time.sleep(0.25)

    raise AssertionError(
        f"no verification email for {email} within {timeout}s "
        f"({last_seen} messages in the inbox) -- check `docker compose logs api`"
    )


# --- the browser -----------------------------------------------------------


def install_slowmo(monkeypatch, driver, seconds: float) -> None:
    """Pause after every navigation, click and keystroke.

    Selenium has no slow-motion option of its own. Only the calls that make
    something visibly happen are wrapped: a WebDriverWait polls find_element
    several times a second, and pacing those would put the delay into waiting
    rather than doing.

    monkeypatch, not a plain setattr: click and send_keys live on the
    WebElement *class*, and a patch left there would slow every later test.
    """
    from selenium.webdriver.remote.webelement import WebElement

    def paced(original):
        def wrapper(*args, **kwargs):
            result = original(*args, **kwargs)
            # After, not before: the pause leaves the result on screen.
            time.sleep(seconds)
            return result

        return wrapper

    def slow_get(url, _original=driver.get):
        _original(url)
        # Double, since a navigation changes the whole screen.
        time.sleep(seconds * 2)

    monkeypatch.setattr(driver, "get", slow_get)
    for name in ("click", "send_keys", "clear"):
        monkeypatch.setattr(WebElement, name, paced(getattr(WebElement, name)))


@pytest.fixture
def driver(monkeypatch):
    """One Chrome per test, with nothing carried over from the last.

    Per test because this app's whole session is a bearer token in
    localStorage: a shared browser would carry one test's login into the next,
    and "/liked shows my articles" would pass for a user nobody logged in as.

    No explicit chromedriver -- Selenium Manager downloads one matching the
    installed Chrome on first use.
    """
    # Imported here so that collecting this file without the e2e group is a
    # skip with an instruction, not an ImportError that takes the run down.
    try:
        from selenium import webdriver
    except ImportError:  # pragma: no cover - a skip, not a behaviour
        pytest.skip("selenium is not installed -- `uv sync --group e2e`")

    options = webdriver.ChromeOptions()
    if HEADLESS:
        # The "new" mode: the real browser rendering off-screen, rather than
        # the old separate implementation that differed from headed Chrome.
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    # Chrome's own noise, not the app's -- a first-run prompt can steal a click.
    options.add_argument("--disable-search-engine-choice-screen")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option(
        "prefs", {"credentials_enable_service": False, "profile.password_manager_enabled": False}
    )

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:  # pragma: no cover - a skip, not a behaviour
        pytest.skip(f"could not start Chrome ({exc}) -- is Google Chrome installed?")

    driver.set_page_load_timeout(TIMEOUT_SECONDS)
    if SLOWMO_SECONDS:
        install_slowmo(monkeypatch, driver, SLOWMO_SECONDS)

    yield driver
    driver.quit()
