"""The newsletter task, and the three things a test must not let it reach.

Patch the name in the module that *calls* a function: news/tasks.py does
`from .mail import send_newsletter_email`, so patching `news.mail.…` does
nothing.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from news import news_api, tasks


def headline(n: int) -> dict:
    """One article shaped the way NewsAPI shapes them."""
    return {
        "source": {"id": "cnn", "name": "CNN"},
        "author": "A. Reporter",
        "title": f"Headline {n}",
        "description": f"Summary {n}",
        "url": f"https://news.example/story-{n}",
        "urlToImage": None,
        "publishedAt": f"2026-01-0{n}T09:30:00+00:00",
        "content": f"Body {n}",
    }


@pytest.fixture
def task_session(monkeypatch, session):
    """Point the task at the test's session. Not autouse: a task test that
    forgot it would try to reach Postgres and fail loudly, which is right."""

    @asynccontextmanager
    async def fake_get_session():
        yield session

    monkeypatch.setattr(tasks, "get_session", fake_get_session)


@pytest.fixture
def fetched(monkeypatch):
    """Replaces NewsAPI. Returned so the test can both arrange and assert on it."""
    mock = AsyncMock(return_value=[])
    monkeypatch.setattr(news_api, "top_headlines", mock)
    return mock


async def test_newsletter_goes_to_confirmed_subscribers_only(
    task_session, fetched, outbox, users
):
    """Three users, one email: an unconfirmed address may never be mailed, and
    a confirmed reader who did not subscribe may not either."""
    fetched.return_value = [headline(1)]
    subscriber = await users.create(subscribed=True, confirmed=True)
    await users.create(subscribed=True, confirmed=False)
    await users.create(subscribed=False, confirmed=True)

    result = await tasks._send_newsletter()

    assert result == {"articles": 1, "sent": 1, "failed": 0}
    assert [email.recipients for email in outbox] == [[subscriber.email]]
    fetched.assert_awaited_once()
