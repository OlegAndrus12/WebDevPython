"""A cache-aside layer for article responses, on Redis: every failure is logged and swallowed."""

from __future__ import annotations

import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .schemas import ArticleOut
from .settings import settings

logger = logging.getLogger(__name__)

redis_client = Redis.from_url(settings.redis_url, decode_responses=True)


async def get_article(article_id: int) -> ArticleOut | None:
    """The cached article, or None for a miss or an error."""
    # RuntimeError alongside RedisError: a pooled connection belongs to the loop that
    # opened it, and the Celery tasks close theirs, so reuse raises "Event loop is closed".
    try:
        raw = await redis_client.get(f"article:{article_id}")
    except (RedisError, RuntimeError):
        logger.warning("cache read failed for article %s", article_id, exc_info=True)
        return None
    if raw is None:
        return None
    try:
        return ArticleOut.model_validate_json(raw)
    except ValueError:
        logger.info("discarding unparseable cache entry for article %s", article_id)
        return None


async def set_article(article: ArticleOut) -> None:
    """Store an article under its id, with the configured TTL."""
    try:
        await redis_client.set(
            f"article:{article.id}",
            article.model_dump_json(),
            ex=settings.article_cache_ttl_seconds,
        )
    except (RedisError, RuntimeError):
        logger.warning("cache write failed for article %s", article.id, exc_info=True)


async def invalidate_article(article_id: int) -> None:
    """Drop an article's entry, called when its row is written."""
    try:
        await redis_client.delete(f"article:{article_id}")
    except (RedisError, RuntimeError):
        logger.warning("cache invalidation failed for article %s", article_id, exc_info=True)


async def close() -> None:
    """Release the connection pool on shutdown."""
    await redis_client.aclose()
