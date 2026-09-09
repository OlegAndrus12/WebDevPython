# module09 — JWT authentication

The news reader with accounts. Registering stores a bcrypt hash, logging in
returns a signed JSON Web Token, and every JSON endpoint refuses to answer
without one. Likes become per-user, because there is finally a user to attach
them to.

Four tables, fifteen endpoints, generated docs at `/docs`. The browser holds
its token in `localStorage` and attaches it by hand, so there is no cookie and
no server-side session anywhere.

```
cnn-website/
  news/
    main.py           the FastAPI app, static mount, /healthz
    security.py       AuthService: bcrypt hashing, HS256 tokens, get_current_user
    routers/
      auth.py         register, login, me
      api.py          the JSON API, every route behind a token
      pages.py        the HTML pages and the Jinja environment
    dependencies.py   SessionDep — the injected AsyncSession
    db.py             async engine, async_sessionmaker, get_db()
    repository.py     every query, all `async def`
    models.py         Source, Article, User, LikedArticle
    schemas.py        Pydantic request and response models
    news_api.py       the NewsAPI client (httpx.AsyncClient)
    settings.py       pydantic-settings, validated at import
    utils.py          pure helpers: domain, parse_published, slugify
    templates/        base, index, article, _card, login, register, liked
    static/
      styles.css
      auth.js         holds the token, drives the forms and the like buttons
  migrations/         Alembic with an async env.py + three revisions
  docker-compose.yaml api + db + pgAdmin
```

**Stack:** FastAPI · uvicorn · SQLAlchemy 2.0 (asyncio) + greenlet · Alembic ·
psycopg 3 · httpx · pydantic + email-validator · pydantic-settings ·
passlib + bcrypt · python-jose · Postgres 15 · Python 3.13 · uv

---

## Running it

You need a free NewsAPI key from <https://newsapi.org/register>. The Developer
plan allows 100 requests a day, and the front page spends one per load.

```bash
cd cnn-website
cp .env.example .env       # put your key in NEWS_API_KEY
openssl rand -hex 32       # and paste the result into SECRET_KEY
```

`SECRET_KEY` has no default on purpose: an app that signs tokens with a
guessable key signs forgeable tokens. It will refuse to start without one.

### Everything in Docker

```bash
docker compose up --build --wait
```

`--wait` blocks until every healthcheck passes and exits non-zero if one does
not, so it is safe to chain a `curl` after it. Migrations run automatically on
container start.

### Open it in a browser

| | |
| --- | --- |
| the reader | <http://localhost:8080> |
| interactive API docs (Swagger UI) | <http://localhost:8080/docs> |
| the same schema, ReDoc | <http://localhost:8080/redoc> |
| pgAdmin | <http://localhost:5050> — `admin@gmail.com` / `admin` |

Try it end to end in the browser: open <http://localhost:8080>, click
**Register**, create an account, log in, then click a heart on any story and
open **Liked** in the navbar. pgAdmin takes about 25 seconds to finish booting
and has the `db` connection preloaded, so there is no "Register → Server…"
dialog to fill in.

To call a protected endpoint from `/docs`, click **Authorize**, and enter the
account's *email* in the field labelled `username` — that is the OAuth2 password
flow's field name, not a mistake.

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
| `api` | `cnn09_api` | 8080 | the app under uvicorn (`8000` inside) |
| `db` | `cnn09_postgres` | 5433 | Postgres 15 (`5432` inside the network) |
| `pgadmin` | `cnn09_pgadmin` | 5050 | |

`name: cnn09` at the top of `docker-compose.yaml` is load-bearing. Compose
otherwise derives the project name from the directory, and more than one
project on this machine is called `cnn-website` — without an explicit name a
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

**Hashing, not storing.** `AuthService.hash_password()` runs the password
through passlib's bcrypt context, and only the hash reaches the database.
`User` has a `hashed_password` column and `UserOut` does not have the field at
all, so no response can leak it even by accident.

**HS256, one secret, symmetric.** `create_access_token()` signs a payload of
`sub` (the email), `scope`, and `exp` with `SECRET_KEY`. The same key verifies
it, which is what "symmetric" means: anything that can check a token can also
mint one, so the key never leaves the server.

