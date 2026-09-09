"""Every query in the project. Nothing else may import select()."""

from __future__ import annotations

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from .models import Article, Source
from .utils import like_escape, parse_published, slugify


class Repository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save_articles(self, payloads: list[dict]) -> list[Article]:
        return [
            self.save_article(payload, self.save_source(payload.get("source") or {}))
            for payload in payloads
            # NewsAPI returns redacted entries with url=None, and url is the natural key.
            if payload.get("url")
        ]

    def get_article_by_id(self, article_id: int) -> Article | None:
        """One article with its source, or None for the 404."""
        return self.session.scalar(
            select(Article)
            .where(Article.id == article_id)
            # joinedload, so reading article.source later is not a second
            # query -- the N+1 this whole file exists to keep in one place.
            .options(joinedload(Article.source))
        )

    def list_articles(
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

        total = self.session.scalar(
            select(func.count()).select_from(Article).where(*where)
        )

        articles = self.session.scalars(
            select(Article)
            .where(*where)
            # The caller reads article.source on every row; without this, N+1.
            .options(joinedload(Article.source))
            # id DESC tie-breaks: OFFSET over a non-unique order repeats and skips rows.
            .order_by(Article.published_at.desc().nulls_last(), Article.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()

        return list(articles), total or 0

    def article_counts_by_source(self) -> list[tuple[str, str, int]]:
        rows = self.session.execute(
            select(Source.slug, Source.name, func.count(Article.id))
            .outerjoin(Source.articles)
            .group_by(Source.id)
            .order_by(func.count(Article.id).desc(), Source.name)
        ).all()
        return [(slug, name, count) for slug, name, count in rows]

    def ping(self) -> bool:
        return self.session.scalar(select(text("1"))) == 1

    def save_source(self, payload: dict) -> Source:
        """Find or create the source named in an article's `source` object."""
        slug = payload.get("id") or slugify(payload.get("name") or "unknown")
        source = self.session.scalar(select(Source).where(Source.slug == slug))
        if source is None:
            source = Source(slug=slug, name=payload.get("name") or slug)
            self.session.add(source)
            # flush, not commit: source.id must exist for the article referencing it.
            self.session.flush()
        return source

    def save_article(self, payload: dict, source: Source) -> Article:
        """Find or create by `url`, so a story seen twice stays one row."""
        article = self.session.scalar(
            select(Article).where(Article.url == payload["url"])
        )
        if article is None:
            article = Article(url=payload["url"])
            self.session.add(article)

        # Assigned on both branches: otherwise a template reading article.source
        # after the session closes lazy-loads on a detached object and raises.
        article.source = source
        article.title = payload.get("title") or "(untitled)"
        article.description = payload.get("description")
        article.content = payload.get("content")
        article.image_url = payload.get("urlToImage")
        article.author = payload.get("author")
        article.published_at = parse_published(payload.get("publishedAt"))
        self.session.flush()
        return article
