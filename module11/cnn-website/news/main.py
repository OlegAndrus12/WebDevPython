"""The FastAPI application, async from the route down to the driver."""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Response, status
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_db
from .middleware import install as install_middleware
from .repository import Repository
from .routers import api, auth, newsletter, pages
from .schemas import Health
from .settings import settings

PACKAGE_ROOT = Path(__file__).resolve().parent


app = FastAPI(
    title="CNN Reader",
    description="A news reader on newsapi.org: async FastAPI, SQLAlchemy asyncio, Alembic, Postgres.",
    version="0.3.0",
    debug=settings.debug,
)

install_middleware(app)

app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="static")

app.include_router(api.router)
app.include_router(auth.router)
app.include_router(newsletter.router)
app.include_router(pages.router)


@app.get("/healthz", response_model=Health, tags=["ops"])
async def healthz(response: Response, session: AsyncSession = Depends(get_db)) -> Health:
    """Liveness for the compose healthcheck: is the database reachable?"""
    ok = await Repository(session).ping()
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return Health(status="ok" if ok else "error", db="ok" if ok else "unreachable")
