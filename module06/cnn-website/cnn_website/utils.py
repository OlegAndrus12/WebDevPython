"""Pure functions: no Flask, no SQLAlchemy, no settings, so any layer can import them."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse


def article_json(article) -> dict:
    """Our JSON shape for one article. Call it with the session still open."""
    return {
        "id": article.id,
        "title": article.title,
        "description": article.description,
        "content": article.content,
        "url": article.url,
        "image_url": article.image_url,
        "author": article.author,
        # isoformat: Flask's JSON provider would render an HTTP-date instead.
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "source": {"slug": article.source.slug, "name": article.source.name},
    }


def int_arg(
    name: str,
    raw: str | None,
    *,
    default: int,
    minimum: int,
    maximum: int | None = None,
) -> int:
    """One query parameter as a bounded int. Raises ValueError with a message
    meant for the response body.
    """
    if raw is None or raw == "":
        return default

    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None

    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}, got {value}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}, got {value}")
    return value


def domain(url: str) -> str:
    """`https://edition.cnn.com/2026/...` -> `edition.cnn.com`, for link labels."""
    return urlparse(url).netloc or url


def parse_published(value: str | None) -> datetime | None:
    """NewsAPI's `2026-08-27T09:30:00Z`; None if absent or unparseable."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def like_escape(value: str) -> str:
    """Escape LIKE wildcards -- an unescaped % in a search matches every row."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def slugify(name: str) -> str:
    return "-".join(name.lower().split())[:80]
