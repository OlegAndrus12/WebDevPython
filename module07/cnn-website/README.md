# cnn-website/ — the async port

The same reader as [../../module07/cnn-website/](../../module07/cnn-website/),
taken async from the route handler all the way down to the driver: `async def`
endpoints, `AsyncSession`, `httpx.AsyncClient`, and an async Alembic `env.py`.

```bash
cp .env.example .env                 # then put your NewsAPI key in it

docker compose up --build --wait     # -> http://localhost:8003/docs

# ...or run uvicorn on the host against the containerised database:
docker compose up -d --wait db
uv run alembic upgrade head
uv run uvicorn news:app --reload --port 8004   # -> http://localhost:8004/docs
```

Ports are **8003** and **5435** (module05 has 8000/5433, module07 8001/5434), so
all three stacks can run at once.

---

## Does it actually go faster?

Measured on this machine, against the container, 48 requests to
`/api/articles?per_page=20`:

| | 48 sequential | 48 concurrent | speedup |
| --- | --- | --- | --- |
| module08 (async) | 293 ms | 320 ms | **0.9×** |
| module07 (sync, threadpool) | 280 ms | 380 ms | 0.7× |

**No gain.** Both are marginally *slower* under concurrency. That is the honest
answer for this workload: the queries return six rows in well under a
millisecond, so there is no I/O latency to overlap, and all concurrency adds is
scheduling and pool contention.

The async plumbing is real, though — it just needs something to wait on. Eight
concurrent `SELECT pg_sleep(0.3)` through eight `AsyncSession`s:

```
sequential : 2.44s
gathered   : 0.37s      6.5x
```

So the rewrite buys what async always buys: the ability to have many requests
in flight while each waits on something slow. It does not make a fast query
faster. On this app the one genuinely slow call is NewsAPI on `/` — which is
also the one route you are rate-limited to ~100 uses a day.

Worth knowing before assuming sync was the bottleneck: FastAPI already runs
`def` routes in a threadpool, so module07 was never serial either. The
difference is the ceiling — a thread per in-flight request (default limit 40)
versus a coroutine — and that ceiling is not what hurts at this scale.

## What the port changed

| concern | module07 (sync) | here (async) |
| --- | --- | --- |
| engine | `create_engine` | `create_async_engine` — **same URL**, psycopg 3 is both |
| sessions | `sessionmaker` | `async_sessionmaker`, `AsyncSession` |
| repository | `session.scalar(...)` | `await session.scalar(...)` — 9 call sites |
| routes | `def` | `async def` |
| NewsAPI client | `httpx.Client` | `httpx.AsyncClient`, `await client.get(...)` |
| shutdown | `client.close()` | `await client.aclose()` **and** `await engine.dispose()` |
| Alembic | `engine_from_config` | `async_engine_from_config` + `connection.run_sync` |
| dependency | `def get_db()` | `async def get_db()` |

Unchanged: [models.py](news/models.py), [schemas.py](news/schemas.py),
[utils.py](news/utils.py), the templates, and every file in
`migrations/versions/`.

### Lazy loading stops being a performance bug and becomes a crash

This is the change that matters most in review. In module07, a missing
`joinedload` cost you an extra query per row — the classic N+1, invisible until
you profile. Under `AsyncSession` the same code raises:

```python
row = await session.scalar(select(Article).limit(1))   # no joinedload
row.source.name
# sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
# can't call await_only() here.
```

Attribute access is sync by definition — there is no `await` on
`row.source.name` — so SQLAlchemy cannot go to the database for it. Every
relationship a caller will touch has to be loaded up front, which is why
[repository.py](news/repository.py) states `joinedload` on both read paths and
why `save_article` assigns `article.source = source` on both branches.

The corollary is `expire_on_commit=False` in [db.py](news/db.py). Leave it on
and `commit()` marks every attribute stale, so the next read is a lazy load —
i.e. a `MissingGreenlet`, not a slow query.

### Alembic: async connection, sync migrations

`op.create_table(...)` is ordinary sync code and stays that way. Only getting
the connection is async:

```python
async with connectable.connect() as connection:
    await connection.run_sync(do_run_migrations)
```

`run_sync` hands the migration a sync-style connection driven by the async one
underneath, which is why the two revisions in `migrations/versions/` are
byte-identical to module07's. `asyncio.run()` sits at the bottom of
[env.py](migrations/env.py) because Alembic's command layer is sync and has to
start the loop itself.

### The lifespan now has real work to do

```python
await news_api.close()      # aclose() on the httpx client
await engine.dispose()      # the connection pool
```

Both are awaitable, and both must be closed on the loop that opened them —
which is precisely why an async app needs a lifespan hook rather than an
`atexit` handler.

### `save_articles` is a serial loop, not `asyncio.gather`

```python
for payload in payloads:
    source = await self.save_source(...)
    articles.append(await self.save_article(payload, source))
```

One session owns one connection, and an `AsyncSession` is not safe to drive from
two tasks at once. Gathering these would interleave statements on the same
connection and corrupt the transaction. Concurrency across *requests* is free;
concurrency *inside* one session is not available.

---

## Routes

