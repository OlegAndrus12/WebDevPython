# Module 07 — Agenda

- **cnn-website** (`cnn-website/`) — the news reader ported to FastAPI: SQLAlchemy 2.0 (asyncio) + Alembic + Postgres
  - FastAPI essentials: `APIRouter`s, `Depends`-based DB session, Pydantic response models, automatic `/docs`
  - Async end to end — `async def` routes, `AsyncSession`, `httpx.AsyncClient`, async Alembic `env.py`
  - Eager loading required: a missed `joinedload` now crashes (`MissingGreenlet`) instead of costing an extra query
  - Settings via `pydantic-settings`, `SecretStr` for the NewsAPI key and DB password
  - Postgres in Docker Compose, plus a bare-bones `/api/auth/register` (passlib/bcrypt hashing)
- **pydantic_ex** (`pydantic_ex/`) — Pydantic models: validators, alias generators, strict vs. lax coercion
