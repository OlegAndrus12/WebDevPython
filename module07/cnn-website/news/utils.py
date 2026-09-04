"""Pure functions: no FastAPI, no SQLAlchemy, no settings, so any layer can import them."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse


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
