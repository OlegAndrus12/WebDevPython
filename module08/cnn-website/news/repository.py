"""Every query in the project. Nothing else may import select()."""

from __future__ import annotations

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from .models import Article, LikedArticle, Source, User
from .utils import like_escape, parse_published, slugify


class Repository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_articles(self, payloads: list[dict]) -> list[Article]:
        """Upsert a whole NewsAPI response, in the order given.

        A serial loop, not asyncio.gather: one session owns one connection, and
        an AsyncSession is not safe to drive from two tasks at once.
        """
        articles = []
        for payload in payloads:
            # NewsAPI returns redacted entries with url=None, and url is the key.
            if not payload.get("url"):
                continue
            source = await self.save_source(payload.get("source") or {})
            articles.append(await self.save_article(payload, source))
        return articles

    async def get_article_by_id(self, article_id: int) -> Article | None:
        return await self.session.scalar(
            select(Article)
            .where(Article.id == article_id)
            # Mandatory, not an optimisation: a later lazy load of `source`
            # raises MissingGreenlet instead of costing a second query.
            .options(joinedload(Article.source))
        )

    async def list_articles(
        self, query: str | None = None, limit: int = 20, offset: int = 0
    ) -> tuple[list[Article], int]:
        """One page of stored articles, newest first, plus the matching total."""
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
            # id DESC tie-breaks: OFFSET over a non-unique order repeats rows.
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
            # flush, not commit: source.id must exist for the article using it.
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

        # Assigned on both branches: otherwise reading article.source later is
        # a lazy load, which raises rather than querying.
        article.source = source
        article.title = payload.get("title") or "(untitled)"
        article.description = payload.get("description")
        article.content = payload.get("content")
        article.image_url = payload.get("urlToImage")
        article.author = payload.get("author")
        article.published_at = parse_published(payload.get("publishedAt"))
        await self.session.flush()
        return article

    # ---- users ----------------------------------------------------------

    async def list_users(self) -> list[User]:
        result = await self.session.scalars(select(User).order_by(User.id))
        return list(result.all())

    async def get_user_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_user_by_email(self, email: str) -> User | None:
        return await self.session.scalar(select(User).where(User.email == email))

    async def get_user_by_username(self, username: str) -> User | None:
        return await self.session.scalar(select(User).where(User.username == username))

    async def create_user(self, username: str, email: str) -> User:
        user = User(username=username, email=email)
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_user(self, user: User, **fields) -> User:
        """Assign only the keys given, so an omitted PATCH field stays put."""
        for name, value in fields.items():
            setattr(user, name, value)
        await self.session.flush()
        return user

    async def delete_user(self, user: User) -> None:
        # liked_articles.user_id is ON DELETE CASCADE, so the likes go too.
        await self.session.delete(user)
        await self.session.flush()

    # ---- likes ----------------------------------------------------------

    async def like_article(self, user_id: int, article_id: int) -> None:
        """Idempotent: the composite primary key would reject a second insert,
        so asking first turns that into a quiet success.
        """
        if not await self.is_liked(user_id, article_id):
            self.session.add(LikedArticle(user_id=user_id, article_id=article_id))
            await self.session.flush()

    async def unlike_article(self, user_id: int, article_id: int) -> None:
        like = await self.session.get(LikedArticle, (user_id, article_id))
        if like is not None:
            await self.session.delete(like)
            await self.session.flush()

    async def is_liked(self, user_id: int, article_id: int) -> bool:
        return await self.session.get(LikedArticle, (user_id, article_id)) is not None

    async def list_liked_articles(self, user_id: int) -> list[Article]:
        """Newest like first -- ordered by when it was liked, not published."""
        result = await self.session.scalars(
            select(Article)
            .join(LikedArticle, LikedArticle.article_id == Article.id)
            .where(LikedArticle.user_id == user_id)
            .options(joinedload(Article.source))
            .order_by(LikedArticle.liked_at.desc())
        )
        return list(result.all())