**A signed token is not an encrypted one.** Anyone holding a token can read its
claims — try it below. What the signature buys is that nobody can *forge* or
*alter* one. Never put anything secret in a JWT.

**`get_current_user` as a dependency.** One `async def` in `security.py`
decodes the token, pulls `sub`, and looks the user up. Any route that adds
`current_user: User = Depends(auth_service.get_current_user)` is protected, and
`/docs` grows a padlock for it automatically. The database lookup on every
request is deliberate: the signature proves the claim was issued, not that the
row still exists.

**The OAuth2 password flow, and its odd field name.**
`OAuth2PasswordRequestForm` parses a **form-urlencoded** body — not JSON — with
fields named `username` and `password`. This app authenticates by email, so the
email goes in the field called `username`. That is the spec's name; it is why
`login.html` has `name="username"` on an `type="email"` input, and why
`python-multipart` is a dependency.

**One error message for two failures.** An unknown address and a wrong password
both return `401 Invalid email or password`. Distinguishing them would turn the
login endpoint into an oracle for "is this address registered?".

**401 with `WWW-Authenticate: Bearer`.** RFC 6750 requires the header on a
rejection from a bearer scheme; `CREDENTIALS_EXCEPTION` in `security.py` sets
it once and every failure path reuses it.

**No cookie means the browser needs JavaScript.** A cookie is attached
automatically; an `Authorization` header is not, and a plain
`<form method="post">` cannot set one. That single fact is what pushes
`static/auth.js` into existence — it stores the token, attaches it to every
`fetch`, hydrates the navbar with the logged-in name, and drives the like
buttons. The pages themselves are shells: the server rendering them has no idea
who is asking.

**Bearer tokens cannot be revoked.** Nothing here has a logout endpoint,
because there is nothing to tell. "Log out" deletes the token from
`localStorage`; the token itself stays valid until `exp`. That is the trade for
statelessness, and the reason `ACCESS_TOKEN_EXPIRE_MINUTES` is short.

**Likes belong to the token holder.** `POST /api/articles/{id}/like` takes no
user id — it reads `current_user.id`. `liked_articles` is keyed on
`(user_id, article_id)`, so the same pair cannot exist twice and liking is
idempotent at the schema level; both routes make that a `204` rather than a
conflict. Both foreign keys are `ON DELETE CASCADE`.

**Eager loading is not optional under asyncio.** Attribute access is sync by
definition, so an `AsyncSession` cannot go to the database for
`article.source.name`:

```python
row = await session.scalar(select(Article).limit(1))   # no joinedload
row.source.name
# sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called
```

Every relationship a caller will touch has to be loaded up front, which is why
`list_liked_articles()` states `joinedload(Article.source)`. The corollary is
`expire_on_commit=False` in `db.py`: leave it on and `commit()` marks every
attribute stale, so the next read is a lazy load — an exception, not a slow
query.

**The repository pattern holds.** Every `select()` lives in `repository.py`;
routers and `security.py` contain no SQL.

```bash
grep -rn "select(" news/     # only ever repository.py
```

---

## Endpoints

🔒 marks a route that requires `Authorization: Bearer <token>`.

### Accounts

| method | path | what it does |
| --- | --- | --- |
| `POST` | `/api/auth/register` | create an account — `201`, or `409` if taken |
| `POST` | `/api/auth/login` | form-urlencoded; returns the bearer token |
| `GET` | `/api/auth/me` | 🔒 whoever the token belongs to |

### Articles

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/api/articles` | 🔒 stored articles: `?q=`, `?page=`, `?per_page=` |
| `GET` | `/api/articles/{article_id}` | 🔒 one stored article |
| `GET` | `/api/stats` | 🔒 how many articles each source accounts for |

### Likes

| method | path | what it does |
| --- | --- | --- |
| `POST` | `/api/articles/{article_id}/like` | 🔒 `204`, idempotent |
| `DELETE` | `/api/articles/{article_id}/like` | 🔒 `204`, idempotent |
| `GET` | `/api/me/liked` | 🔒 the caller's likes, newest like first |

### Pages and ops

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/` | headlines, or `?q=` search — the only route that calls NewsAPI |
| `GET` | `/article/{article_id}` | detail page, rendered from the database |
| `GET` | `/login`, `/register` | shells; `auth.js` submits them |
| `GET` | `/liked` | a shell; `auth.js` fills it with the token |
| `GET` | `/healthz` | `SELECT 1`, used by the Compose healthcheck |
| `GET` | `/docs`, `/redoc`, `/openapi.json` | generated, no code |

