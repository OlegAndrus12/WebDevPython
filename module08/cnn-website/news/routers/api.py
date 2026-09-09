"""The JSON API. Reads the database only -- nothing here calls NewsAPI."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..dependencies import SessionDep
from ..repository import Repository
from ..schemas import ArticleOut, ArticlePage, SourceCount, Stats

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

router = APIRouter(prefix="/api", tags=["articles"])


@router.get("/articles", response_model=ArticlePage, summary="List stored articles")
async def list_articles(
    session: SessionDep,
    q: str = Query("", description="Substring of title or description"),
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
) -> ArticlePage:
    """Stored articles, newest first.

    `q` searches what is stored, which is not what `/?q=` does -- that one asks
    NewsAPI. A story NewsAPI has never handed us is not here.
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
        # Ceiling division; 0 pages when empty, so `page > pages` means past the end.
        pages=-(-total // per_page),
    )


@router.get(
    "/articles/{article_id}",
    response_model=ArticleOut,
    responses={404: {"description": "No article with that id"}},
)
async def get_article(article_id: int, session: SessionDep):
    """One stored article. The same row the HTML page renders."""
    article = await Repository(session).get_article_by_id(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")
    return article


@router.get("/stats", response_model=Stats)
async def stats(session: SessionDep) -> Stats:
    """How many stored articles each source accounts for."""
    counts = await Repository(session).article_counts_by_source()
    return Stats(
        sources=[
            SourceCount(slug=slug, name=name, articles=count)
            for slug, name, count in counts
        ],
        total_articles=sum(count for _, _, count in counts),
        total_sources=len(counts),
    )
