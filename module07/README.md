# module07 — FastAPI basics, async end to end

The same news reader as a FastAPI application, async from the route handler
down to the database driver. Each visit to the front page asks
[newsapi.org](https://newsapi.org/) for stories, stores them in Postgres, and
renders them; every other route reads the database only. Two tables, six
routes, and generated API docs at `/docs`.

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
    utils.py          pure helpers: domain, parse_published, slugify
    templates/        base, index, article, _card
    static/styles.css
  migrations/         Alembic with an async env.py + two revisions
  docker-compose.yaml api + db + pgAdmin
```

**Stack:** FastAPI · uvicorn · SQLAlchemy 2.0 (asyncio) + greenlet ·
Alembic · psycopg 3 · httpx · pydantic · pydantic-settings · Postgres 15 ·
Python 3.13 · uv

---

## Running it

You need a free NewsAPI key from <https://newsapi.org/register>. The Developer
plan allows 100 requests a day, and the front page spends one per load.

```bash
cd cnn-website
cp .env.example .env          # then put your key in NEWS_API_KEY
```

### Everything in Docker

```bash
docker compose up --build --wait
```

`--wait` blocks until every healthcheck passes and exits non-zero if one does
not, so it is safe to chain a `curl` after it. Migrations run automatically on
container start — the `command:` in `docker-compose.yaml` is
`uv sync && alembic upgrade head && uvicorn --reload`.

### Open it in a browser

| | |
| --- | --- |
| the reader | <http://localhost:8080> |
| interactive API docs (Swagger UI) | <http://localhost:8080/docs> |
| the same schema, ReDoc | <http://localhost:8080/redoc> |
| pgAdmin | <http://localhost:5050> — `admin@gmail.com` / `admin` |

<http://localhost:8080> lands on the headlines; the navbar's topic links and
search box re-query NewsAPI, and a card's title opens the detail page, which is
rendered from the database. <http://localhost:8080/docs> is the more
interesting page here — every endpoint is listed with its schema, and **Try it
out** fires a real request from the browser. pgAdmin takes about 25 seconds to
finish booting and has the `db` connection preloaded, so there is no
"Register → Server…" dialog to fill in.

### App on the host, database in Docker

```bash
docker compose up -d --wait db        # just Postgres, on localhost:5433
uv run alembic upgrade head
uv run uvicorn news:app --reload      # -> http://localhost:8000/docs
```

The host app reads `DB_HOST=localhost` / `DB_PORT=5433` from `.env`; the
container overrides both to `db:5432`, because inside the Compose network the
database is a service name rather than a published port.

### Ports and containers

| service | container | host port | what it is |
| --- | --- | --- | --- |
| `api` | `cnn07_api` | 8080 | the app under uvicorn (`8000` inside) |
| `db` | `cnn07_postgres` | 5433 | Postgres 15 (`5432` inside the network) |
| `pgadmin` | `cnn07_pgadmin` | 5050 | <http://localhost:5050> |

pgAdmin logs in with `admin@gmail.com` / `admin`; the `db` connection is
preloaded from `pgadmin/servers.json`, so there is no "Register → Server…"
dialog to fill in.

`name: cnn07` at the top of `docker-compose.yaml` is load-bearing. Compose
otherwise derives the project name from the directory, and more than one
project here is called `cnn-website` — without an explicit name a
`docker compose up` could adopt another stack's containers and volumes.

### Everyday commands

```bash
docker compose logs -f api                 # follow the app log
docker compose exec api sh                 # a shell in the app container
docker compose exec db psql -U admin -d cnn    # a psql prompt
docker compose exec api alembic current    # which revision it is on
docker compose down                        # stop; keeps the database volume
docker compose down -v                     # stop and delete the database
```

---

## What this module covers

**The app and its routers.** `main.py` builds one `FastAPI()` instance, mounts
`/static`, and composes the app from two `APIRouter`s via `include_router` —
`routers/api.py` owns the JSON API, `routers/pages.py` owns the HTML. Each
router owns one concern instead of one file owning every route. The API router
is included first, so `/docs` lists it above the pages.

**Dependency injection.** `dependencies.py` declares
`SessionDep = Annotated[AsyncSession, Depends(get_db)]` once; every route that
needs the database just adds `session: SessionDep` to its signature. `get_db()`
in `db.py` is an async generator dependency — code before `yield` runs before
the route, code after runs as teardown (commit or rollback), on the same event
loop that ran the route.

**Request validation for free.** Path and query parameters are plain Python
type hints. `page: int = Query(1, ge=1)` rejects `?page=0` with a `422` before
the route body runs; no `if` statement wrote that check, and the constraint
shows up in the generated schema.

**Response models.** `schemas.py` declares Pydantic models with
`from_attributes=True`, so a route can `return` an ORM object directly and
FastAPI serialises only the declared fields. `published_at` comes out as ISO
8601 because it is typed `datetime`. The same models generate the OpenAPI
schema.

**Automatic docs.** `/docs` (Swagger UI), `/redoc` and `/openapi.json` need no
code. They are built from the routers, the `response_model`s, and the
`summary`/`tags` kwargs on each route. `/docs` is also the easiest way to fire
a request by hand.

**`async def` all the way down.** Routes, the SQLAlchemy session
(`AsyncSession`), and the NewsAPI client (`httpx.AsyncClient`) are all async,
so one worker can hold many requests in flight while each waits on the database
or on NewsAPI. Worth knowing: FastAPI already runs plain `def` routes in a
threadpool, so a sync app is not serial either. The difference is the ceiling —
a thread per in-flight request versus a coroutine.

**Async does not make a fast query faster.** These queries return a handful of
rows in well under a millisecond, so there is no I/O latency to overlap and
concurrency only adds scheduling and pool contention. What the plumbing buys is
the ability to wait on many slow things at once. Eight
`SELECT pg_sleep(0.3)` through eight sessions is the demo worth running:

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
    for _ in range(8):
        await sleeper()
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

Eight sleeps of 0.3 s cost 2.5 s in a row and 0.37 s overlapped, because the
waiting happens in parallel while the work does not. Run the same comparison
against `/api/articles` and the gain disappears — there is nothing to wait on.

**Lazy loading stops being a performance bug and becomes a crash.** This is the
change that matters most in review. Attribute access is sync by definition —
there is no `await` on `row.source.name` — so an `AsyncSession` cannot go to
the database for it:

```python
row = await session.scalar(select(Article).limit(1))   # no joinedload
row.source.name
# sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called
```

Every relationship a caller will touch has to be loaded up front, which is why
`repository.py` states `joinedload(Article.source)` on both read paths and why
`save_article()` assigns `article.source = source` on both branches. The
corollary is `expire_on_commit=False` in `db.py`: leave it on and `commit()`
marks every attribute stale, so the next read is a lazy load — an exception,
not a slow query.

**One session is not concurrent.** `save_articles()` is a serial `for` loop,
not an `asyncio.gather`. One session owns one connection, and an `AsyncSession`
is not safe to drive from two tasks at once — gathering would interleave
statements on the same connection and corrupt the transaction. Concurrency
across *requests* is free; concurrency *inside* one session is not on offer.

**Alembic: async connection, sync migrations.** `op.create_table(...)` is
ordinary sync code and stays that way. Only getting the connection is async:

```python
async with connectable.connect() as connection:
    await connection.run_sync(do_run_migrations)
```

`run_sync` hands the migration a sync-style connection driven by the async one
underneath, and `asyncio.run()` sits at the bottom of `env.py` because
Alembic's command layer is sync and has to start the loop itself.

**The driver URL does not change.** psycopg 3 is both a sync and an async
driver, so `postgresql+psycopg://…` works under `create_async_engine`
unchanged. Moving to asyncpg would mean editing the URL too.
`sqlalchemy[asyncio]` in `pyproject.toml` is what pulls in **greenlet**;
without it the async engine will not build at all.

**Settings as a validated object.** `settings.py` uses `pydantic-settings` to
read the environment and then `.env`, once at import. A missing
`NEWS_API_KEY` fails at startup rather than on the first request that needs it,
and `SecretStr` keeps the token out of tracebacks and `repr()`. `database_url`
is a `@computed_field` assembled from the parts, with the password run through
`quote_plus` so an `@` or `/` in it cannot cut the URL in the wrong place.

**The repository pattern survives the port.** Every `select()` still lives in
`repository.py`; the routers contain no SQL.

```bash
grep -rn "select(" news/     # only ever repository.py
```

---

## Endpoints

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/` | headlines, or `?q=` search — the only route that calls NewsAPI |
| `GET` | `/article/{article_id}` | detail page, rendered from the database |
| `GET` | `/api/articles` | stored articles as JSON: `?q=`, `?page=`, `?per_page=` |
| `GET` | `/api/articles/{article_id}` | one stored article as JSON |
| `GET` | `/api/stats` | how many stored articles each source accounts for |
| `GET` | `/healthz` | `SELECT 1`, used by the Compose healthcheck |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | generated, no code |

Notes worth knowing before you rely on them:

- `/` is the only route that spends a NewsAPI request. Everything else reads
  Postgres, so the JSON API works fine with your daily quota exhausted.
- `?q=` on `/` searches **NewsAPI**; `?q=` on `/api/articles` searches **what
  is already stored**. A story NewsAPI has never handed you is not in the
  second one.
- The HTML pages are excluded from the schema (`include_in_schema=False`), so
  `/docs` shows the API only.
- `page` and `per_page` are validated by `Query(ge=…, le=…)` and rejected with
  a `422` carrying a structured body, not a hand-written `400`.
- `per_page` is capped at 100.

---

## Testing it with curl

Against the Compose stack on port 8080. If you are running uvicorn on the host,
use `localhost:8000` instead.

```bash
B=localhost:8080
```

**Is it up, and can it reach the database?**

```bash
curl -s $B/healthz
# {"status":"ok","db":"ok"}
```

The route also sets a `503` status when the database is unreachable, which is
what the Compose healthcheck reads.

**Load the front page once, to put stories in the database.** This is the call
that spends a NewsAPI request.

```bash
curl -s -o /dev/null -w '%{http_code}\n' $B/
# 200
```

**What is stored, and from which sources?**

```bash
curl -s $B/api/stats
# {"sources":[{"slug":"cnn","name":"CNN","articles":10}],"total_articles":10,"total_sources":1}
```

**One page of articles.**

```bash
curl -s "$B/api/articles?per_page=2" | python3 -m json.tool | head -20
# {
#     "articles": [
#         {
#             "id": 1,
#             "title": "CNN Explains | CNN",
#             "description": "CNN Explains delivers clear, visually rich ...",
#             "content": "Electric Bills\r\n Supply shocks, grid repair ...",
#             "url": "https://www.cnn.com/...",
#             "image_url": "https://media.cnn.com/...",
#             "author": null,
#             "published_at": "2026-09-08T13:39:10+00:00",
#             "source": {"slug": "cnn", "name": "CNN"}
#         },
# ...
```

**Search what is stored** (not NewsAPI):

```bash
curl -s "$B/api/articles?q=energy&per_page=3" | python3 -c \
  'import json,sys; d=json.load(sys.stdin); print(d["total"], "matches")'
```

**One article by id.**

```bash
curl -s $B/api/articles/1 | python3 -m json.tool | head -5
curl -s -w ' [%{http_code}]\n' $B/api/articles/99999
# {"detail":"article not found"} [404]
```

**The validation you did not write.** Note the `422` and the structured body —
this is Pydantic reporting, not an `if` in the route.

```bash
curl -s -w ' [%{http_code}]\n' "$B/api/articles?page=0"
# {"detail":[{"type":"greater_than_equal","loc":["query","page"], ... }]} [422]

curl -s -o /dev/null -w '%{http_code}\n' "$B/api/articles?per_page=500"
# 422
```

**The generated schema.** Every path the app serves, with no route table to
maintain by hand:

```bash
curl -s $B/openapi.json | python3 -c "
import json,sys
for path, ops in sorted(json.load(sys.stdin)['paths'].items()):
    for method in sorted(ops):
        print(method.upper(), path)"
# GET /api/articles
# GET /api/articles/{article_id}
# GET /api/stats
# GET /healthz
```

**The HTML pages.**

```bash
curl -s -o /dev/null -w '%{http_code}\n' $B/                 # 200
curl -s -o /dev/null -w '%{http_code}\n' $B/article/1        # 200
curl -s -o /dev/null -w '%{http_code}\n' "$B/?q=ukraine"     # 200, spends a request
curl -s -o /dev/null -w '%{http_code}\n' $B/article/99999    # 404
```

---

## Configuration

Read from the environment first, then `.env`. Environment wins, which is how
Compose overrides the database host without editing a file.

| variable | default | what it is |
| --- | --- | --- |
| `NEWS_API_KEY` | *required* | no default — the app refuses to start without it |
| `DB_USER` | `admin` | also fed to Postgres itself by Compose |
| `DB_PASSWORD` | `admin` | a `SecretStr`; URL-escaped into the connection string |
| `DB_NAME` | `cnn` | |
| `DB_HOST` | `localhost` | Compose overrides this to `db` for the api container |
| `DB_PORT` | `5433` | host-side; inside Compose the api container uses `5432` |
| `DEFAULT_SOURCE` | `cnn` | which NewsAPI source the front page shows |
| `PAGE_SIZE` | `12` | how many articles to request **from NewsAPI** |

Both `.env` and `.env.example` are committed in this repo, so keep anything
genuinely secret out of both — the values checked in are throwaway.

---

## The database

Two tables, both created by migrations. There is deliberately no `create_all()`
anywhere.

```
sources    id, slug (unique), name
articles   id, source_id -> sources.id (cascade), url (unique), title,
           description, content, image_url, author, published_at
```

```bash
docker compose exec db psql -U admin -d cnn -c '\dt'
docker compose exec db psql -U admin -d cnn -c '\d articles'
```

Two revisions, `759161cd8fb3` → `b773fddbe615`, and `b773fddbe615` is head.

```bash
uv run alembic current            # where the database is
uv run alembic history            # the chain
uv run alembic upgrade head       # apply everything
uv run alembic downgrade -1       # step back one
```

After changing `models.py`:

```bash
uv run alembic revision --autogenerate -m "what changed"
# then READ the generated file before applying it
uv run alembic upgrade head
```

A naming convention on `Base.metadata` gives constraints predictable names,
so autogenerated downgrades can name what they drop instead of emitting
`drop_constraint(None, ...)`.

### Adding an article without spending a NewsAPI request

The repository is async, so the snippet needs a loop to run in:

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

---

## Troubleshooting

**`sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`.** A
lazy load on an async session — some code touched a relationship that was not
eager-loaded. Add `joinedload(...)` to the query that produced the object, or
assign the related object explicitly. This is the one error this module will
hand you most often.

**`ModuleNotFoundError` naming a package that is clearly installed**, usually
from `alembic` or `uvicorn`. A copied `.venv` is the cause: console scripts in
`.venv/bin/` carry **absolute** shebangs, so a venv copied from another project
still points at that project's interpreter.

```bash
head -1 .venv/bin/alembic     # is this path in *this* directory?
rm -rf .venv && uv sync       # the fix
```

**`ValidationError: news_api_key Field required` at startup.** There is no
`.env`, or it has no key in it. `cp .env.example .env` and fill it in.

**`InvalidRequestError` about an async driver, or greenlet missing.** The
`[asyncio]` extra on SQLAlchemy is what installs greenlet. `uv sync` after
checking `pyproject.toml` still says `sqlalchemy[asyncio]`.

**Port 8080, 5433 or 5050 already in use.** Something else is bound. The database
port can be overridden on the host side without editing the file:

```bash
DB_PORT=5533 docker compose up -d --wait db
```

For the app port, edit the `ports:` mapping for the `api` service — only the
left-hand number matters.

**`rateLimited` or a banner on the front page.** The free plan is 100 requests
a day and `/` spends one per load. The JSON API keeps working; it reads
Postgres.
