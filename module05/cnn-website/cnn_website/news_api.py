from __future__ import annotations

import requests

from .settings import settings


class NewsAPIError(RuntimeError):
    """NewsAPI refused the request. Carries the message meant for the reader."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


def top_headlines() -> list[dict]:
    """Front page: the newest stories from `settings.default_source`."""
    return _get(
        "top-headlines",
        {"sources": settings.default_source, "pageSize": settings.page_size},
    )


def search(query: str) -> list[dict]:
    """Search everything NewsAPI indexes, newest first.

    Note for the free plan: /everything only reaches articles older than 24
    hours, so a story on the front page may be missing from a search for it.
    """
    return _get(
        "everything",
        {
            "q": query,
            "pageSize": settings.page_size,
            "sortBy": "publishedAt",
            "language": "en",
        },
    )


def _get(endpoint: str, params: dict) -> list[dict]:
    """Returns the articles. Raises NewsAPIError on a refusal."""
    try:
        response = requests.get(
            f"{settings.news_api_url}/{endpoint}",
            params=params,
            headers={"X-Api-Key": settings.news_api_key.get_secret_value()},
            timeout=10.0,
        )
    except requests.RequestException as exc:
        # DNS failure, refused connection, timeout -- no HTTP response at all.
        raise NewsAPIError(f"Could not reach NewsAPI: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise NewsAPIError("NewsAPI returned a non-JSON response") from exc

    if payload.get("status") != "ok":
        raise NewsAPIError(
            payload.get("message", "NewsAPI returned an error"), payload.get("code")
        )

    # `articles` can legitimately be absent on a zero-result query.
    return payload.get("articles", [])