Notes worth knowing before you rely on them:

- The HTML pages are **not** token-gated — they are public shells. The data
  behind them is, which is why `/liked` redirects to `/login` when there is no
  token.
- `/` is the only route that spends a NewsAPI request. Everything else reads
  Postgres, so the API works with your daily quota exhausted.
- `?q=` on `/` searches **NewsAPI**; `?q=` on `/api/articles` searches **what
  is already stored**.
- `page` and `per_page` are validated by `Query(ge=…, le=…)` and rejected with
  a `422`; `per_page` is capped at 100.
- There is no logout endpoint and no token refresh. See the note on revocation
  above.

---

## Testing it with curl

Against Docker on port 8080. If you are running uvicorn on the host, use
`localhost:8000`. The sequence below is meant to be run in order.

```bash
B=localhost:8080
```

**Up, and reaching the database?**

```bash
curl -s $B/healthz
# {"status":"ok","db":"ok"}
```

**Load the front page once, to put stories in the database.** This spends a
NewsAPI request, and the likes below need articles to point at.

```bash
curl -s -o /dev/null -w '%{http_code}\n' $B/
# 200
```

**The gate is real.** Nothing under `/api` answers without a token:

```bash
curl -s -o /dev/null -w '%{http_code}\n' $B/api/articles
# 401
```

**Register, then log in.** Note the `Content-Type` on the two calls — JSON to
register, form-urlencoded to log in, with the email in the `username` field:

```bash
curl -s -X POST $B/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"grace","email":"grace@example.com","password":"hunter2hunter2"}'
# {"id":1,"username":"grace","email":"grace@example.com"}
#   ^ no hashed_password in the response: UserOut has no such field

TOKEN=$(curl -s -X POST $B/api/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=grace@example.com&password=hunter2hunter2' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

echo "${TOKEN:0:24}..."
# eyJhbGciOiJIUzI1NiIsInR5...
```

**Who am I?**

```bash
curl -s -H "Authorization: Bearer $TOKEN" $B/api/auth/me
# {"id":1,"username":"grace","email":"grace@example.com"}
```

**Now the API answers:**

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  -H "Authorization: Bearer $TOKEN" "$B/api/articles?per_page=2"
# 200

curl -s -H "Authorization: Bearer $TOKEN" $B/api/stats
# {"sources":[{"slug":"cnn","name":"CNN","articles":12}],"total_articles":12,"total_sources":1}
```

**Likes, keyed to the token, idempotent both ways:**

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H "Authorization: Bearer $TOKEN" $B/api/articles/1/like        # 204
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H "Authorization: Bearer $TOKEN" $B/api/articles/1/like        # 204  <- again

curl -s -H "Authorization: Bearer $TOKEN" $B/api/me/liked | python3 -c \
  'import json,sys; print([a["id"] for a in json.load(sys.stdin)])'
# [1]

curl -s -o /dev/null -w '%{http_code}\n' -X DELETE \
  -H "Authorization: Bearer $TOKEN" $B/api/articles/1/like        # 204
```

**The failures:**

```bash
# wrong password -- and note the message does not say which half was wrong
curl -s -X POST $B/api/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=grace@example.com&password=nope'
# {"detail":"Invalid email or password"}

# an address that was never registered gives the identical answer
curl -s -X POST $B/api/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=nobody@example.com&password=whatever'
# {"detail":"Invalid email or password"}

# a garbage token
curl -s -i -H 'Authorization: Bearer nonsense' $B/api/auth/me | head -4
# HTTP/1.1 401 Unauthorized
# www-authenticate: Bearer        <- required by RFC 6750
# {"detail":"Could not validate credentials"}

# registering the same address twice
curl -s -o /dev/null -w '%{http_code}\n' -X POST $B/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"other","email":"grace@example.com","password":"hunter2hunter2"}'
# 409
```

