# module10 — email, Redis and a Celery worker

module09's news reader stops being a single process. Three ideas arrive
together, and each brings a container: a **mail sink**, a **cache**, and a
**worker**.

| | |
| --- | --- |
| [**Email verification**](#emails) | a mailed confirmation link; an account cannot log in until it is clicked |
| [**Redis cache**](#redis-and-caching) | cache-aside on one route, invalidated on write |
| [**Rate limiting**](#middlewares) | a Redis-backed middleware on `/api/*`, plus an opt-in debug toolbar |
| [**Celery**](#celery) | a worker and beat, two daily tasks: the reader newsletter and an admin stats report |
| [**Roles**](#jwt-scopes-and-roles) | a `user`/`admin` Postgres enum, and the two things it gates |

Every published port ends in **10**, the module number — api **8010**, Postgres
**5410**, pgAdmin **5110**, Redis **6310**, Mailpit **8210**, Flower **5510** —
so modules 06 to 11 can all run at once.

Adding a test suite to exactly this app is [module11](../module11/).

---

## Start the project

```bash
cd module10/cnn-website
cp .env.example .env       # then set NEWS_API_KEY and SECRET_KEY
docker compose up --build --wait
```

Every command below runs from `cnn-website/`, next to `docker-compose.yaml`.
Two values have no defaults and the app will not boot without them:
`NEWS_API_KEY` (<https://newsapi.org/register>) and `SECRET_KEY`
(`openssl rand -hex 32`).

| Service | URL / address | Notes |
| --- | --- | --- |
| **App** | <http://localhost:8010> | `/docs` for Swagger UI, `/healthz` for liveness |
| **Mailpit** | <http://localhost:8210> | every email the app sends; SMTP on `:1010` |
| **pgAdmin** | <http://localhost:5110> | `admin@gmail.com` / `admin`, `db` preloaded |
| **Postgres** | `localhost:5410` | `admin` / `admin`, database `cnn` |
| **Redis** | `localhost:6310` | no UI — use `redis-cli` |
| **Flower** | <http://localhost:5510> | Celery's UI. Opt-in: `docker compose --profile debug up -d flower` |
| **Debug toolbar** | on every HTML page | opt-in: `DEBUG=true` in `.env` |

`worker` and `beat` have no address at all — nothing connects to them. They are
seen through their logs and through Flower.

**Registering mails a confirmation link, and an account cannot log in until that
link is clicked**, so Mailpit is part of the normal signup path in dev.

### Or run uvicorn on the host

```bash
docker compose up -d db redis mailpit    # just the backing services
uv sync && uv run alembic upgrade head
uv run uvicorn news:app --reload         # http://localhost:8000
```

The `.env` defaults (`localhost:5410`, `localhost:1010`, `localhost:6310`)
describe exactly this case; the `api` container overrides them to service names.

### Commands

```bash
docker compose up -d --wait               # start; --build after a Dockerfile change
docker compose logs -f api worker beat    # the three processes worth watching
docker compose down -v                    # stop and delete every volume

docker compose exec api alembic current   # 31dd488df6fe (head)
docker compose exec db psql -U admin -d cnn
docker compose exec redis redis-cli -n 0  # 0 cache, 1 broker, 2 results

# run either task now instead of waiting for the schedule
docker compose exec api python -c "
from news.tasks import send_newsletter, send_stats_report
print(send_newsletter.delay().get(timeout=120))
print(send_stats_report.delay().get(timeout=120))"
```

`worker` and `beat` gate on `api` being **healthy**, not on `db`, because only
one container may run `alembic upgrade head` — waiting for a healthy api is
waiting for the migration it already ran.

---

## JWT, scopes and roles

[news/security.py](cnn-website/news/security.py) — HS256 via `python-jose`, bcrypt via
passlib, one `AuthService` singleton that routes depend on through bound methods.
`bcrypt` is pinned `<4.1`: passlib 1.7.4 probes it with a fixed 74-byte test hash
expecting silent truncation, and 4.1 raises instead.

### Two token kinds, told apart by `scope`

Both carry the same three claims — `sub`, `scope`, `exp` — signed by the same key
in the same place (`_create_token`). Only `scope` differs:

| `scope` | Made by | Accepted by | Lifetime |
| --- | --- | --- | --- |
| `access_token` | `/api/auth/login` | `get_current_user`, i.e. every gated route | `ACCESS_TOKEN_EXPIRE_MINUTES` (60) |
| `verification_token` | signup / resend, emailed | `confirmed_email` only | `VERIFICATION_TOKEN_EXPIRE_MINUTES` (60) |

**The scope check is the point.** Without it the link mailed at signup would be a
usable bearer token for the account it was meant to verify.

```bash
curl -s "$BASE/api/auth/confirmed_email/$TOKEN"          # 401 Invalid scope for token
curl -s "$BASE/api/auth/me" -H "Authorization: Bearer $VERIFY_TOKEN"
                                                          # 401 Could not validate credentials
```

Note the deliberately different codes in `decode_verification_token`: **422** for
a token this app did not sign or that expired, **401** for a well-signed token of
the wrong kind.

### Two ordering decisions

- **`login` checks the password before `confirmed`.** The other order would
  answer "is this address registered but unconfirmed?" for anyone who asks.
- **`request_email` replies identically** whether or not the address exists — it
  needs no credentials, so "no such user" would be a way to test addresses.

### Roles

`users.role` is a native Postgres enum (`user_role`) defaulting to `user`. There
is no endpoint that grants it — you promote by hand:

```bash
docker compose exec db psql -U admin -d cnn \
  -c "UPDATE users SET role = 'admin' WHERE email = 'you@example.com';"
```

An enum rather than a `String` precisely *because* it is edited by hand: the
database rejects a typo (`'admni'`) instead of letting it silently mean "not an
admin". Every endpoint is available to `role = 'user'`; the role gates exactly
two things — `GET /api/stats`, and who receives the daily stats report.

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/stats"                                    # 401
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/stats" -H "Authorization: Bearer $TOKEN"  # 403
```

**401 means "I don't know who you are", 403 means "I know, and no".** The role is
read from the database on every request, so a promotion takes effect immediately
— the existing token keeps working and picks up the new role.

---

## Emails

Three emails, all through **fastapi-mail** over SMTP, all landing in Mailpit in
dev. They differ in *who* sends them, which is the interesting part:

| Email | Sent by | Trigger |
| --- | --- | --- |
| verification link | the **web process**, as a `BackgroundTask` | `POST /api/auth/register`, or `request_email` |
| newsletter | the **Celery worker** | `send_newsletter`, 08:00 UTC |
| stats report | the **Celery worker** | `send_stats_report`, 07:00 UTC |

That split matters twice. A `BackgroundTask` dies with the web process and cannot
be scheduled or retried — the whole argument for the worker. And a worker has no
request, so it cannot build links from `request.base_url` the way the
verification mail does; hence `PUBLIC_BASE_URL`.

Templates in [news/templates/email/](cnn-website/news/templates/email/) render through
fastapi-mail's **own** Jinja environment, not Starlette's, so `url_for` is
unavailable and every link is built from a `host` string passed in by the caller.

### The verification flow

1. `POST /api/auth/register` creates the row, calls
   `background_tasks.add_task(send_verification_email, …)` and returns **201**.
2. The task runs **after the response is sent** — which is also after `get_db`'s
   teardown has committed, so the row the link refers to is durable before the
   link exists.
3. The link points at `/verify-email?token=…`, a *page*, not the API. Its JS
   calls `GET /api/auth/confirmed_email/{token}`, which flips `users.confirmed`.
4. Confirming is **idempotent** — a link clicked twice, or prefetched by a mail
   client and then clicked, reports success both times.

**The verification mail swallows SMTP failures; the worker's mail does not.**
`send_verification_email` catches `ConnectionErrors` and logs, because it runs
after the response has already gone out — there is no one left to tell, and
`request_email` exists to recover. The worker's sends raise, so the task can
count `{'sent': N, 'failed': M}`.

```bash
# end to end, in the shell
B=http://localhost:8010; M=http://localhost:8210
curl -s -X POST $B/api/auth/register -H 'Content-Type: application/json' \
  -d '{"username":"grace","email":"grace@example.com","password":"supersecret123"}'
# {... "confirmed": false}

curl -s -X POST $B/api/auth/login -d 'username=grace@example.com&password=supersecret123'
# {"detail":"Email is not verified"}

# pull the token out of the newest message -- poll, don't sleep a guess
MID=$(curl -s "$M/api/v1/search?query=grace@example.com" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["messages"][0]["ID"])')
TOK=$(curl -s "$M/api/v1/message/$MID" \
  | python3 -c 'import sys,json,re; print(re.search(r"token=([\w.-]+)", json.load(sys.stdin)["HTML"]).group(1))')

curl -s $B/api/auth/confirmed_email/$TOK    # {"message":"Email confirmed"}
curl -s $B/api/auth/confirmed_email/$TOK    # {"message":"Your email is already confirmed"}
```

To point at a real provider instead of Mailpit, set `MAIL_SERVER`, `MAIL_PORT`,
credentials, and `MAIL_STARTTLS=true` / `MAIL_USE_CREDENTIALS=true` /
`MAIL_VALIDATE_CERTS=true`.

---

## Redis and caching

[news/cache.py](cnn-website/news/cache.py) — cache-aside on exactly one route,
`GET /api/articles/{id}`.

- **Only one route is cached.** The listing is not: it varies by `q`, `page` and
  `per_page`, so it would need a key per combination and invalidation across all
  of them.
- **Writes invalidate; the TTL is a backstop.** `save_article()` calls
  `invalidate_article()` only when `session.is_modified()` says a field actually
  changed, so re-fetching an unchanged story is a no-op.
- **A cache failure is never a request failure.** Every `RedisError` is logged
  and swallowed, and a miss just goes to Postgres. `RuntimeError` is caught
  alongside it: a pooled connection belongs to the loop that opened it, and the
  Celery tasks close theirs, so reuse raises "Event loop is closed".
- **JSON, not pickle.** A cache entry is data. Pickle would execute whatever is
  in Redis, and a schema change would deserialise into a stale class.
- **Persistence is off, explicitly.** `redis-server --save ""` — the stock image
  ships `save 3600 1 …` and writes `/data/dump.rdb`, so even with no volume a
  restart reloads the snapshot. Everything here is re-fillable from Postgres.

```bash
A=12   # some article id
docker compose exec redis redis-cli -n 0 DEL "article:$A"
curl -s -o /dev/null "$BASE/api/articles/$A" -H "Authorization: Bearer $TOKEN"
docker compose exec redis redis-cli -n 0 TTL "article:$A"    # 300
docker compose exec redis redis-cli -n 0 GET "article:$A"
```

---

## Middlewares

[news/middleware.py](cnn-website/news/middleware.py) owns the whole stack, and
`install(app)` is the one call `main.py` makes. **Order is load-bearing.**

| order | middleware | applies to |
| --- | --- | --- |
| outermost | `rate_limit` | `/api/*` only |
| inner | `DebugToolbarMiddleware` | every HTML page, only when `DEBUG=true` |

Starlette's `add_middleware` inserts at position 0, so **the last one registered
is the outermost**. `install()` adds the toolbar first and the limiter second.
That is not cosmetic: a `429` never reaches the router, so `scope["endpoint"]` is
never set — and a toolbar outside the limiter would raise `KeyError: 'endpoint'`
building its panels, turning every rate-limited response into a **500**.

### The rate limiter

A **cooldown, not a quota**: one request per `RATE_LIMIT_WINDOW_SECONDS` per
client IP, held in Redis so it applies across worker processes.

```python
fresh = await cache.redis_client.set(f"rl:{client}", 1, ex=window, nx=True)
# NX means "only if absent" -- the key's own TTL is the window
```

- **`/api/*` only.** HTML pages, `/static` and `/healthz` are never limited — a
  healthcheck that can be rate-limited into failing is a liability.
- Over the limit → `429` with `Retry-After` and `{"detail": "Too many requests"}`.
- **`RATE_LIMIT_WINDOW_SECONDS=0` turns it off**, which is what `.env` ships:
  one page load fires two or three `/api` calls, so any window above 0 refuses
  all but the first and the page renders empty.
- **Fails open.** `RedisError` and `RuntimeError` are caught and the request is
  allowed through. The trade is explicit — someone who can kill Redis bypasses
  the limit, which beats Redis being a single point of failure for the API.

```bash
# set RATE_LIMIT_WINDOW_SECONDS=60 in .env, then:
docker compose up -d api --force-recreate --wait
for i in $(seq 1 8); do curl -s -o /dev/null -w '%{http_code} ' $BASE/api/articles; done
# 200 429 429 429 429 429 429 429
curl -s -i $BASE/api/articles | head -3      # retry-after: 60
docker compose exec redis redis-cli -n 0 KEYS 'rl:*'
```

The prefix must go on `.env`, not the shell — `env_file:` outranks the
environment for every variable Compose does not spell out (only `DEBUG` is).

**Two known limits.** A fixed window lets a client send at the end of one bucket
and again at the start of the next. And the key is `request.client.host`, which
behind a proxy is the *proxy's* address; a real deployment would read
`X-Forwarded-For`.

### Debug toolbar

`DEBUG=true` turns on FastAPI's debug mode and splices SQL, timing, a sampling
profiler and the resolved route into every HTML page before `</body>`. Nothing
appears on `/docs` or the JSON API — there is no `</body>` to splice into.
Development only: the panels show SQL with bound parameters and every request
header.

[news/debug.py](cnn-website/news/debug.py) carries two patches against upstream: route
matching (since FastAPI 0.137, `include_router()` appends an `_IncludedRouter`
with no `endpoint`, which the toolbar reads as "not a route"), and handing the
SQL panel this app's one engine instead of letting it discover one through a
`solve_dependencies()` signature that has since changed.

---

## Celery

[news/celery_app.py](cnn-website/news/celery_app.py) and
[news/tasks.py](cnn-website/news/tasks.py) — the app's second process type: work no
request is waiting for. `worker`, `beat` and `flower` run from the **same image**
as the api and differ only in their command, deliberately: a worker on a
different build from the app it shares a database with is how you get bugs that
only appear in the background.

| task | schedule | does |
| --- | --- | --- |
| `send_newsletter` | `crontab(hour=8)` | fetch headlines, save them, mail every confirmed subscriber |
| `send_stats_report` | `crontab(hour=7)` | mail per-source counts to every confirmed admin |

- **A crontab, not an interval.** An interval drifts from the clock on every
  restart; "every morning at 8" is a wall-clock statement.
- **Sync tasks over an async app.** The task body is `asyncio.run(_coroutine())`.
  Celery's worker is sync, the repository is async, and `asyncio.run` is the
  bridge — a fresh loop per task, which is also why `cache.py` catches
  `RuntimeError`.
- **Prefork, and connections that outlive their loop.** `--concurrency=2` forks,
  and every task builds a fresh event loop. A pooled connection belongs to the
  loop that opened it, so reuse across tasks raises "Event loop is closed" —
  which is why `cache.py` catches `RuntimeError` beside `RedisError`, and why the
  engine uses `pool_pre_ping=True`.
- **Redis databases 0, 1 and 2** — cache, broker, result backend. Kept apart so
  that flushing the cache does not delete every queued job and beat's schedule.
- **Exactly one beat replica, always.** Two beats reading one schedule both fire
  it, and every reader gets the newsletter twice. Beat's last-run file lives in a
  named volume outside the bind mount, so `down -v` is what makes a schedule fire
  immediately again.
- **No lifespan.** A worker never runs FastAPI's startup hooks, so anything the
  app sets up there would simply not exist here.

`beat_schedule` in this repo fires the newsletter **every minute** rather than at
08:00, so the task can actually be watched running; Mailpit delivers none of it.
The daily line is in the file, commented, right beside it.

```bash
docker compose logs -f worker beat
docker compose exec worker celery -A news.celery_app inspect registered
docker compose exec redis redis-cli -n 1 DBSIZE    # queued
docker compose exec redis redis-cli -n 2 DBSIZE    # results
```

**Subscribing** is an explicit opt-in, separate from `confirmed`:
`PUT /api/me/subscription` with `{"subscribed": true}` → `204`. The front page
carries the same toggle, hidden for a visitor with no token — the server has no
idea who is signed in, and the route needs a bearer header a plain `<form>`
cannot set.

---

## API reference

`/docs` has the interactive version. `$BASE` is `http://localhost:8010`, `$TOKEN`
an access token from `/api/auth/login`.

| method | path | notes |
| --- | --- | --- |
| `POST` | `/api/auth/register` | `201`, `confirmed: false`; mails the link |
| `POST` | `/api/auth/login` | **form-encoded**; the field is `username` but holds the email |
| `GET` | `/api/auth/me` | 🔒 |
| `GET` | `/api/auth/confirmed_email/{token}` | the emailed link's target; idempotent |
| `POST` | `/api/auth/request_email` | resend; always `200` |
| `GET` | `/api/articles` | 🔒 `?q=`, `?page=`, `?per_page=` |
| `GET` | `/api/articles/{id}` | 🔒 the only cached route |
| `POST` `DELETE` | `/api/articles/{id}/like` | 🔒 `204`, idempotent |
| `GET` | `/api/me/liked` | 🔒 newest like first |
| `PUT` | `/api/me/subscription` | 🔒 `{"subscribed": bool}` → `204` |
| `GET` | `/api/stats` | 🔒 **admins only**: `401` with no token, `403` with `role='user'` |
| `GET` | `/healthz` | `{"status":"ok","db":"ok"}`; `503` if the db is unreachable |

HTML pages, all `GET`, all shells that fetch their data client-side with the
token from `localStorage`: `/` (calls NewsAPI and upserts), `/article/{id}`,
`/login`, `/register`, `/verify-email?token=…`, `/liked`.

`q` searches what is *stored*; `/?q=` asks NewsAPI.

---

## Configuration

[news/settings.py](cnn-website/news/settings.py) is the single reader of `.env`, via
pydantic-settings. Secrets are `SecretStr` so they print as `**********`. Every
variable is commented in [.env.example](cnn-website/.env.example).

| Group | Variables |
| --- | --- |
| NewsAPI | `NEWS_API_KEY`\*, `NEWS_API_URL`, `DEFAULT_SOURCE`, `PAGE_SIZE` |
| Database | `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME` |
| Auth | `SECRET_KEY`\*, `ACCESS_TOKEN_EXPIRE_MINUTES`, `VERIFICATION_TOKEN_EXPIRE_MINUTES` |
| Cache | `REDIS_HOST`, `REDIS_PORT`, `ARTICLE_CACHE_TTL_SECONDS` |
| Limiter | `RATE_LIMIT_WINDOW_SECONDS` (0 disables) |
| Mail | `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`, `MAIL_FROM_NAME`, `MAIL_STARTTLS`, `MAIL_SSL_TLS`, `MAIL_USE_CREDENTIALS`, `MAIL_VALIDATE_CERTS` |
| Worker | `CELERY_BROKER_DB`, `CELERY_RESULT_DB`, `CELERY_RESULT_EXPIRES_SECONDS`, `PUBLIC_BASE_URL` |
| Schedule | `NEWSLETTER_HOUR`, `NEWSLETTER_MINUTE`, `NEWSLETTER_MAX_ARTICLES`, `STATS_REPORT_HOUR`, `STATS_REPORT_MINUTE` |
| Dev | `DEBUG` |

\* no default — the app will not start without it.

---

## Layout

```
news/
  main.py          FastAPI app, /healthz
  middleware.py    the middleware stack: rate limit + debug toolbar
  debug.py         the debug toolbar's two patches (DEBUG only)
  settings.py      all config, validated at import
  db.py            async engine, session, get_db dependency
  models.py        Role, Source, Article, User, LikedArticle
  repository.py    every query; invalidates the cache on write
  security.py      bcrypt + JWT, two token scopes, the admin gate
  mail.py          FastMail client + the three emails
  cache.py         cache-aside on Redis
  celery_app.py    the Celery app and the beat schedule
  tasks.py         send_newsletter, send_stats_report
  routers/         api.py, auth.py, newsletter.py, pages.py
  templates/       Jinja pages, plus email/ for the three message bodies
migrations/        Alembic (env.py is the async variant)
```

There is no `tests/` here on purpose: this module is the features, and
[module11](../module11/) is the same application with a test suite around it.

---

## After a code change

| Changed | Do this |
| --- | --- |
| Code under `news/` | Nothing — `--reload` picks it up through the bind mount |
| `news/tasks.py`, `news/celery_app.py` | `docker compose restart worker beat` — Celery has no `--reload` |
| `pyproject.toml` / `uv.lock` | `uv lock` on the host, then `docker compose restart api worker beat` |
| `news/models.py` | `uv run alembic revision --autogenerate`, **read it**, `upgrade head` |
| `Dockerfile` | `docker compose up -d --build api worker beat` |
| `.env` | `docker compose up -d --force-recreate <service>` — a restart keeps the old environment |

No `--build` for a dependency change: `pyproject.toml` and `uv.lock` arrive
through the bind mount and the start command re-runs `uv sync --frozen`.

```bash
docker compose down -v      # drops the Postgres volume too -- schema and data gone
docker compose up --build --wait
```

`-v` also clears beat's schedule volume, which is how you make a schedule fire
immediately again rather than waiting out its interval.

📋 Topic list: **[AGENDA.md](AGENDA.md)**
