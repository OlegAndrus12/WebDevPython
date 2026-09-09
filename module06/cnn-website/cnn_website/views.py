"""Routes and the app object. No SQL here -- Repository answers every query."""

from __future__ import annotations

from flask import Flask, abort, render_template, request

from . import news_api
from .db import get_session
from .repository import Repository
from .settings import settings
from .utils import article_json, domain, int_arg

app = Flask(__name__)
app.config["SECRET_KEY"] = settings.secret_key.get_secret_value()

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100

# Jinja filter: {{ article.url | domain }}
app.add_template_filter(domain, "domain")


@app.get("/")
def index():
    """Headlines, or search results for ?q=. Spends a NewsAPI request per load."""
    query = request.args.get("q", "").strip()

    articles, error = [], None
    try:
        payloads = news_api.search(query) if query else news_api.top_headlines()
    except news_api.NewsAPIError as exc:
        # A refusal is not a crash: banner in the template, not a 500.
        error = str(exc)
    else:
        with get_session() as session:
            articles = Repository(session).save_articles(payloads)

    return render_template("index.html", articles=articles, query=query, error=error)


@app.get("/article/<int:article_id>")
def article(article_id: int):
    """Detail page, read from the database -- this route never calls NewsAPI."""
    with get_session() as session:
        article = Repository(session).get_article_by_id(article_id)
        if article is None:
            abort(404)

    return render_template("article.html", article=article)


@app.get("/api/articles")
def api_articles():
    """Stored articles as JSON, newest first. Params: q, page, per_page (max 100)."""
    try:
        page = int_arg("page", request.args.get("page"), default=1, minimum=1)
        per_page = int_arg(
            "per_page",
            request.args.get("per_page"),
            default=DEFAULT_PER_PAGE,
            minimum=1,
            maximum=MAX_PER_PAGE,
        )
    except ValueError as exc:
        # 400, not a silent default: `per_page=-5` is a client bug worth reporting.
        return {"error": str(exc)}, 400

    query = request.args.get("q", "").strip()

    with get_session() as session:
        articles, total = Repository(session).list_articles(
            query=query or None,
            limit=per_page,
            offset=(page - 1) * per_page,
        )
        # Inside the block: once the session closes these only keep what was loaded.
        items = [article_json(article) for article in articles]

    return {
        "articles": items,
        "query": query,
        "page": page,
        "per_page": per_page,
        "total": total,
        # Ceiling division; 0 pages when empty, so `page > pages` means past the end.
        "pages": -(-total // per_page),
    }


@app.get("/api/articles/<int:article_id>")
def api_article(article_id: int):
    """The same row the HTML page renders, as JSON."""
    with get_session() as session:
        article = Repository(session).get_article_by_id(article_id)
        if article is None:
            # JSON, not abort(404), which would send HTML to a client parsing a body.
            return {"error": "article not found", "id": article_id}, 404

        return article_json(article)


@app.get("/api/stats")
def api_stats():
    """How many stored articles each source accounts for."""
    with get_session() as session:
        counts = Repository(session).article_counts_by_source()

    return {
        "sources": [
            {"slug": slug, "name": name, "articles": count}
            for slug, name, count in counts
        ],
        "total_articles": sum(count for _, _, count in counts),
        "total_sources": len(counts),
    }


@app.get("/healthz")
def healthz():
    """Liveness for the compose healthcheck: is the database reachable?"""
    with get_session() as session:
        ok = Repository(session).ping()
    return {"status": "ok" if ok else "error"}