**Read your own token.** Signed, not encrypted — no key needed to see inside:

```bash
python3 - <<EOF
import base64, json
payload = "$TOKEN".split(".")[1]
payload += "=" * (-len(payload) % 4)
print(json.loads(base64.urlsafe_b64decode(payload)))
EOF
# {'scope': 'access_token', 'sub': 'grace@example.com', 'exp': 1789...}
```

**The pages, which are public shells:**

```bash
for p in / /article/1 /login /register /liked; do
  printf '%-12s %s\n' "$p" "$(curl -s -o /dev/null -w '%{http_code}' $B$p)"
done
# /            200
# /article/1   200
# /login       200
# /register    200
# /liked       200
```

---

## Configuration

Read from the environment first, then `.env`. Environment wins, which is how
Compose overrides the database host without editing a file. Every key is
commented in `.env.example`.

| variable | default | what it is |
| --- | --- | --- |
| `NEWS_API_KEY` | *required* | no default — the app refuses to start without it |
| `SECRET_KEY` | *required* | signs and verifies every JWT; `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | token lifetime; nothing can revoke one early |
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

Four tables, all created by migrations. There is no `create_all()` anywhere.

```
sources          id, slug (unique), name
articles         id, source_id -> sources.id (cascade), url (unique), title,
                 description, content, image_url, author, published_at
users            id, username (unique), email (unique), hashed_password
liked_articles   user_id + article_id  (composite primary key),
                 both FKs ON DELETE CASCADE, liked_at default now()
```

```bash
docker compose exec db psql -U admin -d cnn -c '\dt'
docker compose exec db psql -U admin -d cnn -c '\d users'

# proof that no password is stored
docker compose exec -T db psql -U admin -d cnn \
  -c 'select username, left(hashed_password, 29) as bcrypt_prefix from users;'
```

Three revisions, `759161cd8fb3` → `b773fddbe615` → `fadcea4266cb`, and
`fadcea4266cb` is head.

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
a generated revision can name what a downgrade should drop instead of emitting
`drop_constraint(None, ...)`.

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
        print("created id:", article.id)
    await engine.dispose()

asyncio.run(main())
EOF
```

`await engine.dispose()` at the end, or asyncio complains about a connection
pool torn down at interpreter exit.

---

## Troubleshooting

**`ValidationError: secret_key Field required` at startup.** `.env` has no
`SECRET_KEY`. Generate one with `openssl rand -hex 32`.

**Every request 401s right after you changed `SECRET_KEY`.** Tokens are signed
with the old key and can no longer be verified. Log in again — and clear the
browser's `localStorage` if the navbar is stuck.

**`ValueError: password cannot be longer than 72 bytes` from passlib.** passlib
1.7.4 probes bcrypt with a fixed test hash that `bcrypt>=4.1` rejects. That is
why `pyproject.toml` pins `bcrypt<4.1`; run `uv sync` after checking the pin is
still there.

**`sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called`.** A
lazy load on an async session — some code touched a relationship that was not
eager-loaded. Add `joinedload(...)` to the query that produced the object.

**`ModuleNotFoundError` naming a package that is clearly installed**, usually
from `alembic` or `uvicorn`. A copied `.venv` is the cause: console scripts in
`.venv/bin/` carry **absolute** shebangs, so a venv copied from another project
still points at that project's interpreter.

```bash
head -1 .venv/bin/alembic     # is this path in *this* directory?
rm -rf .venv && uv sync       # the fix
```

**Port 8080, 5433 or 5050 already in use.** Something else is bound. The
database port can be overridden on the host side without editing the file:

```bash
DB_PORT=5533 docker compose up -d --wait db
```

For the app port, edit the `ports:` mapping for the `api` service — only the
left-hand number matters.

**`rateLimited` or a banner on the front page.** The free plan is 100 requests
a day and `/` spends one per load. Everything else reads Postgres.
