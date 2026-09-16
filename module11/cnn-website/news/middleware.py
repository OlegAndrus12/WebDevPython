"""Every HTTP middleware this app installs, and the order it installs them in."""

from __future__ import annotations

import time

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from redis.exceptions import RedisError

from . import cache
from .settings import settings


async def rate_limit(request: Request, call_next):
    """One request per window per client IP, on /api only. Fails open."""

    if not request.url.path.startswith("/api"):
        return await call_next(request)

    window = settings.rate_limit_window_seconds
    # A window of 0 turns the limiter off. Redis would reject `EX 0` anyway and
    # the fail-open branch below would let the request through by accident --
    # this says so on purpose instead. It is how the test suite disables the
    # limiter (tests/conftest.py) without patching this function out, and it
    # doubles as the switch for a dev session that hammers /api by hand.
    if window <= 0:
        return await call_next(request)

    client = request.client.host if request.client else "unknown"

    try:
        fresh = await cache.redis_client.set(f"rl:{client}", 1, ex=window, nx=True)
    except (RedisError, RuntimeError):
        return await call_next(request)

    if not fresh:
        return JSONResponse(
            {"detail": "Too many requests"},
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(window)},
        )
    return await call_next(request)


def install(app: FastAPI) -> None:
    """Add the middleware stack. Order is load-bearing, see below."""
    if settings.debug:
        # Imported here, not at module scope: a `uv sync --no-dev` install has
        # no toolbar.
        from .debug import install as install_debug_toolbar

        install_debug_toolbar(app)

    # Last, so it ends up outermost -- add_middleware inserts at position 0.
    # A 429 returned inside the toolbar never reaches the router, and the
    # toolbar's panels then raise KeyError('endpoint') on a routeless request.
    app.middleware("http")(rate_limit)
