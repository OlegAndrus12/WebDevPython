"""A thin async client for newsapi.org. No FastAPI here, no SQLAlchemy either."""

from __future__ import annotations

import httpx

from .settings import settings

_client = httpx.AsyncClient(base_url=settings.news_api_url, timeout=10.0)


class NewsAPIError(RuntimeError):
    """NewsAPI refused the request. Carries the message meant for the reader."""

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        self.code = code


async def top_headlines() -> list[dict]:
    """Front page: the newest stories from `settings.default_source`."""
    return await _get(
        "top-headlines",
        {"sources": settings.default_source, "pageSize": settings.page_size},
    )


async def search(query: str) -> list[dict]:
    """Search everything NewsAPI indexes, newest first."""
    return await _get(
        "everything",
        {
            "q": query,
            "pageSize": settings.page_size,
            "sortBy": "publishedAt",
            "language": "en",
        },
    )


async def close() -> None:
    """aclose(), not close(): shutting down an AsyncClient is itself awaitable."""
    await _client.aclose()


async def _get(endpoint: str, params: dict) -> list[dict]:
    """Returns the articles. Raises NewsAPIError on a refusal."""
    try:
        response = await _client.get(
            f"/{endpoint}",
            params=params,
            # The key travels in a header, not `?apiKey=`: query strings end up
            # in access logs, proxy caches and browser history.
            headers={"X-Api-Key": settings.news_api_key.get_secret_value()},
        )
    except httpx.RequestError as exc:
        raise NewsAPIError(f"Could not reach NewsAPI: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise NewsAPIError("NewsAPI returned a non-JSON response") from exc

    # NewsAPI also returns 200 with an error body, so the status code alone
    # cannot tell success from failure.
    if payload.get("status") != "ok":
        raise NewsAPIError(
            payload.get("message", "NewsAPI returned an error"), payload.get("code")
        )

    return payload.get("articles", [])
