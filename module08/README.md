# module08 — a full REST surface: writes, sub-resources and relations

The news reader with a complete set of endpoints. Alongside the read-only article
API there is now a **readers** resource with real `POST` / `PATCH` / `DELETE`,
and a **likes** sub-resource joining readers to articles. Four tables, fifteen
endpoints.

Nothing here authenticates. The reader is named in the URL, so `user_id` is an
ordinary path parameter — no session, no token, no `current_user`. That is a
deliberate limit: it keeps this module about REST shape, status codes and
relational writes, and makes the identity problem visible rather than solved.
module09 answers it.

```
cnn-website/
  news/
    main.py           the FastAPI app, static mount, /healthz
    routers/
      api.py          the read-only article API
      users.py        readers CRUD + the likes sub-resource
      pages.py        the HTML pages
    db.py             async engine, async_sessionmaker, get_db()
    repository.py     every query, all `async def`
    models.py         Source, Article, User, LikedArticle
    schemas.py        Pydantic request and response models
    static/likes.js   the reader picker and the like buttons
  migrations/         Alembic with an async env.py + three revisions
  docker-compose.yaml api + db + pgAdmin
  render-start.sh     migrate, then serve -- deployment only, see module12
```

`render-start.sh` is the odd one out — the only file here that is not about this
module's topic. It runs `alembic upgrade head` and then the server, which is what
[deploying to Render](../module12/render-module08.md) needs and nothing local
does: Compose runs its own command and never touches it.

**Stack:** FastAPI · uvicorn · SQLAlchemy 2.0 (asyncio) + greenlet · Alembic ·
psycopg 3 · httpx · pydantic + email-validator · Postgres 15 · Python 3.13 · uv

---

## Running it

```bash
cd module08/cnn-website
cp .env.example .env          # then put your key in NEWS_API_KEY
docker compose up --build --wait
```

| service | container | URL | |
| --- | --- | --- | --- |
| `api` | `cnn08_api` | <http://localhost:8008> | the reader; `/docs` for Swagger UI |
| `db` | `cnn08_postgres` | `localhost:5408` | Postgres 15 (`5432` in-network) |
| `pgadmin` | `cnn08_pgadmin` | <http://localhost:5108> | `admin@gmail.com` / `admin`, `db` preloaded |

Every published port ends in **08**, so modules 06–11 can all run at once.

Try the feature end to end: `POST /api/users` from `/docs` to create a reader,
then open <http://localhost:8008>, pick that reader in the navbar dropdown, click
a heart, and open **Liked**. Clicking a heart with nobody picked reveals a banner
instead — reading needs no reader, only liking does.

### Or run uvicorn on the host

```bash
docker compose up -d --wait db        # just Postgres, on localhost:5408
uv run alembic upgrade head
uv run uvicorn news:app --reload      # -> http://localhost:8000/docs
```

---

## What this module covers

**A third router.** `main.py` composes the app from `api.py` (articles),
`users.py` (readers and likes) and `pages.py` (HTML), each with its own `prefix`
and `tags` — which is what groups them in `/docs`.

**The write half of REST, and its status codes.**

| | |
| --- | --- |
| `201 Created` | `POST /api/users`, with the created object in the body |
| `204 No Content` | `DELETE`, and both like routes — nothing to return |
| `404 Not Found` | any `{user_id}` or `{article_id}` that does not exist |
| `409 Conflict` | a username or email already taken |
| `422 Unprocessable` | a malformed email, or `user_id=0` against `Path(ge=1)` |

**Uniqueness checked in the app, not only the database.** Both columns are
`UNIQUE`, so Postgres would refuse a duplicate either way — as an
`IntegrityError`, which surfaces as a 500. Looking the value up first turns that
into a `409` that says *which* field clashed.

**`PATCH` semantics.** `UserUpdate` has every field optional and the route uses
`body.model_dump(exclude_unset=True)`. That is what separates "the client omitted
this field" from "the client sent null" — an omitted field keeps its value. The
uniqueness re-check only fires for a value that actually changed, so `PATCH`ing a
reader with its own email is a `200`, not a `409` against itself.

**A composite primary key as an integrity rule.** `liked_articles` is keyed on
`(user_id, article_id)`, so the same pair cannot exist twice — the schema
enforces "one like per reader per article" rather than the application
remembering to. The routes then make liking *idempotent*: a double `POST` is
`204` both times instead of an `IntegrityError`, and a `DELETE` of something
never liked is also `204`.

**`ON DELETE CASCADE` on a join table.** Both foreign keys cascade, so deleting a
reader takes their likes in one statement.

**Querying across a relation without a `relationship()`.** There is no
`secondary=` on either model. `list_liked_articles()` joins explicitly and orders
by a column on the *association* table:

```python
select(Article)
  .join(LikedArticle, LikedArticle.article_id == Article.id)
  .where(LikedArticle.user_id == user_id)
  .options(joinedload(Article.source))
  .order_by(LikedArticle.liked_at.desc())
```

"Newest like first" is a different order from "newest article first", and only
the join can express it. The `joinedload` is still mandatory — attribute access
is sync, so a missed one is `MissingGreenlet`, not a slow query.

**`EmailStr`, and what it costs.** A malformed address is a `422` from the schema
with no hand-written check. It needs the `[email]` extra on pydantic; without it
importing `schemas.py` raises. Note that `email-validator` rejects reserved TLDs
— `.local` and `.test` both fail — so use `.example` in test data.

