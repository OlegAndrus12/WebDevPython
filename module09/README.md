# module09 — JWT authentication

The news reader with accounts. Registering stores a bcrypt hash, logging in
returns a signed JSON Web Token, and every JSON endpoint refuses to answer
without one. Likes become per-user, because there is finally a user to attach
them to.

Four tables, fifteen endpoints. The browser holds its token in `localStorage` and
attaches it by hand, so there is no cookie and no server-side session anywhere.

```
cnn-website/
  news/
    main.py           the FastAPI app, static mount, /healthz
    security.py       AuthService: bcrypt hashing, HS256 tokens, get_current_user
    routers/
      auth.py         register, login, me
      api.py          the JSON API, every route behind a token
      pages.py        the HTML pages
    db.py             async engine, async_sessionmaker, get_db()
    repository.py     every query, all `async def`
    models.py         Source, Article, User, LikedArticle
    schemas.py        Pydantic request and response models
    static/auth.js    holds the token, drives the forms and the like buttons
  migrations/         Alembic with an async env.py + three revisions
  docker-compose.yaml api + db + pgAdmin
```

**Stack:** FastAPI · uvicorn · SQLAlchemy 2.0 (asyncio) + greenlet · Alembic ·
psycopg 3 · httpx · pydantic + email-validator · passlib + bcrypt · python-jose ·
Postgres 15 · Python 3.13 · uv

---

## Running it

```bash
cd module09/cnn-website
cp .env.example .env       # put your key in NEWS_API_KEY
openssl rand -hex 32       # and paste the result into SECRET_KEY
docker compose up --build --wait
```

`SECRET_KEY` has no default on purpose: an app that signs tokens with a guessable
key signs forgeable tokens. It refuses to start without one.

| service | container | URL | |
| --- | --- | --- | --- |
| `api` | `cnn09_api` | <http://localhost:8009> | the reader; `/docs` for Swagger UI |
| `db` | `cnn09_postgres` | `localhost:5409` | Postgres 15 (`5432` in-network) |
| `pgadmin` | `cnn09_pgadmin` | <http://localhost:5109> | `admin@gmail.com` / `admin`, `db` preloaded |

Every published port ends in **09**, so modules 06–11 can all run at once.

End to end in the browser: open <http://localhost:8009>, **Register**, log in,
click a heart, open **Liked**. To call a protected endpoint from `/docs`, click
**Authorize** and enter the account's *email* in the field labelled `username` —
that is the OAuth2 password flow's field name, not a mistake.

### Or run uvicorn on the host

```bash
docker compose up -d --wait db        # just Postgres, on localhost:5409
uv run alembic upgrade head
uv run uvicorn news:app --reload      # -> http://localhost:8000/docs
```

---

## What this module covers

**Hashing, not storing.** `AuthService.hash_password()` runs the password through
passlib's bcrypt context and only the hash reaches the database. `User` has a
`hashed_password` column and `UserOut` does not have the field at all, so no
response can leak it even by accident.

**HS256, one secret, symmetric.** `create_access_token()` signs a payload of
`sub` (the email), `scope` and `exp` with `SECRET_KEY`. The same key verifies it
— which is what symmetric means: anything that can check a token can also mint
one, so the key never leaves the server.

**A signed token is not an encrypted one.** Anyone holding a token can read its
claims — decode one below and see. What the signature buys is that nobody can
*forge* or *alter* one. Never put anything secret in a JWT.

**`get_current_user` as a dependency.** One `async def` in `security.py` decodes
the token, pulls `sub` and looks the user up. Any route that adds
`current_user: User = Depends(auth_service.get_current_user)` is protected, and
`/docs` grows a padlock for it automatically. The database lookup on every
request is deliberate: the signature proves the claim was *issued*, not that the
row still exists.

**The OAuth2 password flow, and its odd field name.**
`OAuth2PasswordRequestForm` parses a **form-urlencoded** body — not JSON — with
fields named `username` and `password`. This app authenticates by email, so the
email goes in the field called `username`. That is the spec's name; it is why
`login.html` has `name="username"` on a `type="email"` input, and why
`python-multipart` is a dependency.

**One error message for two failures.** An unknown address and a wrong password
both return `401 Invalid email or password`. Distinguishing them would turn login
into an oracle for "is this address registered?".

**401 with `WWW-Authenticate: Bearer`.** RFC 6750 requires the header on a
rejection from a bearer scheme; `CREDENTIALS_EXCEPTION` sets it once and every
failure path reuses it.

**No cookie means the browser needs JavaScript.** A cookie is attached
automatically; an `Authorization` header is not, and no `<form method="post">`
can set one. That single fact is what pushes `static/auth.js` into existence — it
stores the token, attaches it to every `fetch`, hydrates the navbar and drives
the like buttons. The pages are shells: the server rendering them has no idea who
is asking.

**Bearer tokens cannot be revoked.** There is no logout endpoint because there is
nothing to tell. "Log out" deletes the token from `localStorage`; the token stays
valid until `exp`. That is the trade for statelessness, and the reason
`ACCESS_TOKEN_EXPIRE_MINUTES` is short.

**Likes belong to the token holder.** `POST /api/articles/{id}/like` takes no
user id — it reads `current_user.id`. `liked_articles` is keyed on
`(user_id, article_id)`, so liking is idempotent at the schema level and both
routes return `204` rather than a conflict. Both foreign keys cascade.

