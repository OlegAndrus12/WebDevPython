"""Outbound mail: the verification link, the newsletter, the stats report."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from fastapi_mail.errors import ConnectionErrors

from .models import Article
from .schemas import Stats
from .security import auth_service
from .settings import settings

logger = logging.getLogger(__name__)

TEMPLATE_FOLDER = Path(__file__).resolve().parent / "templates"

conf = ConnectionConfig(
    MAIL_USERNAME=settings.mail_username,
    MAIL_PASSWORD=settings.mail_password,
    MAIL_FROM=settings.mail_from,
    MAIL_FROM_NAME=settings.mail_from_name,
    MAIL_PORT=settings.mail_port,
    MAIL_SERVER=settings.mail_server,
    MAIL_STARTTLS=settings.mail_starttls,
    MAIL_SSL_TLS=settings.mail_ssl_tls,
    USE_CREDENTIALS=settings.mail_use_credentials,
    VALIDATE_CERTS=settings.mail_validate_certs,
    TEMPLATE_FOLDER=TEMPLATE_FOLDER,
)

mailer = FastMail(conf)


async def send_verification_email(email: str, username: str, host: str) -> None:
    """Mail `email` a link that confirms it."""
    token = await auth_service.create_verification_token(email)
    message = MessageSchema(
        subject="Confirm your email",
        recipients=[email],
        template_body={
            "host": host,
            "username": username,
            "token": token,
            "expires_minutes": settings.verification_token_expire_minutes,
        },
        subtype=MessageType.html,
    )
    try:
        await mailer.send_message(message, template_name="email/verify_email.html")
    except ConnectionErrors:
        logger.exception("could not send the verification email to %s", email)


async def send_newsletter_email(
    email: str,
    username: str,
    articles: Sequence[Article],
    host: str,
) -> None:
    """Mail one reader the stories in `articles`. Raises on an SMTP failure."""
    message = MessageSchema(
        subject=f"{len(articles)} new stories on CNN Reader",
        recipients=[email],
        template_body={
            "host": host,
            "username": username,
            "articles": articles,
        },
        subtype=MessageType.html,
    )
    await mailer.send_message(message, template_name="email/newsletter.html")


async def send_stats_report_email(
    email: str,
    username: str,
    stats: Stats,
    host: str,
) -> None:
    """Mail one admin the site's article counts. Raises on an SMTP failure."""
    message = MessageSchema(
        subject=f"CNN Reader stats: {stats.total_articles} articles "
        f"from {stats.total_sources} sources",
        recipients=[email],
        template_body={
            "host": host,
            "username": username,
            "stats": stats,
        },
        subtype=MessageType.html,
    )
    await mailer.send_message(message, template_name="email/stats_report.html")
