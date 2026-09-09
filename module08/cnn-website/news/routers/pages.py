"""The HTML pages, rendered with Jinja through Starlette's template support."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .. import news_api
from ..dependencies import SessionDep
from ..repository import Repository
from ..utils import domain

templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
templates.env.filters["domain"] = domain

# response_class on the router: without it FastAPI documents these as JSON.
router = APIRouter(default_response_class=HTMLResponse, include_in_schema=False)


@router.get("/", name="index")
async def index(request: Request, session: SessionDep, q: str = ""):
    """Headlines, or search results for ?q=. Spends a NewsAPI request per load."""
    query = q.strip()

    articles, error = [], None
    try:
        payloads = await (news_api.search(query) if query else news_api.top_headlines())
    except news_api.NewsAPIError as exc:
        # A refusal is not a crash: banner in the template, not a 500.
        error = str(exc)
    else:
        articles = await Repository(session).save_articles(payloads)

    return templates.TemplateResponse(
        request,
        "index.html",
        {"articles": articles, "query": query, "error": error},
    )


@router.get("/article/{article_id}", name="article")
async def article(article_id: int, request: Request, session: SessionDep):
    """Detail page, read from the database -- this route never calls NewsAPI."""
    record = await Repository(session).get_article_by_id(article_id)
    if record is None:
        raise HTTPException(status_code=404, detail="article not found")

    return templates.TemplateResponse(request, "article.html", {"article": record})


@router.get("/liked", name="liked")
async def liked_page(request: Request):
    """A shell. There is no session, so likes.js reads the picked reader from
    localStorage and fills the list from GET /api/users/{user_id}/liked.
    """
    return templates.TemplateResponse(request, "liked.html", {})
