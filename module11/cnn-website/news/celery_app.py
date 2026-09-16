"""The Celery app: configuration and the beat schedule."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from .settings import settings


celery_app = Celery(
    "news",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["news.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    result_expires=settings.celery_result_expires_seconds,
    task_soft_time_limit=60,
    task_time_limit=90,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "newsletter": {
            "task": "news.tasks.send_newsletter",
            # Every minute, rather than once a day at settings.newsletter_hour /
            # settings.newsletter_minute -- so the task can actually be watched
            # running. Safe to leave on in dev: mailpit accepts the mail and
            # delivers none of it. Restore the daily schedule with
            #   crontab(hour=settings.newsletter_hour, minute=settings.newsletter_minute)
            "schedule": crontab(minute="*"),
        },
        "stats-report": {
            "task": "news.tasks.send_stats_report",
            "schedule": crontab(
                hour=settings.stats_report_hour, minute=settings.stats_report_minute
            ),
        },
    },
)