**Eager loading is still not optional.** Attribute access is sync, so a missed
`joinedload(Article.source)` is `MissingGreenlet`, not a slow query. The
corollary is `expire_on_commit=False` in `db.py`: leave it on and `commit()`
marks every attribute stale, making the next read a lazy load.

---

## Endpoints

🔒 marks a route that requires `Authorization: Bearer <token>`.

| method | path | what it does |
| --- | --- | --- |
| `POST` | `/api/auth/register` | create an account — `201`, or `409` if taken |
| `POST` | `/api/auth/login` | form-urlencoded; returns the bearer token |
| `GET` | `/api/auth/me` | 🔒 whoever the token belongs to |
| `GET` | `/api/articles` | 🔒 stored articles: `?q=`, `?page=`, `?per_page=` |
| `GET` | `/api/articles/{article_id}` | 🔒 one stored article |
| `GET` | `/api/stats` | 🔒 per-source counts |
| `POST` `DELETE` | `/api/articles/{article_id}/like` | 🔒 `204`, idempotent both ways |
| `GET` | `/api/me/liked` | 🔒 the caller's likes, newest like first |
| `GET` | `/`, `/article/{id}`, `/login`, `/register`, `/liked` | public shells |
| `GET` | `/healthz` | `SELECT 1`, used by the Compose healthcheck |

- The HTML pages are **not** token-gated — they are public shells. The data
  behind them is, which is why `/liked` redirects to `/login` without a token.
- Only `/` spends NewsAPI quota; everything else reads Postgres.
- There is no logout endpoint and no token refresh. See revocation, above.

### The sequence worth running

```bash
B=localhost:8009
curl -s -o /dev/null -w '%{http_code}\n' $B/            # 200 -- fills the database
curl -s -o /dev/null -w '%{http_code}\n' $B/api/articles  # 401 -- the gate is real

curl -s -X POST $B/api/auth/register -H 'Content-Type: application/json' \
  -d '{"username":"grace","email":"grace@example.com","password":"hunter2hunter2"}'
# {"id":1,"username":"grace","email":"grace@example.com"}
#   ^ no hashed_password: UserOut has no such field

TOKEN=$(curl -s -X POST $B/api/auth/login \
  -d 'username=grace@example.com&password=hunter2hunter2' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

curl -s -H "Authorization: Bearer $TOKEN" $B/api/auth/me
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  -H "Authorization: Bearer $TOKEN" $B/api/articles/1/like    # 204, twice over
curl -s -H "Authorization: Bearer $TOKEN" $B/api/me/liked

# the failures -- note both login errors are identical
curl -s -X POST $B/api/auth/login -d 'username=grace@example.com&password=nope'
curl -s -X POST $B/api/auth/login -d 'username=nobody@example.com&password=whatever'
# {"detail":"Invalid email or password"}   (both)

curl -s -i -H 'Authorization: Bearer nonsense' $B/api/auth/me | head -3
# HTTP/1.1 401 Unauthorized
# www-authenticate: Bearer        <- required by RFC 6750

# read your own token: signed, not encrypted -- no key needed to see inside
python3 - <<EOF
import base64, json
p = "$TOKEN".split(".")[1]; p += "=" * (-len(p) % 4)
print(json.loads(base64.urlsafe_b64decode(p)))
EOF
# {'sub': 'grace@example.com', 'scope': 'access_token', 'exp': 1789...}
```

---

## Configuration

| variable | default | what it is |
| --- | --- | --- |
| `NEWS_API_KEY` | *required* | no default; the app refuses to start without it |
| `SECRET_KEY` | *required* | signs and verifies every JWT; `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | token lifetime; nothing can revoke one early |
| `DB_USER` / `DB_PASSWORD` / `DB_NAME` | `admin` / `admin` / `cnn` | also fed to Postgres by Compose |
| `DB_HOST` / `DB_PORT` | `localhost` / `5409` | the api container overrides both to `db:5432` |
| `DEFAULT_SOURCE` / `PAGE_SIZE` | `cnn` / `12` | what to ask **NewsAPI** for |

---

## The database

```
sources          id, slug (unique), name
articles         id, source_id -> sources.id (cascade), url (unique), title,
                 description, content, image_url, author, published_at
users            id, username (unique), email (unique), hashed_password
liked_articles   user_id + article_id  (composite primary key),
                 both FKs ON DELETE CASCADE, liked_at default now()
```

```bash
# proof that no password is stored
docker compose exec -T db psql -U admin -d cnn \
  -c 'select username, left(hashed_password, 29) as bcrypt_prefix from users;'
```

Three revisions, `759161cd8fb3` → `b773fddbe615` → `fadcea4266cb` (head).

```bash
uv run alembic current            # where the database is
uv run alembic upgrade head
uv run alembic downgrade -1       # drops users + liked_articles again
```

---

## Troubleshooting

**`ValidationError: secret_key Field required`** — `.env` has no `SECRET_KEY`.

**Every request 401s right after you changed `SECRET_KEY`** — existing tokens
were signed with the old one. Log in again, and clear `localStorage` if the
navbar is stuck.

**`ValueError: password cannot be longer than 72 bytes` from passlib** — passlib
1.7.4 probes bcrypt with a fixed test hash that `bcrypt>=4.1` rejects. That is
why `pyproject.toml` pins `bcrypt<4.1`.

**`MissingGreenlet`** — a lazy load on an async session. Add `joinedload(...)`.

📋 Topic list: **[AGENDA.md](AGENDA.md)**
