# module07 — FastAPI basics, async end to end

The same news reader as a FastAPI application, async from the route handler down
to the database driver. Same two tables and six routes as module06, so the only
variable is the framework — plus generated API docs at `/docs`.

```
cnn-website/
  news/
    main.py           the FastAPI app, static mount, /healthz
    routers/
      api.py          the JSON API
      pages.py        the HTML pages and the Jinja environment
    dependencies.py   SessionDep — the injected AsyncSession
    db.py             async engine, async_sessionmaker, get_db()
    repository.py     every query, all `async def`
    models.py         Source and Article
    schemas.py        Pydantic response models
    news_api.py       the NewsAPI client (httpx.AsyncClient)
    settings.py       pydantic-settings, validated at import
    templates/        base, index, article, _card
  migrations/         Alembic with an async env.py + two revisions
  docker-compose.yaml api + db + pgAdmin
```

**Stack:** FastAPI · uvicorn · SQLAlchemy 2.0 (asyncio) + greenlet · Alembic ·
psycopg 3 · httpx · pydantic-settings · Postgres 15 · Python 3.13 · uv

---

## Running it

```bash
cd module07/cnn-website
cp .env.example .env          # then put your key in NEWS_API_KEY
docker compose up --build --wait
```

Migrations run on container start (`uv sync && alembic upgrade head &&
uvicorn --reload`).

| service | container | URL | |
| --- | --- | --- | --- |
| `api` | `cnn07_api` | <http://localhost:8007> | the reader; `/docs`, `/redoc`, `/openapi.json` |
| `db` | `cnn07_postgres` | `localhost:5407` | Postgres 15 (`5432` in-network) |
| `pgadmin` | `cnn07_pgadmin` | <http://localhost:5107> | `admin@gmail.com` / `admin`, `db` preloaded |

Every published port ends in **07**, so modules 06–11 can all run at once.
`name: cnn07` in `docker-compose.yaml` keeps Compose from adopting a sibling
`cnn-website` stack.

<http://localhost:8007/docs> is the page worth opening: every endpoint with its
schema, and **Try it out** fires a real request from the browser.

### Or run uvicorn on the host

```bash
docker compose up -d --wait db        # just Postgres, on localhost:5407
uv run alembic upgrade head
uv run uvicorn news:app --reload      # -> http://localhost:8000/docs
```

### Everyday commands

```bash
docker compose logs -f api                      # follow the app log
docker compose exec db psql -U admin -d cnn     # a psql prompt
docker compose exec api alembic current         # which revision it is on
docker compose down -v                          # stop and delete the database
```

---

## What this module covers

**The app and its routers.** `main.py` builds one `FastAPI()` instance and
composes it from two `APIRouter`s via `include_router` — `routers/api.py` owns
the JSON API, `routers/pages.py` owns the HTML. The API router is included
first, so `/docs` lists it above the pages.

**Dependency injection.** `dependencies.py` declares
`SessionDep = Annotated[AsyncSession, Depends(get_db)]` once; any route that
needs the database adds `session: SessionDep` to its signature. `get_db()` is an
async generator dependency — code before `yield` runs before the route, code
after runs as teardown, on the same event loop that ran the route.

**Validation and responses for free.** Query parameters are plain type hints:
`page: int = Query(1, ge=1)` rejects `?page=0` with a `422` before the route body
runs, and the constraint appears in the generated schema. `schemas.py` declares
Pydantic models with `from_attributes=True`, so a route can `return` an ORM
object and only the declared fields are serialised. `/docs`, `/redoc` and
`/openapi.json` are built from those two things and need no code at all. This is
exactly the `int_arg()` / `article_json()` work module06 wrote by hand.

**`async def` all the way down.** Routes, the session (`AsyncSession`) and the
NewsAPI client (`httpx.AsyncClient`) are all async, so one worker holds many
requests in flight while each waits. Worth knowing: FastAPI already runs plain
`def` routes in a threadpool, so a sync app is not serial either — the
difference is the ceiling, a thread per in-flight request versus a coroutine.

**Async does not make a fast query faster.** These queries return a handful of
rows in well under a millisecond, so there is no latency to overlap and
concurrency only adds scheduling and pool contention. What the plumbing buys is
waiting on many slow things at once:

```bash
docker compose up -d --wait db
uv run python - <<'EOF'
import asyncio, time
from sqlalchemy import text
from news.db import SessionLocal, engine

async def sleeper():
    async with SessionLocal() as s:
        await s.execute(text("SELECT pg_sleep(0.3)"))

async def main():
    t = time.perf_counter()
    for _ in range(8): await sleeper()
    seq = time.perf_counter() - t

    t = time.perf_counter()
    await asyncio.gather(*(sleeper() for _ in range(8)))
    gat = time.perf_counter() - t

    print(f"sequential : {seq:.2f}s")
    print(f"gathered   : {gat:.2f}s      {seq/gat:.1f}x")
    await engine.dispose()

asyncio.run(main())
EOF
# sequential : 2.51s
# gathered   : 0.37s      6.8x
```

