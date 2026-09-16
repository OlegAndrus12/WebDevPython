"""The debug toolbar: development only, installed from middleware.py when DEBUG is on."""

from __future__ import annotations

from collections.abc import Sequence

from debug_toolbar import middleware as toolbar_middleware
from debug_toolbar.middleware import DebugToolbarMiddleware
from debug_toolbar.panels.sqlalchemy import SQLAlchemyPanel as BaseSQLAlchemyPanel
from fastapi import FastAPI, Request
from starlette.routing import BaseRoute, Match

from .db import engine


def find_route(
    request: Request, routes: Sequence[BaseRoute] | None = None
) -> BaseRoute | None:
    """The route this request will reach, or None if it will not reach one."""
    # Replaces the toolbar's own matched_route: since FastAPI 0.137 include_router()
    # appends an _IncludedRouter with no `endpoint`, which it reads as "not a route".
    if routes is None:
        routes = request.app.routes

    for route in routes:
        match, _ = route.matches(request.scope)

        if match != Match.FULL:
            continue
        if hasattr(route, "endpoint"):
            return route

        included = getattr(route, "original_router", None)
        if included is not None:
            found = find_route(request, included.routes)
            if found is not None:
                return found
            continue
        return None
    return None


class SQLAlchemyPanel(BaseSQLAlchemyPanel):
    """The SQL panel, handed this app's one engine instead of discovering it."""

    async def add_engines(self, request: Request) -> None:
        # Stock discovery calls solve_dependencies(), whose signature changed after the
        # toolbar's 2024 release; .sync_engine because events reject an AsyncEngine.
        self.engines.add(engine.sync_engine)


def install(app: FastAPI) -> None:
    """Attach the toolbar. Call once, from middleware.install()."""
    # Patched on the module, because dispatch() looks the name up there each request.
    toolbar_middleware.matched_route = find_route

    # No allowed_hosts: inside the container the client is a 172.x bridge address,
    # so a localhost allowlist would hide the toolbar in the only setup this runs in.
    app.add_middleware(DebugToolbarMiddleware, panels=[f"{__name__}.SQLAlchemyPanel"])
