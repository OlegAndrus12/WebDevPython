# module08 — a full REST surface: writes, sub-resources and relations

The news reader with a complete set of endpoints. Alongside the read-only
article API there is now a **readers** resource with real `POST` / `PATCH` /
`DELETE`, and a **likes** sub-resource joining readers to articles. Four
tables, fifteen endpoints, generated docs at `/docs`.

Nothing here authenticates. The reader is named in the URL, so `user_id` is an
ordinary path parameter — there is no session, no token and no `current_user`.
That is a deliberate limit: it keeps this module about REST shape, status codes
and relational writes, and makes the identity problem visible rather than
solved.

```
cnn-website/
  news/
    main.py           the FastAPI app, static mount, /healthz
    routers/
      api.py          the read-only article API
      users.py        readers CRUD + the likes sub-resource
      pages.py        the HTML pages and the Jinja environment
    dependencies.py   SessionDep — the injected AsyncSession
    db.py             async engine, async_sessionmaker, get_db()
    repository.py     every query, all `async def`
    models.py         Source, Article, User, LikedArticle
    schemas.py        Pydantic request and response models
    news_api.py       the NewsAPI client (httpx.AsyncClient)
    settings.py       pydantic-settings, validated at import
    utils.py          pure helpers: domain, parse_published, slugify
    templates/        base, index, article, _card, liked
    static/
      styles.css
      likes.js        the reader picker and the like buttons
  migrations/         Alembic with an async env.py + three revisions
  docker-compose.yaml api + db + pgAdmin
```

**Stack:** FastAPI · uvicorn · SQLAlchemy 2.0 (asyncio) + greenlet ·
Alembic · psycopg 3 · httpx · pydantic + email-validator ·
pydantic-settings · Postgres 15 · Python 3.13 · uv

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

Try the whole feature in the browser: open <http://localhost:8080/docs> and
`POST /api/users` to create a reader, then open <http://localhost:8080>, pick
that reader in the navbar dropdown, click a heart on any story, and open
**Liked** in the navbar. Clicking a heart with nobody picked reveals a banner
instead — reading needs no reader, only liking does. pgAdmin takes about 25
seconds to finish booting and has the `db` connection preloaded.

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
| `api` | `cnn08_api` | 8080 | the app under uvicorn (`8000` inside) |
| `db` | `cnn08_postgres` | 5433 | Postgres 15 (`5432` inside the network) |
| `pgadmin` | `cnn08_pgadmin` | 5050 | <http://localhost:5050> |

pgAdmin logs in with `admin@gmail.com` / `admin`; the `db` connection is
preloaded from `pgadmin/servers.json`.

`name: cnn08` at the top of `docker-compose.yaml` is load-bearing. Compose
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

**A second router, mounted alongside the first.** `main.py` composes the app
from three `APIRouter`s via `include_router`: `api.py` (articles, read-only),
`users.py` (readers and their likes), `pages.py` (HTML). Each router carries
its own `prefix` and `tags`, which is what groups them in `/docs`.

**The write half of REST, and the status codes that go with it.**

| | |
| --- | --- |
| `201 Created` | `POST /api/users`, with the created object in the body |
| `204 No Content` | `DELETE`, and both like routes — nothing to return |
| `404 Not Found` | any `{user_id}` or `{article_id}` that does not exist |
| `409 Conflict` | a username or email already taken |
| `422 Unprocessable` | a malformed email, or `user_id=0` against `Path(ge=1)` |

**Uniqueness checked in the app, not just the database.** `users.username` and
`users.email` are both `UNIQUE`, so Postgres would refuse a duplicate either
way — as an `IntegrityError`, which surfaces as a 500. Looking the value up
first turns that into a `409` that says *which* field clashed.

**`PATCH` semantics.** `UserUpdate` has every field optional, and the route
uses `body.model_dump(exclude_unset=True)`. That is what separates "the client
omitted this field" from "the client sent null" — an omitted field keeps its
current value instead of being wiped. The uniqueness re-check only fires for a
value that actually changed, so `PATCH`ing a reader with its own email is a
`200`, not a `409` against itself.

**Constrained path parameters.** `Path(..., ge=1)` on `user_id` and
`article_id` means `/api/users/0` is a `422` from the framework, before any
query runs, and the bound appears in the generated schema.

