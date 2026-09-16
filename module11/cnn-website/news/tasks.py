"""The scheduled work: the reader newsletter, and the admin stats report."""

from __future__ import annotations

import asyncio
import logging

import httpx
from celery.utils.log import get_task_logger
from fastapi_mail.errors import ConnectionErrors

from . import news_api
from .celery_app import celery_app
from .db import get_session
from .mail import send_newsletter_email, send_stats_report_email
from .repository import Repository
from .schemas import SourceCount, Stats
from .settings import settings

logger: logging.Logger = get_task_logger(__name__)


@celery_app.task(
    name="news.tasks.send_newsletter",
    autoretry_for=(news_api.NewsAPIError, httpx.HTTPError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=2,
)
def send_newsletter() -> dict[str, int]:
    """Fetch the headlines, save them, and mail them to every subscriber."""
    return asyncio.run(_send_newsletter())


async def _send_newsletter() -> dict[str, int]:
    async with get_session() as session:
        repo = Repository(session)

        payloads = await news_api.top_headlines()
        articles = await repo.save_articles(payloads)
        articles = articles[: settings.newsletter_max_articles]

        if not articles:
            logger.info("NewsAPI returned nothing; sending nothing")
            return {"articles": 0, "sent": 0, "failed": 0}

        recipients = await repo.list_newsletter_recipients()
        logger.info(
            "%d articles to announce to %d subscribers", len(articles), len(recipients)
        )

        sent = failed = 0
        for user in recipients:
            try:
                await send_newsletter_email(
                    email=user.email,
                    username=user.username,
                    articles=articles,
                    host=settings.public_base_url,
                )
            except ConnectionErrors:
                failed += 1
                logger.warning("could not mail %s", user.email, exc_info=True)
            else:
                sent += 1

        logger.info("newsletter sent to %d subscribers, %d failed", sent, failed)
        return {"articles": len(articles), "sent": sent, "failed": failed}


@celery_app.task(
    name="news.tasks.send_stats_report",
    retry_backoff=True,
    retry_jitter=True,
    max_retries=2,
)
def send_stats_report() -> dict[str, int]:
    """Mail the site's article counts to every admin."""
    return asyncio.run(_send_stats_report())


async def _send_stats_report() -> dict[str, int]:
    async with get_session() as session:
        repo = Repository(session)

        admins = await repo.list_admins()
        if not admins:
            logger.info("no confirmed admins; sending nothing")
            return {"sent": 0, "failed": 0}

        counts = await repo.article_counts_by_source()
        stats = Stats(
            sources=[
                SourceCount(slug=slug, name=name, articles=count)
                for slug, name, count in counts
            ],
            total_articles=sum(count for _, _, count in counts),
            total_sources=len(counts),
        )

        logger.info(
            "%d articles from %d sources, reporting to %d admins",
            stats.total_articles,
            stats.total_sources,
            len(admins),
        )

        sent = failed = 0
        for admin in admins:
            try:
                await send_stats_report_email(
                    email=admin.email,
                    username=admin.username,
                    stats=stats,
                    host=settings.public_base_url,
                )
            except ConnectionErrors:
                failed += 1
                logger.warning("could not mail %s", admin.email, exc_info=True)
            else:
                sent += 1

        logger.info("stats report sent to %d admins, %d failed", sent, failed)
        return {"sent": sent, "failed": failed}
