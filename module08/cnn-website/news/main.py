"""The FastAPI application.

    uv run uvicorn news:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Response, status
from fastapi.staticfiles import StaticFiles

from .dependencies import SessionDep
from .repository import Repository
from .routers import api, pages, users
from .schemas import Health

PACKAGE_ROOT = Path(__file__).resolve().parent

app = FastAPI(
    title="CNN Reader",
    description="A news reader on newsapi.org: async FastAPI, SQLAlchemy asyncio, Alembic, Postgres.",
    version="0.3.0",
)

# name="static" is what `url_for('static', path=...)` resolves against.
app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="static")

# The API first, so /docs lists it above the pages.
app.include_router(api.router)
app.include_router(users.router)
app.include_router(pages.router)


@app.get("/healthz", response_model=Health, tags=["ops"])
async def healthz(session: SessionDep, response: Response) -> Health:
    """Liveness for the compose healthcheck: is the database reachable?"""
    ok = await Repository(session).ping()
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Health(status="ok" if ok else "error", db="ok" if ok else "unreachable")