**A composite primary key as an integrity rule.** `liked_articles` is keyed on
`(user_id, article_id)`, so the same pair simply cannot exist twice — the
schema enforces "one like per reader per article" rather than the application
remembering to. The routes then make liking *idempotent*: `like_article()` asks
before inserting, so a double `POST` is `204` both times instead of an
`IntegrityError`, and a `DELETE` of something never liked is also `204`.

**`ON DELETE CASCADE` on a join table.** Both foreign keys cascade, so
deleting a reader takes their likes with it in one statement. Worth watching in
psql: delete a reader, then count the rows left in `liked_articles`.

**Querying across a relation without a `relationship()`.** There is no
`secondary=` on either model. `list_liked_articles()` joins explicitly and
orders by a column on the *association* table, not on the articles:

```python
select(Article)
  .join(LikedArticle, LikedArticle.article_id == Article.id)
  .where(LikedArticle.user_id == user_id)
  .options(joinedload(Article.source))
  .order_by(LikedArticle.liked_at.desc())
```

"Newest like first" is a different order from "newest article first", and only
the join can express it. The `joinedload` is still mandatory — see below.

**Eager loading is not optional under asyncio.** Attribute access is sync by
definition, so an `AsyncSession` cannot go to the database for
`article.source.name`:

```python
row = await session.scalar(select(Article).limit(1))   # no joinedload
row.source.name
# sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called
```

Every relationship a caller will touch has to be loaded up front. The corollary
is `expire_on_commit=False` in `db.py`: leave it on and `commit()` marks every
attribute stale, so the next read is a lazy load — an exception, not a slow
query.

**`EmailStr`, and what it costs.** `UserCreate.email` is an `EmailStr`, so a
malformed address is a `422` from the schema and no route validates by hand.
It needs the `[email]` extra on pydantic (`email-validator`); without it,
importing `schemas.py` raises. Note that `email-validator` rejects reserved
TLDs — `.local` and `.test` both fail — so use `.example` in test data.

**Identity without authentication, and why it is a stand-in.** Every like route
takes the reader's id in the path, so the browser has to decide who it is
acting as. `static/likes.js` fills a navbar `<select>` from `GET /api/users`
and keeps the choice in `localStorage`. That is a stand-in for a session, not a
security boundary: picking someone else's id is exactly as allowed as picking
your own, because nothing proves anything. The file says so in its own header
comment. Discussion worth having in the lecture — what exactly would have to
change to make this safe.

**Server-rendered pages that cannot render the answer.** `/liked` is an empty
shell. The server has no idea which reader is asking, so the template ships
with nothing in it and `likes.js` fills `#liked-list` from
`GET /api/users/{user_id}/liked`. Same reason the like hearts on the front page
always start empty and get coloured in after load: the HTML is identical for
every visitor.

**The repository pattern survives all of it.** Every `select()` still lives in
`repository.py`; the routers contain no SQL.

```bash
grep -rn "select(" news/     # only ever repository.py
```

---

## Endpoints

### Articles — read only

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/api/articles` | stored articles as JSON: `?q=`, `?page=`, `?per_page=` |
| `GET` | `/api/articles/{article_id}` | one stored article |
| `GET` | `/api/stats` | how many stored articles each source accounts for |

### Readers

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/api/users` | list readers |
| `POST` | `/api/users` | create one — `201`, or `409` if taken |
| `GET` | `/api/users/{user_id}` | one reader |
| `PATCH` | `/api/users/{user_id}` | partial update |
| `DELETE` | `/api/users/{user_id}` | `204`; cascades to that reader's likes |

### Likes

| method | path | what it does |
| --- | --- | --- |
| `POST` | `/api/users/{user_id}/articles/{article_id}/like` | `204`, idempotent |
| `DELETE` | `/api/users/{user_id}/articles/{article_id}/like` | `204`, idempotent |
| `GET` | `/api/users/{user_id}/liked` | that reader's likes, newest like first |

