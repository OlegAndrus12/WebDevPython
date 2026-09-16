"""The HTML pages, rendered with Jinja through Starlette's template support."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from .. import news_api
from ..db import get_db
from ..repository import Repository
from ..utils import domain

templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
templates.env.filters["domain"] = domain

router = APIRouter(default_response_class=HTMLResponse, include_in_schema=False)


@router.get("/", name="index")
async def index(request: Request, q: str = "", session: AsyncSession = Depends(get_db)):
    """Headlines, or search results for ?q=. Spends a NewsAPI request per load."""
    query = q.strip()

    articles, error = [], None
    try:
        payloads = await (news_api.search(query) if query else news_api.top_headlines())
    except news_api.NewsAPIError as exc:
        error = str(exc)
    else:
        articles = await Repository(session).save_articles(payloads)

    return templates.TemplateResponse(
        request,
        "index.html",
        {"articles": articles, "query": query, "error": error},
    )


@router.get("/article/{article_id}", name="article")
async def article(article_id: int, request: Request, session: AsyncSession = Depends(get_db)):
    """Detail page, read from the database -- this route never calls NewsAPI."""
    record = await Repository(session).get_article_by_id(article_id)
    if record is None:
        raise HTTPException(status_code=404, detail="article not found")

    return templates.TemplateResponse(request, "article.html", {"article": record})


@router.get("/login", name="login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@router.get("/register", name="register")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {})


@router.get("/verify-email", name="verify_email")
async def verify_email_page(request: Request):
    """Where the link in the verification email lands."""
    return templates.TemplateResponse(request, "verify.html", {})


@router.get("/liked", name="liked")
async def liked_page(request: Request):
    """Also a shell: the list itself comes from GET /api/me/liked, fetched"""
    return templates.TemplateResponse(request, "liked.html", {})


@router.get("/architecture", name="architecture")
async def architecture_page(request: Request):
    """The architecture map, revealed only to admins.

    No `Depends(get_current_admin)` here, and it is not an oversight: this
    app's auth is a bearer token in localStorage rather than a cookie, so a
    browser navigating to this URL sends no Authorization header and a
    server-side dependency would 401 every visit.

    So the gate is the same one /liked uses -- the page asks
    GET /api/auth/me for itself and only unhides the diagram for
    role='admin'. That hides the page from a reader, but the markup is in the
    response either way: a `curl /architecture` still returns it. Genuinely
    gating the content means moving the diagram behind an admin-only API
    route and injecting it, which is a bigger change than this page is worth.
    """
    return templates.TemplateResponse(request, "architecture.html", {})
