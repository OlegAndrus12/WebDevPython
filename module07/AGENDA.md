# Module 07 — Agenda

- One `FastAPI()` app composed from `APIRouter`s via `include_router`
- `Depends` and an injected `AsyncSession`: `SessionDep`, `get_db()`
- Validation from type hints: `Query(ge=…, le=…)` → 422
- Pydantic response models, `from_attributes=True`, returning ORM objects
- Automatic OpenAPI: `/docs`, `/redoc`, `/openapi.json`
- `async def` routes, `AsyncSession`, `httpx.AsyncClient`
- What async does *not* buy on a sub-millisecond query
- Eager loading is mandatory: a missed `joinedload` raises `MissingGreenlet`
- `expire_on_commit=False`, and why
- Why `save_articles` is a serial loop, not `asyncio.gather`
- Async Alembic: `run_sync`, sync migration bodies, `asyncio.run` in `env.py`
- psycopg 3 as both drivers; `sqlalchemy[asyncio]` pulls in greenlet
- `pydantic-settings` + `SecretStr`, validated at import