| route | what it does |
| --- | --- |
| `GET /` | headlines, or `?q=` search — the one route that calls NewsAPI |
| `GET /article/{id}` | detail page, rendered from the database |
| `GET /api/articles` | stored articles as JSON: `?q=`, `?page=`, `?per_page=` |
| `GET /api/articles/{id}` | one stored article |
| `GET /api/stats` | how many articles each source accounts for |
| `GET /healthz` | `SELECT 1`, used by the Compose healthcheck |
| `GET /docs`, `/redoc`, `/openapi.json` | generated |

Behaviour is identical to module07, including the 422s from
`Query(ge=…, le=…)` and the JSON-shaped 404 on the HTML pages. See
[module07's README](../../module07/cnn-website/README.md#differences-worth-knowing-before-you-rely-on-them)
for that list — none of it changed.

## Layout

| file | what it holds |
| --- | --- |
| [news/main.py](news/main.py) | the app, static mount, lifespan, `/healthz` |
| [news/db.py](news/db.py) | async engine, `async_sessionmaker`, `get_session()`, `get_db()` |
| [news/repository.py](news/repository.py) | every query, all `async def` |
| [news/routers/api.py](news/routers/api.py) | the JSON API |
| [news/routers/pages.py](news/routers/pages.py) | the HTML pages and the Jinja environment |
| [news/schemas.py](news/schemas.py) | Pydantic response models |
| [news/dependencies.py](news/dependencies.py) | `SessionDep` — now `Annotated[AsyncSession, ...]` |
| [news/news_api.py](news/news_api.py) | the async NewsAPI client |
| [news/models.py](news/models.py), [news/utils.py](news/utils.py) | unchanged from module07 |
| [migrations/env.py](migrations/env.py) | the async Alembic entry point |

```bash
grep -rn "select(" news/      # still only ever repository.py
```

## Configuration

| variable | default | what it is |
| --- | --- | --- |
| `NEWS_API_KEY` | *required* | no default — the app refuses to start without it |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `admin` / `admin` / `cnn` | |
| `DB_HOST` | `localhost` | Compose overrides this to `db` for the api container |
| `DB_PORT` | `5435` | host-side; inside Compose the api container uses `5432` |
| `DEFAULT_SOURCE` | `cnn` | which source the front page shows |
| `PAGE_SIZE` | `12` | how many articles to request **from NewsAPI** |

The URL is still `postgresql+psycopg://…`. psycopg 3 is a sync *and* async
driver, so `create_async_engine` takes it unchanged — moving to asyncpg would
mean editing the URL too. `sqlalchemy[asyncio]` in
[pyproject.toml](pyproject.toml) is what pulls in **greenlet**; without it the
async engine will not build at all.

---

# Docker

| service | what it is | where |
| --- | --- | --- |
| `api` | the async app under uvicorn | http://localhost:8003 |
| `db` | Postgres 15 | `localhost:5435` (`5432` inside the network) |
| `pgadmin` | optional, behind a profile | `docker compose --profile tools up -d` → :5053 |

**`name: cnn8` in [docker-compose.yaml](docker-compose.yaml) is load-bearing.**
Compose derives the project name from the directory, and module05 *and* module07
both have a directory called `cnn-website` — without an explicit name a
`docker compose up` here would adopt one of their stacks. Containers are
`cnn8_api`, `cnn8_postgres`, `cnn8_pgadmin`.

```bash
docker compose logs -f api                     # follow the app log
docker compose exec api sh                     # a shell in the app container
docker compose exec db psql -U admin -d cnn    # a psql prompt
docker compose exec api alembic current        # which revision it is on
docker compose down                            # stop; keeps the volume
docker compose down -v                         # stop **and delete the database**
```

## Seeding without spending NewsAPI requests

The repository is async now, so the snippet needs a loop to run in:

```bash
docker compose exec -T api python <<'EOF'
import asyncio
from news.db import get_session, engine
from news.repository import Repository

payload = {
    "url": "https://example.com/written-by-hand",   # the natural key
    "title": "Written by hand, not by NewsAPI",
    "description": "Inserted from a python shell inside the container.",
    "content": "The whole body, with no truncation marker in sight.",
    "urlToImage": None,
    "author": "You",
    "publishedAt": "2026-08-27T12:00:00Z",
    "source": {"id": "manual", "name": "Manual"},
}

async def main():
    async with get_session() as session:
        repo = Repository(session)
        article = await repo.save_article(payload, await repo.save_source(payload["source"]))
        print("created id:", article.id)
    await engine.dispose()

asyncio.run(main())
EOF
```

`await engine.dispose()` at the end, or asyncio complains about a connection
pool torn down at interpreter exit.

## If you copied this folder from module07

`.venv/bin/*` console scripts carry **absolute** shebangs, so a copied venv
still points at the interpreter it was created for — `alembic` will die with
`ModuleNotFoundError` naming a package that is only in the other project's
environment. `rm -rf .venv && uv sync` fixes it.

## Versions

fastapi 0.141 · starlette 1.6 · uvicorn 0.52 · sqlalchemy 2.0.52 (asyncio) ·
greenlet 3.5 · psycopg 3 · httpx 0.28 · pydantic 2.13 · postgres 15 · python 3.13