Run the same comparison against `/api/articles` and the gain disappears — there
is nothing to wait on.

**Lazy loading stops being a performance bug and becomes a crash.** The change
that matters most in review. Attribute access is sync by definition — there is
no `await` on `row.source.name` — so an `AsyncSession` cannot go to the database
for it:

```python
row = await session.scalar(select(Article).limit(1))   # no joinedload
row.source.name
# sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called
```

Every relationship a caller will touch has to be eager-loaded, which is why
`repository.py` states `joinedload(Article.source)` on both read paths. The
corollary is `expire_on_commit=False` in `db.py`: leave it on and `commit()`
marks every attribute stale, so the next read is a lazy load — an exception, not
a slow query.

**One session is not concurrent.** `save_articles()` is a serial `for` loop, not
an `asyncio.gather`. One session owns one connection, and gathering would
interleave statements on it and corrupt the transaction. Concurrency across
*requests* is free; concurrency *inside* one session is not on offer.

**Alembic: async connection, sync migrations.** `op.create_table(...)` stays
ordinary sync code. Only getting the connection is async:

```python
async with connectable.connect() as connection:
    await connection.run_sync(do_run_migrations)
```

`asyncio.run()` sits at the bottom of `env.py` because Alembic's command layer is
sync and has to start the loop itself.

**The driver URL does not change.** psycopg 3 is both a sync and an async driver,
so `postgresql+psycopg://…` works under `create_async_engine` unchanged.
`sqlalchemy[asyncio]` is what pulls in **greenlet**; without it the async engine
will not build at all.

**The repository pattern survives the port.** Every `select()` still lives in
`repository.py` — `grep -rn "select(" news/` only ever hits that one file.

---

## Endpoints

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/` | headlines, or `?q=` search — the only route that calls NewsAPI |
| `GET` | `/article/{article_id}` | detail page, rendered from the database |
| `GET` | `/api/articles` | stored articles as JSON: `?q=`, `?page=`, `?per_page=` |
| `GET` | `/api/articles/{article_id}` | one stored article as JSON |
| `GET` | `/api/stats` | how many stored articles each source accounts for |
| `GET` | `/healthz` | `SELECT 1`; `503` when the database is unreachable |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | generated, no code |

- `?q=` on `/` searches **NewsAPI**; `?q=` on `/api/articles` searches **what is
  already stored**.
- The HTML pages are `include_in_schema=False`, so `/docs` shows the API only.
- `page` / `per_page` are validated by `Query(ge=…, le=…)` and rejected with a
  structured `422`, not a hand-written `400`.

```bash
B=localhost:8007
curl -s $B/healthz                                  # {"status":"ok","db":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' $B/        # 200 -- fills the database
curl -s $B/api/stats
curl -s "$B/api/articles?per_page=2" | python3 -m json.tool

curl -s -w ' [%{http_code}]\n' "$B/api/articles?page=0"
# {"detail":[{"type":"greater_than_equal","loc":["query","page"], ...}]} [422]
curl -s -w ' [%{http_code}]\n' $B/api/articles/99999
# {"detail":"article not found"} [404]

# the generated schema -- no route table maintained by hand
curl -s $B/openapi.json | python3 -c "
import json,sys
for path, ops in sorted(json.load(sys.stdin)['paths'].items()):
    for method in sorted(ops): print(method.upper(), path)"
```

---

## Configuration

Environment first, then `.env` — which is how Compose overrides the database host
without editing a file.

| variable | default | what it is |
| --- | --- | --- |
| `NEWS_API_KEY` | *required* | no default; the app refuses to start without it |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `admin` / `admin` / `cnn` | also fed to Postgres by Compose |
| `DB_HOST` / `DB_PORT` | `localhost` / `5407` | the api container overrides both to `db:5432` |
| `DEFAULT_SOURCE` | `cnn` | which NewsAPI source the front page shows |
| `PAGE_SIZE` | `12` | how many articles to request **from NewsAPI** |

---

## The database

```
sources    id, slug (unique), name
articles   id, source_id -> sources.id (cascade), url (unique), title,
           description, content, image_url, author, published_at
```

Two revisions, `759161cd8fb3` → `b773fddbe615` (head).

```bash
uv run alembic current            # where the database is
uv run alembic history            # the chain
uv run alembic upgrade head
uv run alembic downgrade -1

uv run alembic revision --autogenerate -m "what changed"   # then READ the file
```

---

## Troubleshooting

**`MissingGreenlet: greenlet_spawn has not been called`** — a lazy load on an
async session. Add `joinedload(...)` to the query that produced the object. This
is the error this module hands you most often.

**`ValidationError: news_api_key Field required`** — no `.env`, or no key in it.

**`ModuleNotFoundError` for a package that is clearly installed** — a copied
`.venv`; console scripts carry absolute shebangs. `rm -rf .venv && uv sync`.

📋 Topic list: **[AGENDA.md](AGENDA.md)**
