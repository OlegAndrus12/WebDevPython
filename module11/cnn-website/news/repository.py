from __future__ import annotations

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from . import cache
from .models import Article, LikedArticle, Role, Source, User
from .utils import like_escape, parse_published, slugify


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_articles(self, payloads: list[dict]) -> list[Article]:
        """Upsert a whole NewsAPI response, in the order given."""
        articles = []
        for payload in payloads:
            if not payload.get("url"):
                continue
            source = await self.save_source(payload.get("source") or {})
            articles.append(await self.save_article(payload, source))
        return articles

    async def get_article_by_id(self, article_id: int) -> Article | None:
        """One article with its source, or None for the 404."""
        return await self.session.scalar(
            select(Article)
            .where(Article.id == article_id)
            .options(joinedload(Article.source))
        )

    async def list_articles(
        self, query: str | None = None, limit: int = 20, offset: int = 0
    ) -> tuple[list[Article], int]:
        """One page of stored articles, newest first, plus the total that match."""
        where = []
        if query:
            pattern = f"%{like_escape(query)}%"
            where.append(
                or_(
                    Article.title.ilike(pattern, escape="\\"),
                    Article.description.ilike(pattern, escape="\\"),
                )
            )

        total = await self.session.scalar(
            select(func.count()).select_from(Article).where(*where)
        )

        result = await self.session.scalars(
            select(Article)
            .where(*where)
            .options(joinedload(Article.source))
            .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
            .limit(limit)
            .offset(offset)
        )

        return list(result.all()), total or 0

    async def article_counts_by_source(self) -> list[tuple[str, str, int]]:
        result = await self.session.execute(
            select(Source.slug, Source.name, func.count(Article.id))
            .outerjoin(Source.articles)
            .group_by(Source.id)
            .order_by(func.count(Article.id).desc(), Source.name)
        )
        return [(slug, name, count) for slug, name, count in result.all()]

    async def ping(self) -> bool:
        return (await self.session.scalar(select(text("1")))) == 1

    async def save_source(self, payload: dict) -> Source:
        """Find or create the source named in an article's `source` object."""
        slug = payload.get("id") or slugify(payload.get("name") or "unknown")
        source = await self.session.scalar(select(Source).where(Source.slug == slug))
        if source is None:
            source = Source(slug=slug, name=payload.get("name") or slug)
            self.session.add(source)
            await self.session.flush()
        return source

    async def save_article(self, payload: dict, source: Source) -> Article:
        """Find or create by `url`, so a story seen twice stays one row."""
        article = await self.session.scalar(
            select(Article).where(Article.url == payload["url"])
        )
        if article is None:
            article = Article(url=payload["url"])
            self.session.add(article)

        article.source = source
        article.title = payload.get("title") or "(untitled)"
        article.description = payload.get("description")
        article.content = payload.get("content")
        article.image_url = payload.get("urlToImage")
        article.author = payload.get("author")
        article.published_at = parse_published(payload.get("publishedAt"))

        is_new = article in self.session.new
        changed = not is_new and self.session.is_modified(
            article, include_collections=False
        )

        await self.session.flush()

        if changed:
            await cache.invalidate_article(article.id)
        return article


    async def get_user_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def get_user_by_username(self, username: str) -> User | None:
        return await self.session.scalar(select(User).where(User.username == username))

    async def create_user(self, *, username: str, email: str, hashed_password: str) -> User:
        user = User(username=username, email=email, hashed_password=hashed_password)
        self.session.add(user)
        await self.session.flush()
        return user

    async def confirm_email(self, email: str) -> User | None:
        """Mark an address verified. Returns None if there is no such user."""
        user = await self.get_user_by_email(email)
        if user is not None:
            user.confirmed = True
            await self.session.flush()
        return user


    async def like_article(self, user_id: int, article_id: int) -> None:
        """Idempotent: liking an already-liked article is a no-op, not a conflict."""
        already_liked = await self.is_liked(user_id, article_id)
        if not already_liked:
            self.session.add(LikedArticle(user_id=user_id, article_id=article_id))
            await self.session.flush()

    async def unlike_article(self, user_id: int, article_id: int) -> None:
        like = await self.session.scalar(
            select(LikedArticle).where(
                LikedArticle.user_id == user_id, LikedArticle.article_id == article_id
            )
        )
        if like is not None:
            await self.session.delete(like)
            await self.session.flush()

    async def is_liked(self, user_id: int, article_id: int) -> bool:
        like = await self.session.scalar(
            select(LikedArticle).where(
                LikedArticle.user_id == user_id, LikedArticle.article_id == article_id
            )
        )
        return like is not None

    async def list_liked_articles(self, user_id: int) -> list[Article]:
        result = await self.session.scalars(
            select(Article)
            .join(LikedArticle, LikedArticle.article_id == Article.id)
            .where(LikedArticle.user_id == user_id)
            .options(joinedload(Article.source))
            .order_by(LikedArticle.liked_at.desc())
        )
        return list(result.all())

    async def set_subscribed(self, user: User, subscribed: bool) -> None:
        """Turn the newsletter on or off for one reader. Idempotent."""
        user.subscribed = subscribed
        await self.session.flush()

    async def list_newsletter_recipients(self) -> list[User]:
        """Everyone the newsletter may be sent to."""
        result = await self.session.scalars(
            select(User)
            .where(User.confirmed.is_(True), User.subscribed.is_(True))
            .order_by(User.id)
        )
        return list(result.all())

    async def list_admins(self) -> list[User]:
        """Everyone the stats report goes to: confirmed admins, subscribed or not."""
        result = await self.session.scalars(
            select(User)
            .where(User.confirmed.is_(True), User.role == Role.ADMIN)
            .order_by(User.id)
        )
        return list(result.all())