**Identity without authentication.** Every like route takes the reader's id in
the path, so the browser has to decide who it is acting as. `static/likes.js`
fills a navbar `<select>` from `GET /api/users` and keeps the choice in
`localStorage`. That is a stand-in for a session, not a security boundary:
picking someone else's id is exactly as allowed as picking your own, because
nothing proves anything.

**Server-rendered pages that cannot render the answer.** `/liked` ships as an
empty shell — the server has no idea which reader is asking — and `likes.js`
fills it from the API. Same reason the hearts start empty and get coloured in
after load: the HTML is identical for every visitor.

---

## Endpoints

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/api/articles` | stored articles: `?q=`, `?page=`, `?per_page=` |
| `GET` | `/api/articles/{article_id}` | one stored article |
| `GET` | `/api/stats` | per-source counts |
| `GET` `POST` | `/api/users` | list readers / create one (`201`, or `409`) |
| `GET` `PATCH` `DELETE` | `/api/users/{user_id}` | one reader; `DELETE` cascades to likes |
| `POST` `DELETE` | `/api/users/{user_id}/articles/{article_id}/like` | `204`, idempotent both ways |
| `GET` | `/api/users/{user_id}/liked` | that reader's likes, newest like first |
| `GET` | `/`, `/article/{id}`, `/liked` | the HTML pages |
| `GET` | `/healthz` | `SELECT 1`, used by the Compose healthcheck |

- Only `/` spends NewsAPI quota; everything else reads Postgres.
- Both like routes verify the reader *and* the article, so a bad id in either
  position is a `404` rather than a foreign-key error.
- The HTML pages are excluded from the schema, so `/docs` shows the API only.

### The sequence worth running

```bash
B=localhost:8008
curl -s -o /dev/null -w '%{http_code}\n' $B/        # 200 -- fills the database

curl -s -X POST $B/api/users -H 'Content-Type: application/json' \
  -d '{"username":"grace","email":"grace@example.com"}'
# {"id":1,"username":"grace","email":"grace@example.com"}

# the conflicts and the validation
curl -s -w ' [%{http_code}]\n' -X POST $B/api/users -H 'Content-Type: application/json' \
  -d '{"username":"other","email":"grace@example.com"}'
# {"detail":"Email already registered"} [409]
curl -s -o /dev/null -w '%{http_code}\n' $B/api/users/999    # 404
curl -s -o /dev/null -w '%{http_code}\n' $B/api/users/0      # 422

# PATCH sends only what changes -- and must not conflict with itself
curl -s -X PATCH $B/api/users/1 -H 'Content-Type: application/json' -d '{"username":"grace-h"}'
# {"id":1,"username":"grace-h","email":"grace@example.com"}   <- email untouched
curl -s -o /dev/null -w '%{http_code}\n' -X PATCH $B/api/users/1 \
  -H 'Content-Type: application/json' -d '{"email":"grace@example.com"}'
# 200

# likes: idempotent in both directions
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/1/articles/1/like   # 204
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/1/articles/1/like   # 204
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/users/999/articles/1/like # 404

# newest LIKE first, so article 2 precedes article 1
curl -s $B/api/users/1/liked | python3 -c \
  'import json,sys; print([a["id"] for a in json.load(sys.stdin)])'

# the cascade
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE $B/api/users/1     # 204
docker compose exec -T db psql -U admin -d cnn \
  -tAc "select count(*) from liked_articles where user_id=1;"         # 0
```

---

## Configuration

| variable | default | what it is |
| --- | --- | --- |
| `NEWS_API_KEY` | *required* | no default; the app refuses to start without it |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `admin` / `admin` / `cnn` | also fed to Postgres by Compose |
| `DB_HOST` / `DB_PORT` | `localhost` / `5408` | the api container overrides both to `db:5432` |
| `DEFAULT_SOURCE` | `cnn` | which NewsAPI source the front page shows |
| `PAGE_SIZE` | `12` | how many articles to request **from NewsAPI** |

---

## The database

```
sources          id, slug (unique), name
articles         id, source_id -> sources.id (cascade), url (unique), title,
                 description, content, image_url, author, published_at
users            id, username (unique), email (unique)
liked_articles   user_id + article_id  (composite primary key),
                 both FKs ON DELETE CASCADE, liked_at default now()
```

```bash
docker compose exec db psql -U admin -d cnn -c '\d liked_articles'
```

That one is worth reading aloud — the composite `pk_liked_articles` and the two
cascading foreign keys are the whole integrity story of this module.

Three revisions, `759161cd8fb3` → `b773fddbe615` → `4f0bc8afd9a6` (head).

```bash
uv run alembic current            # where the database is
uv run alembic upgrade head
uv run alembic downgrade -1       # drops users + liked_articles again
```

---

## Troubleshooting

**`MissingGreenlet`** — a lazy load on an async session. Add `joinedload(...)`;
the likes join is the easiest place to reintroduce this by accident.

**A `500` with `IntegrityError` on a like** — something bypassed
`like_article()`'s existence check and hit the composite primary key directly.

**A `422` on an email that looks fine** — `email-validator` rejects reserved
TLDs, so `you@host.local` and `you@host.test` both fail. Use `.example`.

**Every like returns `404` from the browser** — the picked reader was deleted
while its id sat in `localStorage`. Refresh and re-pick.

📋 Topic list: **[AGENDA.md](AGENDA.md)**
