# module07 — FastAPI + SQLAlchemy (async) + Alembic + Postgres

```
cnn-website/   the news reader on FastAPI — routers, async SQLAlchemy, Alembic, Postgres in Docker Compose
pydantic_ex/   Pydantic models — validators, alias generators, strict vs. lax coercion
```

Same news reader as [module06](../module06/cnn-website/) (Flask), rebuilt on FastAPI, async
end to end. Lesson plan — [AGENDA.md](AGENDA.md).

```bash
cd cnn-website
cp .env.example .env                 # put your NewsAPI key in it

docker compose up --build --wait     # -> http://localhost:8004/docs

# ...or run uvicorn on the host against the containerised database:
docker compose up -d --wait db
uv run alembic upgrade head
uv run uvicorn news:app --reload     # -> http://localhost:8000/docs
```

| | |
| --- | --- |
| [cnn-website/](cnn-website/) | the app: routers, async repository, Pydantic schemas, Alembic migrations |
| [cnn-website/README.md](cnn-website/README.md) | deep dive: the sync→async port, benchmarks, routes, configuration |
| [cnn-website/pyproject.toml](cnn-website/pyproject.toml) | `uv sync` installs fastapi, sqlalchemy[asyncio], alembic, psycopg, pydantic-settings |
| [pydantic_ex/](pydantic_ex/) | Pydantic models: validators, alias generators, strict vs. lax coercion |

## FastAPI essentials, as seen here

FastAPI's core ideas, each pointed at the file that shows it:

- **The app and its routers** — [`main.py`](cnn-website/news/main.py) builds one
  `FastAPI()` instance, mounts `/static`, and composes the app from three
  `APIRouter`s ([`routers/api.py`](cnn-website/news/routers/api.py),
  [`routers/pages.py`](cnn-website/news/routers/pages.py),
  [`routers/auth.py`](cnn-website/news/routers/auth.py)) via `include_router`
  — each router owns one concern instead of one file owning every route.

- **Dependency injection** — [`dependencies.py`](cnn-website/news/dependencies.py)
  defines `SessionDep = Annotated[AsyncSession, Depends(get_db)]` once;
  every route that needs the database just adds `session: SessionDep` to its
  signature. `get_db()` in [`db.py`](cnn-website/news/db.py) is an async
  generator dependency — code before `yield` runs before the route, code
  after runs as teardown (commit or rollback), on the same event loop that
  ran the route.

- **Request validation for free** — path and query parameters are plain
  Python type hints. `page: int = Query(1, ge=1)` in
  [`routers/api.py`](cnn-website/news/routers/api.py) rejects
  `?page=0` with a 422 before the route body ever runs; no `if` statement
  wrote that check.

- **Response models** — [`schemas.py`](cnn-website/news/schemas.py) declares
  Pydantic models with `from_attributes=True`, so a route can `return` an
  ORM object directly and FastAPI serialises only the declared fields. The
  same models generate the OpenAPI schema, which is what `/docs` renders.

- **Automatic docs** — `/docs` (Swagger UI), `/redoc`, and `/openapi.json`
  need no extra code; they're built from the routers, the `response_model`s,
  and the `summary`/`tags` kwargs on each route.

- **Settings as a validated object** —
  [`settings.py`](cnn-website/news/settings.py) uses `pydantic-settings` to
  read `.env` once at import time; a missing `NEWS_API_KEY` fails at
  startup, not on the first request, and `SecretStr` keeps it out of tracebacks
  and `repr()`.

- **`async def` all the way down** — routes, the SQLAlchemy session
  (`AsyncSession`), and the NewsAPI client (`httpx.AsyncClient`) are all
  async, so one worker can hold many requests in flight while they wait on
  the database or NewsAPI. What that costs and buys — an eager-loading
  requirement, and a benchmark that's honest about when it helps — is in
  [cnn-website/README.md](cnn-website/README.md#does-it-actually-go-faster).

## Running it

| | dev (host) | Docker Compose |
| --- | --- | --- |
| app | `uv run uvicorn news:app --reload` → :8000 | :8004 → container :8000 |
| database | `docker compose up -d --wait db` | same container, :5435 → :5432 |
| migrations | `uv run alembic upgrade head` | run automatically on container start |

`docker compose exec api sh` gets a shell in the app container;
`docker compose logs -f api` follows the app log. Full command reference and
configuration table — [cnn-website/README.md](cnn-website/README.md).