### Pages and ops

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/` | headlines, or `?q=` search — the only route that calls NewsAPI |
| `GET` | `/article/{article_id}` | detail page, rendered from the database |
| `GET` | `/liked` | a shell; `likes.js` fills it for the picked reader |
| `GET` | `/healthz` | `SELECT 1`, used by the Compose healthcheck |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | generated, no code |

Notes worth knowing before you rely on them:

- `/` is the only route that spends a NewsAPI request. Everything else reads
  Postgres, so the whole API works with your daily quota exhausted.
- `?q=` on `/` searches **NewsAPI**; `?q=` on `/api/articles` searches **what
  is already stored**.
- Liking is idempotent in both directions — `POST` twice and `DELETE` twice are
  both `204`. Neither is an error.
- Both like routes verify the reader *and* the article, so a bad id in either
  position is a `404` rather than a foreign-key error.
- The HTML pages are excluded from the schema, so `/docs` shows the API only.
- `per_page` is capped at 100; `page` and every `{id}` have a minimum of 1.

---

## Testing it with curl

Against the Compose stack on port 8080. If you are running uvicorn on the host,
use `localhost:8000` instead. The sequence below is meant to be run in order.

```bash
B=localhost:8080
```

**Is it up, and can it reach the database?**

```bash
curl -s $B/healthz
# {"status":"ok","db":"ok"}
```

**Load the front page once, to put stories in the database.** This is the call
that spends a NewsAPI request, and the likes below need articles to point at.

```bash
curl -s -o /dev/null -w '%{http_code}\n' $B/
# 200

curl -s $B/api/stats
# {"sources":[{"slug":"cnn","name":"CNN","articles":10}],"total_articles":10,"total_sources":1}
```

### Readers

```bash
curl -s -X POST $B/api/users -H 'Content-Type: application/json' \
  -d '{"username":"grace","email":"grace@example.com"}'
# {"id":1,"username":"grace","email":"grace@example.com"}

curl -s -X POST $B/api/users -H 'Content-Type: application/json' \
  -d '{"username":"alan","email":"alan@example.com"}'
# {"id":2,"username":"alan","email":"alan@example.com"}

curl -s $B/api/users
# [{"id":1,"username":"grace",...},{"id":2,"username":"alan",...}]

curl -s $B/api/users/1
# {"id":1,"username":"grace","email":"grace@example.com"}
```

**The conflicts and the validation:**

```bash
# email already registered
curl -s -w ' [%{http_code}]\n' -X POST $B/api/users \
  -H 'Content-Type: application/json' \
  -d '{"username":"other","email":"grace@example.com"}'
# {"detail":"Email already registered"} [409]

# username already taken
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users \
  -H 'Content-Type: application/json' \
  -d '{"username":"grace","email":"new@example.com"}'
# 409

# not an email address -> the schema rejects it
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users \
  -H 'Content-Type: application/json' \
  -d '{"username":"bob","email":"not-an-email"}'
# 422

# no such reader / id below the Path(ge=1) bound
curl -s -o /dev/null -w '%{http_code}\n' $B/api/users/999    # 404
curl -s -o /dev/null -w '%{http_code}\n' $B/api/users/0      # 422
```

**`PATCH` sends only what changes:**

```bash
curl -s -X PATCH $B/api/users/1 -H 'Content-Type: application/json' \
  -d '{"username":"grace-h"}'
# {"id":1,"username":"grace-h","email":"grace@example.com"}
#            ^ changed              ^ untouched, because it was not sent

# patching a reader with its own email must NOT 409 against itself
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $B/api/users/1 \
  -H 'Content-Type: application/json' -d '{"email":"grace@example.com"}'
# 200

# but taking someone else's does
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $B/api/users/1 \
  -H 'Content-Type: application/json' -d '{"email":"alan@example.com"}'
# 409
```

### Likes

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/1/articles/1/like   # 204
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/1/articles/1/like   # 204  <- idempotent
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/1/articles/2/like   # 204
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/2/articles/1/like   # 204

# a bad id in either position is a 404, not a foreign-key error
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/999/articles/1/like   # 404
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/1/articles/999/like   # 404
```

**Whose likes are whose** — note the order is newest *like* first, so article 2
comes back before article 1:

```bash
curl -s $B/api/users/1/liked | python3 -c \
  'import json,sys; print([a["id"] for a in json.load(sys.stdin)])'
# [2, 1]

curl -s $B/api/users/2/liked | python3 -c \
  'import json,sys; print([a["id"] for a in json.load(sys.stdin)])'
# [1]
```

**Each liked article carries its source**, which is the `joinedload` doing its
job — without it this would raise `MissingGreenlet`:

```bash
curl -s $B/api/users/2/liked | python3 -c \
  'import json,sys; print(json.load(sys.stdin)[0]["source"])'
# {'slug': 'cnn', 'name': 'CNN'}
```

**Unliking, also idempotent:**

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $B/api/users/1/articles/1/like  # 204
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $B/api/users/1/articles/1/like  # 204

curl -s $B/api/users/1/liked | python3 -c \
  'import json,sys; print([a["id"] for a in json.load(sys.stdin)])'
