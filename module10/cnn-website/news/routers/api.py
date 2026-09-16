"""The JSON API. Reads the database only -- nothing here calls NewsAPI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from .. import cache
from ..db import get_db
from ..models import User
from ..repository import Repository
from ..schemas import ArticleOut, ArticlePage, SourceCount, Stats
from ..security import auth_service

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

router = APIRouter(prefix="/api", tags=["articles"])


EMPTY_PAGE_EXAMPLE = {
    "articles": [],
    "query": "penguins",
    "page": 1,
    "per_page": 20,
    "total": 0,
    "pages": 0,
}


@router.get(
    "/articles",
    response_model=ArticlePage,
    status_code=status.HTTP_200_OK,
    summary="List stored articles",
    response_description="One page of articles, newest first, with the paging state",
    operation_id="listArticles",
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        "page": {
                            "summary": "A populated page",
                            "description": "The shape a client renders from.",
                            "value": {
                                "articles": [
                                    {
                                        "id": 42,
                                        "title": "Markets close higher after rate decision",
                                        "description": "Indices recovered late in the session.",
                                        "content": "Stocks rallied into the close... [+1893 chars]",
                                        "url": "https://www.cnn.com/2026/09/15/markets/rate-decision",
                                        "image_url": "https://media.cnn.com/lead.jpg",
                                        "author": "Jane Doe",
                                        "published_at": "2026-09-15T08:30:00Z",
                                        "source": {"slug": "cnn", "name": "CNN"},
                                    }
                                ],
                                "query": "markets",
                                "page": 1,
                                "per_page": 20,
                                "total": 137,
                                "pages": 7,
                            },
                        },
                        "empty": {
                            "summary": "No matches, or a page past the end",
                            "description": "Still a 200 -- an empty result is not an error.",
                            "value": EMPTY_PAGE_EXAMPLE,
                        },
                    }
                }
            },
        },
        401: {"description": "Missing, malformed, or expired bearer token"},
        422: {
            "description": (
                "`page` below 1, `per_page` outside 1..100, or `q` over 200 characters"
            )
        },
    },
)
async def list_articles(
    q: Annotated[
        str,
        Query(
            title="Search term",
            description=(
                "Case-insensitive substring matched against **title** and "
                "**description**. `%` and `_` are escaped, so they match "
                "literally rather than acting as SQL wildcards. Surrounding "
                "whitespace is trimmed; blank means no filter."
            ),
            max_length=200,
            openapi_examples={
                "unfiltered": {
                    "summary": "Everything",
                    "description": "The default -- no search term at all.",
                    "value": "",
                },
                "word": {
                    "summary": "A single word",
                    "value": "election",
                },
                "wildcard": {
                    "summary": "A literal percent sign",
                    "description": "Matches articles containing `100%`, not every article.",
                    "value": "100%",
                },
            },
        ),
    ] = "",
    page: Annotated[
        int,
        Query(
            title="Page number",
            description="1-based. Past the last page you get an empty list, not a 404.",
            ge=1,
            examples=[1],
        ),
    ] = 1,
    per_page: Annotated[
        int,
        Query(
            title="Page size",
            description=f"Articles per page, 1..{MAX_PER_PAGE}.",
            ge=1,
            le=MAX_PER_PAGE,
            examples=[DEFAULT_PER_PAGE],
        ),
    ] = DEFAULT_PER_PAGE,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
) -> ArticlePage:
    """Stored articles, newest first.

    Reads the database only -- nothing here calls NewsAPI, so the result is
    whatever the last ingest run stored.

    **Ordering** is by `published_at` descending, with `id` descending as the
    tie-breaker, so paging is stable across requests.

    **Auth**: any confirmed user. `current_user` is unused in the body -- the
    dependency is there to gate the route, not to filter the rows.

    **Paging** is offset-based: page 3 at 20 per page skips 40 rows. That is
    fine at this scale; it degrades on very deep pages.
    """
    query = q.strip()
    articles, total = await Repository(session).list_articles(
        query=query or None,
        limit=per_page,
        offset=(page - 1) * per_page,
    )

    return ArticlePage(
        articles=[ArticleOut.model_validate(article) for article in articles],
        query=query,
        page=page,
        per_page=per_page,
        total=total,
        pages=-(-total // per_page),
    )


@router.get(
    "/articles/{article_id}",
    response_model=ArticleOut,
    responses={404: {"description": "No article with that id"}},
)
async def get_article(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
) -> ArticleOut:
    """One stored article, the same row the HTML page renders. Auth-gated,"""
    cached = await cache.get_article(article_id)
    if cached is not None:
        return cached

    article = await Repository(session).get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")

    payload = ArticleOut.model_validate(article)
    await cache.set_article(payload)
    return payload


@router.get("/stats", response_model=Stats)
async def stats(
    session: AsyncSession = Depends(get_db),
    current_admin: User = Depends(auth_service.get_current_admin),
) -> Stats:
    """How many stored articles each source accounts for. Admins only."""
    counts = await Repository(session).article_counts_by_source()
    return Stats(
        sources=[
            SourceCount(slug=slug, name=name, articles=count)
            for slug, name, count in counts
        ],
        total_articles=sum(count for _, _, count in counts),
        total_sources=len(counts),
    )


@router.post(
    "/articles/{article_id}/like",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "No article with that id"}},
)
async def like_article(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    repo = Repository(session)
    if await repo.get_article_by_id(article_id) is None:
        raise HTTPException(status_code=404, detail="article not found")
    await repo.like_article(current_user.id, article_id)


@router.delete("/articles/{article_id}/like", status_code=status.HTTP_204_NO_CONTENT)
async def unlike_article(
    article_id: int,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
):
    await Repository(session).unlike_article(current_user.id, article_id)


@router.get("/me/liked", response_model=list[ArticleOut])
async def liked_articles(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(auth_service.get_current_user),
) -> list[ArticleOut]:
    """Everything the current user has liked, newest like first."""
    articles = await Repository(session).list_liked_articles(current_user.id)
    return [ArticleOut.model_validate(article) for article in articles]