# [2]
```

**The cascade.** Delete a reader and their likes go too:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $B/api/users/2       # 204
curl -s -o /dev/null -w '%{http_code}\n' $B/api/users/2                 # 404

docker compose exec -T db psql -U admin -d cnn \
  -tAc "select count(*) from liked_articles where user_id=2;"
# 0
```

### The generated schema

Every path the app serves, with no route table to maintain by hand:

```bash
curl -s $B/openapi.json | python3 -c "
import json,sys
for path, ops in sorted(json.load(sys.stdin)['paths'].items()):
    for method in sorted(ops):
        print(f'{method.upper():7} {path}')"
# GET     /api/articles
# GET     /api/articles/{article_id}
# GET     /api/stats
# GET     /api/users
# POST    /api/users
# DELETE  /api/users/{user_id}
# GET     /api/users/{user_id}
# PATCH   /api/users/{user_id}
# DELETE  /api/users/{user_id}/articles/{article_id}/like
# POST    /api/users/{user_id}/articles/{article_id}/like
# GET     /api/users/{user_id}/liked
# GET     /healthz
```

### The pages

```bash
curl -s -o /dev/null -w '%{http_code}\n' $B/               # 200
curl -s -o /dev/null -w '%{http_code}\n' $B/article/1      # 200
curl -s -o /dev/null -w '%{http_code}\n' $B/liked          # 200, an empty shell
```

In a browser: open <http://localhost:8080>, pick a reader in the navbar
dropdown, then click a heart. Clicking one with nobody picked reveals a banner
instead — reading needs no reader, only liking does.

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

`.env` is gitignored; `.env.example` is not.

---

## The database

Four tables, all created by migrations. There is deliberately no `create_all()`
anywhere.

```
sources          id, slug (unique), name
articles         id, source_id -> sources.id (cascade), url (unique), title,
                 description, content, image_url, author, published_at
users            id, username (unique), email (unique)
liked_articles   user_id + article_id  (composite primary key),
                 both FKs ON DELETE CASCADE, liked_at default now()
```

```bash
docker compose exec db psql -U admin -d cnn -c '\dt'
docker compose exec db psql -U admin -d cnn -c '\d liked_articles'
```

That last one is worth reading aloud — the composite `pk_liked_articles` and
the two cascading foreign keys are the whole integrity story of this module.

Three revisions, `759161cd8fb3` → `b773fddbe615` → `4f0bc8afd9a6`, and
`4f0bc8afd9a6` is head.

```bash
uv run alembic current            # where the database is
uv run alembic history            # the chain
uv run alembic upgrade head       # apply everything
uv run alembic downgrade -1       # drops users + liked_articles again
```

After changing `models.py`:

```bash
uv run alembic revision --autogenerate -m "what changed"
# then READ the generated file before applying it
uv run alembic upgrade head
```

A naming convention on `Base.metadata` gives constraints predictable names, so
the generated revision says `pk_liked_articles` and
`fk_liked_articles_user_id_users` rather than leaving Alembic unable to name
what a downgrade should drop.

### Seeding without spending NewsAPI requests

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
        user = await repo.create_user("seeded", "seeded@example.com")
        await repo.like_article(user.id, article.id)
        print("article", article.id, "liked by user", user.id)
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
eager-loaded. Add `joinedload(...)` to the query that produced the object. The
likes join is the easiest place to reintroduce this by accident.

**A `500` with `IntegrityError` on a like.** Something bypassed
`like_article()`'s existence check and hit the composite primary key directly.
Insert through the repository, not by adding a `LikedArticle` by hand.

**`ImportError` from `schemas.py` mentioning `email-validator`.** `EmailStr`
needs the `[email]` extra on pydantic. Check `pyproject.toml` still says
`pydantic[email]`, then `uv sync`.

**A `422` on an email that looks fine.** `email-validator` rejects reserved
TLDs, so `you@host.local` and `you@host.test` both fail. Use `.example`.

**Every like returns `404` from the browser.** The picked reader no longer
exists — it was deleted through the API while its id sat in `localStorage`.
`likes.js` clears a stale id on load, so a refresh fixes it; re-pick from the
dropdown.

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

**Port 8080, 5433 or 5050 already in use.** Something else is bound. The database
port can be overridden on the host side without editing the file:

```bash
DB_PORT=5533 docker compose up -d --wait db
```

For the app port, edit the `ports:` mapping for the `api` service — only the
left-hand number matters.

**`rateLimited` or a banner on the front page.** The free plan is 100 requests
a day and `/` spends one per load. Everything else reads Postgres.
