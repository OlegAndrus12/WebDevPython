# cnn-website

An async FastAPI news reader on [newsapi.org](https://newsapi.org). Postgres
via SQLAlchemy `asyncio` + Alembic, and on top of that:

|                                                              |                                                                                     |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------- |
| [**JWT auth**](#jwt)                                    | bcrypt + HS256 bearer tokens, two token scopes, a`user`/`admin` role            |
| [**Email verification**](#emails)                       | a mailed confirmation link; an account cannot log in until it is clicked            |
| [**Redis cache**](#redis-and-caching)                   | cache-aside on one route, invalidated on write                                      |
| [**Celery**](#celery-the-worker-beat-and-the-two-tasks) | a worker and beat, two daily tasks: the reader newsletter and an admin stats report |
| [**Middlewares**](#middlewares)                         | a Redis-backed rate limit on`/api/*`, and an opt-in debug toolbar                 |

Every published port in this module ends in **10**, the module number —
api **8010**, Postgres **5410**, pgAdmin **5110**, Redis **6310**, Mailpit
**8210**, Flower **5510** — so modules 06 to 11 can all run at the same time.

Adding a test suite to exactly this app is [module11](../module11/).

---

## Start the project

```bash
cd module10/cnn-website
cp .env.example .env       # then set NEWS_API_KEY and SECRET_KEY
docker compose up --build --wait
```

Every command in this README runs from `cnn-website/`, next to
`docker-compose.yaml`.

Two values have no defaults and the app will not boot without them:

| Variable         | How to get one                                                                                      |
| ---------------- | --------------------------------------------------------------------------------------------------- |
| `NEWS_API_KEY` | https://newsapi.org/register — the free plan allows 100 requests/day, and`/` spends one per load |
| `SECRET_KEY`   | `openssl rand -hex 32`                                                                            |

Everything else has a working default describing the containers in
[docker-compose.yaml](cnn-website/docker-compose.yaml). See [Configuration](#configuration).

**Registering mails a confirmation link, and an account cannot log in until
that link is clicked** — so http://localhost:8210 is part of the normal signup
path in dev, not just somewhere to look when something breaks.

### Or run uvicorn on the host

```bash
docker compose up -d db redis mailpit    # just the backing services
uv sync
uv run alembic upgrade head
uv run uvicorn news:app --reload         # http://localhost:8000
```

The `.env` defaults (`localhost:5410`, `localhost:1010`, `localhost:6310`)
describe exactly this case; the `api` container overrides them to service
names (`db`, `mailpit`, `redis`).

---

## Services

| Service                 | URL / address         | Notes                                                               |
| ----------------------- | --------------------- | ------------------------------------------------------------------- |
| **App**           | http://localhost:8010 | `/docs` for Swagger UI, `/healthz` for liveness                 |
| **Mailpit**       | http://localhost:8210 | Every email the app sends. SMTP on`:1010`                         |
| **pgAdmin**       | http://localhost:5110 | `admin@gmail.com` / `admin`, `db` connection preloaded        |
| **Postgres**      | `localhost:5410`    | `admin` / `admin`, database `cnn`                             |
| **Redis**         | `localhost:6310`    | No UI — use`redis-cli` (below)                                   |
| **Flower**        | http://localhost:5510 | Celery's UI. Opt-in:`docker compose --profile debug up -d flower` |
| **Debug toolbar** | on every HTML page    | Opt-in:`DEBUG=true` in `.env` ([below](#debug-toolbar))          |

Two of the services have no address at all, because nothing connects to them:
**`worker`** runs the Celery tasks and **`beat`** schedules them. They are seen
through their logs and through Flower, not through a port.

Container names are all prefixed `cnn10_` (`cnn10_api`, `cnn10_postgres`,
`cnn10_redis`, `cnn10_mailpit`, `cnn10_pgadmin`, `cnn10_worker`,
`cnn10_beat`, `cnn10_flower`), and the Compose project
is `cnn10` — set explicitly in [docker-compose.yaml](cnn-website/docker-compose.yaml)
because Compose otherwise derives it from the directory name, which
`../cnn-website/` shares.

---

## Commands

Everything you need, in one place. Details for each are in the sections below.

### The stack

```bash
cp .env.example .env                      # then set NEWS_API_KEY and SECRET_KEY
docker compose up --build --wait          # db, api, redis, worker, beat, mailpit, pgadmin
docker compose --profile debug up -d flower   # opt-in Celery UI on :5510
docker compose ps                         # what is up, and healthy
docker compose logs -f api                # follow one service
docker compose logs -f worker beat        # or several
docker compose restart api                # after a settings/dependency change
docker compose up -d --force-recreate api # after an .env change
docker compose down                       # stop, keep the data
docker compose down -v --remove-orphans   # stop and wipe volumes (schema, beat schedule)
```

`worker` and `beat` gate on `api` being **healthy**, not on `db`, because only
one container may run `alembic upgrade head` — waiting for a healthy api is
waiting for the migration it already ran.

### Migrations

```bash
docker compose exec api alembic current            # 31dd488df6fe (head)
docker compose exec api alembic history            # the chain
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1

uv run alembic revision --autogenerate -m "what changed"   # then READ the file
```

### Database

```bash
docker compose exec db psql -U admin -d cnn                # interactive
docker compose exec db psql -U admin -d cnn -c '\dt'       # tables
docker compose exec db psql -U admin -d cnn -c '\d users'  # columns

docker compose exec db psql -U admin -d cnn \
  -c "SELECT id, username, email, confirmed, subscribed, role FROM users;"

docker compose exec db psql -U admin -d cnn \
  -c "UPDATE users SET role = 'admin' WHERE email = 'you@example.com';"
```

Or pgAdmin at http://localhost:5110 (`admin@gmail.com` / `admin`) — the `db`
server is preloaded, and `users.role` renders as a dropdown.

### Redis — three databases

```bash
docker compose exec redis redis-cli -n 0 KEYS 'article:*'   # 0 = the cache
docker compose exec redis redis-cli -n 0 GET article:12
docker compose exec redis redis-cli -n 0 TTL article:12
docker compose exec redis redis-cli -n 0 --scan --pattern 'rl:*'   # rate-limit counters
docker compose exec redis redis-cli -n 0 FLUSHDB            # force every read to miss

docker compose exec redis redis-cli -n 1 DBSIZE             # 1 = the Celery broker
docker compose exec redis redis-cli -n 2 DBSIZE             # 2 = task results

docker compose exec redis redis-cli MONITOR                 # every command, live
```

### Celery

```bash
docker compose exec worker celery -A news.celery_app inspect registered
docker compose exec worker celery -A news.celery_app inspect active
docker compose exec worker celery -A news.celery_app inspect scheduled

docker compose restart worker beat        # Celery has no --reload
```

### Triggering the two tasks by hand

Both tasks are scheduled daily, so you will almost always want to fire one now
instead. Any of the containers built from this image can do it — `api`,
`worker` or `beat` — because they all have the same code and the same broker
URL. Using `api`:

```bash
# enqueue it: returns immediately with a task id, the WORKER runs it
docker exec -it cnn10_api celery -A news.celery_app call news.tasks.send_newsletter
docker exec -it cnn10_api celery -A news.celery_app call news.tasks.send_stats_report
# -> 2dc01ff5-a769-43ed-bebc-73a049f79c1f

docker compose logs -f worker      # watch it actually run
```

The same thing from Python, which also gets you the task id and the result:

```bash
# enqueue, then wait for the worker's return value via the result backend
docker exec -it cnn10_api python -c "
from news.tasks import send_newsletter
r = send_newsletter.delay()
print(r.id, r.get(timeout=60))
"
# -> ea4362d7-... {'articles': 10, 'sent': 2, 'failed': 0}
```

**Or skip Celery entirely and run the task in this container**, synchronously.
Nothing is queued, no worker is involved, and the traceback comes straight
back to your terminal — which is the one you want when a task is broken:

```bash
docker exec -it cnn10_api python -c "
from news.tasks import send_newsletter
print(send_newsletter())
"
# -> {'articles': 10, 'sent': 2, 'failed': 0}

docker exec -it cnn10_api python -c "
from news.tasks import send_stats_report
print(send_stats_report())
"
# -> {'sent': 2, 'failed': 0}
```

Note what each form proves. `.delay()` and `celery call` test the **whole
path** — broker, worker, prefork, the crontab's task name — and a typo in the
task name fails silently into an unroutable queue. The direct call tests only
the **task body**, in a fresh process where `asyncio.run` has no loop to
collide with. If the direct call works and `.delay()` does not, the problem is
Celery's plumbing, not your code.

Substitute `cnn10_worker` for `cnn10_api` above and everything behaves the
same, except the direct call then runs inside the worker container. Use
`docker compose exec worker …` instead of `docker exec -it cnn10_worker …`
if you prefer service names to container names.

### Mail

```bash
open http://localhost:8210                                   # Mailpit's UI
curl -s 'http://localhost:8210/api/v1/messages?limit=5'      # list
curl -s http://localhost:8210/api/v1/message/<ID>            # one message
curl -s http://localhost:8210/api/v1/message/<ID>/raw        # headers included
curl -X DELETE http://localhost:8210/api/v1/messages         # clear the inbox
```

### The app

```bash
docker compose exec api alembic current
docker compose exec api python -c "from news.settings import settings; print(settings.database_url)"
curl -s http://localhost:8010/healthz          # {"status":"ok","db":"ok"}
open http://localhost:8010/docs                # Swagger, with an Authorize button
```

The venv is at **`/opt/venv`**, not `/app/.venv` — deliberately outside the
bind mount so the host's venv cannot shadow it. It is first on `PATH`, so
`alembic`, `uvicorn` and `celery` all resolve bare.

---

## Checking it manually

A single pass that exercises every subsystem. `$BASE` is
`http://localhost:8010` throughout.

```bash
BASE=http://localhost:8010
```

**1. The stack is up.**

```bash
docker compose ps                  # every service running, api/db/redis healthy
curl -s $BASE/healthz              # {"status":"ok","db":"ok"}
```

**2. Register — and watch the verification mail arrive.**

```bash
curl -s -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"username":"ann","email":"ann@cnnreader.example","password":"hunter2hunter2"}'
# 201, and {"confirmed": false}

# login is refused until the address is confirmed
curl -s -X POST "$BASE/api/auth/login" \
  -d 'username=ann@cnnreader.example&password=hunter2hunter2'
# 401 {"detail":"Email is not verified"}
```

Open http://localhost:8210, click the link — or do it headlessly:

```bash
ID=$(curl -s 'http://localhost:8210/api/v1/messages?limit=1' | python3 -c 'import sys,json;print(json.load(sys.stdin)["messages"][0]["ID"])')
VT=$(curl -s "http://localhost:8210/api/v1/message/$ID" | python3 -c 'import sys,json,re;print(re.search(r"verify-email\?token=([\w.-]+)",json.load(sys.stdin)["HTML"]).group(1))')
curl -s "$BASE/api/auth/confirmed_email/$VT"      # {"message":"Email confirmed"}
```

**3. Log in and read the API.**

```bash
TOKEN=$(curl -s -X POST "$BASE/api/auth/login" \
  -d 'username=ann@cnnreader.example&password=hunter2hunter2' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s "$BASE/api/auth/me" -H "Authorization: Bearer $TOKEN"
curl -s "$BASE/api/articles?per_page=2" -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/articles"     # 401, no token
```

**4. The cache — a miss, then a hit.**

```bash
docker compose exec redis redis-cli -n 0 FLUSHDB
curl -s -o /dev/null -w 'miss %{time_total}s\n' "$BASE/api/articles/1" -H "Authorization: Bearer $TOKEN"
curl -s -o /dev/null -w 'hit  %{time_total}s\n' "$BASE/api/articles/1" -H "Authorization: Bearer $TOKEN"
docker compose exec redis redis-cli -n 0 GET article:1
```

**5. The role gate.**

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/stats" -H "Authorization: Bearer $TOKEN"   # 403
docker compose exec db psql -U admin -d cnn \
  -c "UPDATE users SET role='admin' WHERE email='ann@cnnreader.example';"
curl -s "$BASE/api/stats" -H "Authorization: Bearer $TOKEN"                                    # 200
```

The same token now works — the role is read from the database per request, so
no re-login is needed.

**6. Subscribe, then run the newsletter by hand.**

```bash
curl -s -X PUT "$BASE/api/me/subscription" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"subscribed":true}'      # 204

curl -X DELETE http://localhost:8210/api/v1/messages
docker compose exec worker celery -A news.celery_app call news.tasks.send_newsletter
docker compose logs --tail=10 worker
# "10 articles to announce to 1 subscribers" / "newsletter sent to 1 subscribers, 0 failed"
```

The digest is in Mailpit. Run it again and it sends again — nothing tracks what
has already gone out.

**7. The admin stats report.**

```bash
docker compose exec worker celery -A news.celery_app call news.tasks.send_stats_report
docker compose logs --tail=10 worker
# "25 articles from 12 sources, reporting to 1 admins"
```

The table in that email is built from the same numbers `GET /api/stats`
returned in step 5.

**8. The rate limit.**

```bash
for i in $(seq 1 70); do
  curl -s -o /dev/null -w '%{http_code} ' "$BASE/api/articles?per_page=1" \
    -H "Authorization: Bearer $TOKEN"
done; echo
```

Sixty `200`s then `429`s — but only if all 70 land inside one 60-second bucket,
so run them quickly or lower `RATE_LIMIT_REQUESTS` first (see
[The rate limiter](#the-rate-limiter)).

**9. Beat, without waiting for tomorrow.**

```bash
printf 'NEWSLETTER_HOUR=%s\nNEWSLETTER_MINUTE=%s\n' $(date -u +%H) $(( $(date -u +%M) + 1 )) >> .env
docker compose up -d --force-recreate beat worker
docker compose logs -f beat        # "Scheduler: Sending due task newsletter"
```

Take those two lines back out of `.env` afterwards.

---

## Migrations

Alembic owns the schema. There is deliberately no `create_all()` anywhere in
the app — [news/db.py](cnn-website/news/db.py) only builds the engine.

**They run automatically.** The `api` service's command chains three steps with
`&&`, so a failure stops the container rather than serving against the wrong
schema:

```
uv sync --frozen --no-install-project && alembic upgrade head && uvicorn news:app ...
```

Current chain (`alembic history`):

```
759161cd8fb3  create sources and articles
b773fddbe615  remove fetched_at
d37028d90694  add users and liked_articles
c0bc5faeef11  add users.confirmed          <- head
```

### Commands

```bash
# where the database is now
docker compose exec api alembic current

# apply / roll back
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1

# print the SQL without connecting to anything
docker compose exec api alembic upgrade head --sql
```

### Generating a new migration

```bash
# 1. edit news/models.py
# 2. autogenerate against the live database
docker compose exec api alembic revision --autogenerate -m "add whatever"
# 3. READ migrations/versions/<new>.py before trusting it
# 4. apply
docker compose exec api alembic upgrade head
```

The new file appears on the host too — [docker-compose.yaml](cnn-website/docker-compose.yaml)
bind-mounts `.:/app`.

Autogenerate is a diff of `news/models.py` against the live schema, not a
source of truth. It reliably misses table/column *renames* (it emits a drop
plus an add, which loses the data) and server-side defaults on existing rows.
[migrations/env.py](cnn-website/migrations/env.py) sets `compare_type=True` and
`compare_server_default=True`, so a changed column type or default *is*
detected — those are off by default in Alembic.

Postgres has transactional DDL, so a migration that fails halfway rolls back
whole and the database stays on the previous revision.

---

## Debug toolbar

django-debug-toolbar's shape, for FastAPI. `DEBUG=true` in `.env`, then
`docker compose restart api` — no `--build`, since the compose command runs
`uv sync --frozen` first and `fastapi-debug-toolbar` is in the `dev`
dependency group, which `uv sync` installs by default.

Load http://localhost:8010/ and the handle sits at the right-hand edge:

| Panel                                                    | What it answers                                                                                                                              |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| **SQLAlchemy**                                     | Every statement the request ran, with parameters and timing.`/` shows 23 — the N+1 in `save_articles` is not subtle once you can see it |
| **Time**                                           | CPU and wall clock, also emitted as a`Server-Timing` header so the browser's network tab shows it                                          |
| **Profiling**                                      | A pyinstrument sample of the call tree                                                                                                       |
| **Request**                                        | The resolved endpoint, path params, cookies                                                                                                  |
| **Routes**                                         | The whole route table, with the match for this request                                                                                       |
| **Versions**, **Headers**, **Logging** | As they sound                                                                                                                                |

It appears only on the HTML pages, because it works by splicing itself in
before `</body>` — `/docs` and the whole `/api/*` surface have no `</body>`.
JSON responses instead carry a `dtRefresh` cookie, which updates the panels of
the last HTML page you had open.

`DEBUG=false` (the default) removes all of it: no middleware, no
`/_debug_toolbar/*` routes, and the pages go back out byte-for-byte as before.
Keep it that way outside development — the panels show SQL with its bound
parameters, every request header, and the full route table.

It is installed by [news/middleware.py](cnn-website/news/middleware.py)'s `install()`, not
by `main.py`, and it is registered **before** the rate limiter so that it ends
up *inside* it. [Middlewares](#middlewares) explains why that order is not
optional.

### The two patches in `news/debug.py`

The package's last release is May 2024, and FastAPI has moved twice since in
ways that break it. Both fixes live in [news/debug.py](cnn-website/news/debug.py):

1. **The SQL panel found no session.** It discovers your engine by re-solving
   the route's dependencies through `solve_dependencies()`, which now requires
   an `embed_body_fields` argument and returns a dataclass instead of a tuple
   — a `TypeError` on every request. This app has exactly one engine, so
   `add_engines()` is overridden to hand it over directly and skip the
   discovery. (It registers `engine.sync_engine`: SQLAlchemy's event system
   does not accept an `AsyncEngine`.)
2. **The toolbar rendered on nothing.** Its route lookup scans `app.routes`
   for a match carrying an `endpoint`. Since FastAPI 0.137, `include_router()`
   no longer copies routes onto the app — it appends one `_IncludedRouter`
   wrapper that delegates matching to the router inside. The wrapper has no
   `endpoint`, so the lookup concluded "not a route" and declined to render.
   Every route here arrives through `include_router`, so that was all of them.
   The replacement descends into `original_router` instead.

Neither one touches migrations, even though `migrations/env.py` imports
`news.models` and so builds the app inside every `alembic` process:
`add_middleware()` only appends to a list, and Starlette does not construct
the middleware until the first request, which never comes there.

---

## Inspecting each container

```bash
docker compose ps                    # what's up, and health status
docker compose logs -f api           # follow one service
docker compose logs --tail=50 api    # last 50 lines
```

### api

```bash
docker compose exec api bash
docker compose exec api python -c "from news.settings import settings; print(settings.database_url)"
docker compose exec api alembic current
curl -s http://localhost:8010/healthz     # {"status":"ok","db":"ok"}
```

The venv is at **`/opt/venv`**, not `/app/.venv` — deliberately outside the
bind mount so the host's venv can't shadow it. It's first on `PATH`, so
`alembic` and `uvicorn` resolve bare.

### db

```bash
docker compose exec db psql -U admin -d cnn

# straight to a query
docker compose exec db psql -U admin -d cnn -c '\dt'
docker compose exec db psql -U admin -d cnn -c 'SELECT id, username, email, confirmed FROM users;'
docker compose exec db psql -U admin -d cnn -c 'SELECT COUNT(*) FROM articles;'
```

Or use pgAdmin at http://localhost:5110 — the `db` server is preloaded from
[pgadmin/servers.json](cnn-website/pgadmin/servers.json) with the password supplied from a
`.pgpass` copied into place by the entrypoint, so there's no dialog to fill in.

### redis

```bash
docker compose exec redis redis-cli

docker compose exec redis redis-cli KEYS 'article:*'
docker compose exec redis redis-cli GET article:12
docker compose exec redis redis-cli TTL article:12
docker compose exec redis redis-cli INFO stats | grep keyspace
docker compose exec redis redis-cli FLUSHALL      # force every read to miss
```

To watch commands as they happen, run `MONITOR` yourself — Redis never logs
commands at any log level, so this is the only way to see them:

```bash
# simplest: inside the redis container, where redis-cli defaults to localhost:6379
docker compose exec redis redis-cli MONITOR

# or spelled out with the in-network host and port
docker compose exec redis redis-cli -h redis -p 6379 MONITOR

# from the host, via the published port (needs redis-cli installed locally)
redis-cli -h localhost -p 6310 MONITOR

# or a throwaway container on the compose network, no local redis-cli needed
docker compose run --rm --no-deps redis redis-cli -h redis -p 6379 MONITOR
```

It streams until you stop it with `Ctrl-C`. Leave it running in one terminal
and hit `GET /api/articles/{id}` twice from another: the miss shows a `GET`
then a `SET`, the hit shows only the `GET`.

`MONITOR` costs real throughput on a busy server — fine for poking at a dev
stack, never something to leave attached in production.

### mailpit

Browse http://localhost:8210, or use its API:

```bash
curl -s 'http://localhost:8210/api/v1/messages?limit=5'   # list
curl -s http://localhost:8210/api/v1/message/<ID>          # one message, incl. HTML
curl -X DELETE http://localhost:8210/api/v1/messages       # clear the inbox
```

⚠️ Mailpit here is configured with **no `--database` and no volume**, so every
captured message is lost on restart, and `--max` defaults to 500 messages
(oldest pruned first). Fine for dev; see [Emails](#emails) if you want it
durable.

---

## API reference

`GET /docs` has the interactive version. Below, `$BASE` is
`http://localhost:8010` and `$TOKEN` is an access token from `/api/auth/login`.

```bash
BASE=http://localhost:8010
```

### Auth

```bash
# register -> 201, "confirmed": false. Mails a verification link.
curl -s -X POST "$BASE/api/auth/register" \
  -H 'Content-Type: application/json' \
  -d '{"username":"grace","email":"grace@example.com","password":"supersecret123"}'

# login -> {"access_token":"...","token_type":"bearer"}
# NOTE: form-encoded, not JSON, and the field is `username` even though it
# holds the email -- that's OAuth2PasswordRequestForm's fixed shape.
# 401 "Email is not verified" until the link is clicked.
TOKEN=$(curl -s -X POST "$BASE/api/auth/login" \
  -d 'username=grace@example.com&password=supersecret123' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')

# who am I -> 200 UserOut
curl -s "$BASE/api/auth/me" -H "Authorization: Bearer $TOKEN"

# confirm an address (the target of the emailed link)
curl -s "$BASE/api/auth/confirmed_email/<verification-token>"

# resend the link -> always 200, same answer for an unknown address
curl -s -X POST "$BASE/api/auth/request_email" \
  -H 'Content-Type: application/json' -d '{"email":"grace@example.com"}'
```

### Articles

Every route here needs `Authorization: Bearer $TOKEN`, and `/api/stats`
additionally needs `role = 'admin'` — see [Roles](#roles).

```bash
# list stored articles, newest first
curl -s "$BASE/api/articles" -H "Authorization: Bearer $TOKEN"
curl -s "$BASE/api/articles?q=ukraine&page=2&per_page=5" -H "Authorization: Bearer $TOKEN"

# one article -- this is the only cached route
curl -s "$BASE/api/articles/12" -H "Authorization: Bearer $TOKEN"

# like / unlike -> 204 No Content
curl -s -X POST   "$BASE/api/articles/12/like" -H "Authorization: Bearer $TOKEN" -i
curl -s -X DELETE "$BASE/api/articles/12/like" -H "Authorization: Bearer $TOKEN" -i

# everything I've liked, newest like first
curl -s "$BASE/api/me/liked" -H "Authorization: Bearer $TOKEN"

# per-source counts -- admins only: 401 with no token, 403 with role='user'
curl -s "$BASE/api/stats" -H "Authorization: Bearer $TOKEN"
```

`q` searches what is *stored*, which is not what `/?q=` does — that one asks
NewsAPI. A story NewsAPI has never handed us isn't here.

### Newsletter

```bash
# one route, one method -- the body names the state to end up in -> 204
curl -s -X PUT "$BASE/api/me/subscription" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"subscribed":true}' -i

curl -s -X PUT "$BASE/api/me/subscription" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"subscribed":false}' -i
```

Subscribing is an explicit opt-in and separate from `confirmed`. See
[The worker and the newsletter](#celery-the-worker-beat-and-the-two-tasks).

The front page carries the same toggle as a form at the top of the content
area. It is rendered by `setupNewsletterForm()` in
[news/static/auth.js](cnn-website/news/static/auth.js) and stays hidden for a visitor with
no token — the server rendering the page has no idea who is signed in, and
`PUT /api/me/subscription` needs the bearer header a plain `<form>` cannot set.

### Ops and pages

```bash
curl -s "$BASE/healthz"          # {"status":"ok","db":"ok"}; 503 if db unreachable
```

HTML pages, all `GET`, all shells that fetch their data client-side with the
bearer token from `localStorage`:

| Path                       | Page                                                       |
| -------------------------- | ---------------------------------------------------------- |
| `/` (`?q=`)            | Front page.**Calls NewsAPI** and upserts the results |
| `/article/{id}`          | One stored article                                         |
| `/login`, `/register`  | Forms                                                      |
| `/verify-email?token=…` | Where the emailed link lands                               |
| `/liked`                 | The current user's liked list                              |

---

## JWT

[news/security.py](cnn-website/news/security.py) — one `AuthService`, and a module-level
singleton routes depend on via bound methods
(`Depends(auth_service.get_current_user)`).

- **HS256**, signed with `SECRET_KEY` via `python-jose`.
- Passwords are **bcrypt** via passlib. `bcrypt` is pinned `>=4.0.1,<4.1` in
  [pyproject.toml](cnn-website/pyproject.toml): passlib 1.7.4 probes bcrypt with a fixed
  74-byte test hash expecting a silent truncation, and bcrypt ≥ 4.1 raises
  instead, so `CryptContext(["bcrypt"])` fails on first use.
- The client stores the token in `localStorage` and sends it as a bearer
  header ([news/static/auth.js](cnn-website/news/static/auth.js)) — not a cookie, so the
  HTML pages and the JSON API authenticate the same way and there's no CSRF
  surface to guard.

### Two token kinds, told apart by `scope`

Both carry the same three claims — `sub` (the email), `scope`, `exp` — and are
signed by the same key in the same place (`_create_token`). Only `scope`
differs:

| `scope`              | Made by                  | Accepted by                                  | Default lifetime                           |
| ---------------------- | ------------------------ | -------------------------------------------- | ------------------------------------------ |
| `access_token`       | `/api/auth/login`      | `get_current_user`, i.e. every gated route | `ACCESS_TOKEN_EXPIRE_MINUTES` (60)       |
| `verification_token` | signup / resend, emailed | `confirmed_email` only                     | `VERIFICATION_TOKEN_EXPIRE_MINUTES` (60) |

**The scope check is the point.** Without it the link mailed out at signup
would be a usable bearer token for the very account it was meant to be
verifying. Each decoder rejects the other's tokens:

```bash
# an access token presented to the confirm endpoint
curl -s "$BASE/api/auth/confirmed_email/$TOKEN"
# 401 {"detail":"Invalid scope for token"}

# a verification token presented as a bearer token
curl -s "$BASE/api/auth/me" -H "Authorization: Bearer $VERIFY_TOKEN"
# 401 {"detail":"Could not validate credentials"}
```

Note the deliberately different status codes in `decode_verification_token`:
**422** for a token this app didn't sign or that expired, **401** for a
well-signed token of the wrong kind.

### Inspecting a token

The payload is signed, not encrypted, so you can read it with no secret. This
only decodes — it does *not* verify the signature, which is what
`get_current_user` actually checks:

```bash
echo "$TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool
# {"sub":"grace@example.com","scope":"access_token","exp":1757340000}
```

### Two ordering decisions worth knowing

- **`login` checks the password before `confirmed`**
  ([news/routers/auth.py:67](cnn-website/news/routers/auth.py#L67)). The other order would
  answer "is this address registered but unconfirmed?" for anyone who asks —
  an account-enumeration oracle. Here you need the password first.
- **`request_email` replies identically** whether or not the address exists
  ([news/routers/auth.py:104-115](cnn-website/news/routers/auth.py#L104-L115)), for the
  same reason: it needs no credentials, so "no such user" would be a way to
  test addresses against the user table.

### Roles

`users.role` is a **native Postgres enum** (`user_role`) with two values,
`user` and `admin`, defaulting to `user`. There is no endpoint that grants it:
you promote somebody by hand.

```bash
# in pgAdmin, users.role renders as a dropdown -- or from the shell:
docker compose exec db psql -U admin -d cnn \
  -c "UPDATE users SET role = 'admin' WHERE email = 'you@example.com';"

docker compose exec db psql -U admin -d cnn \
  -c "SELECT id, username, email, confirmed, subscribed, role FROM users;"
```

An enum rather than a `String`, precisely *because* it is edited by hand — the
database rejects a typo instead of letting it silently mean "not an admin":

```bash
docker compose exec db psql -U admin -d cnn -c "UPDATE users SET role='admni' WHERE id=1;"
# ERROR:  invalid input value for enum user_role: "admni"
```

**What the role gates.** Every endpoint is available to `role = 'user'` —
articles, likes, the newsletter toggle, all of it. The role exists for exactly
two things:

|                              |                                             |
| ---------------------------- | ------------------------------------------- |
| `GET /api/stats`           | `Depends(auth_service.get_current_admin)` |
| the daily stats report email | goes to confirmed admins only               |

`get_current_admin` calls `get_current_user` and then checks the role, and the
status codes are deliberately different:

```bash
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/stats"                              # 401
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/stats" -H "Authorization: Bearer $TOKEN"  # 403 if role='user'
curl -s "$BASE/api/stats" -H "Authorization: Bearer $ADMIN_TOKEN"                        # 200
```

**401 means "I don't know who you are", 403 means "I know, and no".** A 401
tells the client to go and get a better token, which is not the problem when
the token is fine and the account simply is not an admin.

The role is read from the database on every request, so a promotion takes
effect immediately — the existing token keeps working and picks up the new
role without a re-login.

---

## Emails

Three emails, all sent with **fastapi-mail** over SMTP, all landing in Mailpit
in dev. They differ in *who* sends them, which is the interesting part:

| Email             | Sent by                                           | Trigger                                           |
| ----------------- | ------------------------------------------------- | ------------------------------------------------- |
| verification link | the**web process**, as a `BackgroundTask` | `POST /api/auth/register`, or `request_email` |
| newsletter        | the**Celery worker**                        | `send_newsletter`, 08:00 UTC                    |
| stats report      | the**Celery worker**                        | `send_stats_report`, 07:00 UTC                  |

That split matters in two ways. A `BackgroundTask` dies with the web process
and cannot be scheduled or retried, which is the whole argument for the worker
([Celery](#celery-the-worker-beat-and-the-two-tasks)). And a worker has no
request, so it cannot build links from `request.base_url` the way the
verification mail does — hence `PUBLIC_BASE_URL`.

### The pieces

| File                                          | Role                                                                    |
| --------------------------------------------- | ----------------------------------------------------------------------- |
| [news/settings.py](cnn-website/news/settings.py)           | All`MAIL_*` config, validated at import                               |
| [news/mail.py](cnn-website/news/mail.py)                   | One module-level`FastMail`, built once, plus the three send functions |
| [news/templates/email/](cnn-website/news/templates/email/) | `verify_email.html`, `newsletter.html`, `stats_report.html`       |

Templates render through fastapi-mail's **own** Jinja environment, not
Starlette's — so `url_for` is unavailable and every link is built from a `host`
string passed in by the caller.

### The verification flow

1. `POST /api/auth/register` creates the user row, then calls
   `background_tasks.add_task(send_verification_email, …)` and returns **201**.
2. The task runs **after the response is sent** — which is also after
   `get_db`'s teardown has committed, so the row the link refers to is durable
   before the link exists. It needs no DB session of its own: two strings and a
   freshly signed token are enough.
3. `send_verification_email` signs a `verification_token`, renders the template,
   and hands the message to SMTP.
4. The link points at `/verify-email?token=…` — a *page*, not the API. Its JS
   calls `GET /api/auth/confirmed_email/{token}`, which flips `users.confirmed`.
   Keeping the API as the only thing that knows how confirmation works, and
   giving the reader a page instead of raw JSON.
5. Confirming is **idempotent** — a link clicked twice, or prefetched by a mail
   client and then clicked, reports success both times.

`host` in the template is `str(request.base_url)` passed in from the route: the
app doesn't know its own public URL, only the one the client just reached it on.
It already ends in a slash, hence `{{ host }}verify-email` with no separator.

### The verification mail swallows failures; the worker's mail does not

`send_verification_email` wraps `send_message` in `except ConnectionErrors` →
log and move on. The task runs after the response, so a raise would reach no
client anyway. The account exists either way and `request_email` can retry —
but note the consequence: **an unreachable SMTP server is invisible except in
the app log.**

The two worker emails deliberately do the opposite and **raise**, because
something is listening: the task counts the failure, logs the address, and
carries on to the next recipient, reporting `{'sent': N, 'failed': M}`.
Swallowing there would turn an undelivered newsletter into a silent success.

```bash
docker compose stop mailpit
docker compose exec worker celery -A news.celery_app call news.tasks.send_newsletter
docker compose logs --tail=5 worker    # "could not mail ..." / "0 subscribers, 1 failed"
docker compose start mailpit
```

A recipient whose send fails is skipped until the next scheduled run — there
is no per-recipient retry.

Two failure classes aren't caught even there. fastapi-mail renders the template
*before* opening the connection, and only the connect phase wraps its errors in
`ConnectionErrors` — so a Jinja error in the template, or an SMTP error mid-send,
propagates as a background-task traceback instead. Harmless against Mailpit
(it accepts everything); worth knowing against a real provider.

### End-to-end with curl

```bash
BASE=http://localhost:8010
MAILPIT=http://localhost:8210

# 1. register -- "confirmed": false
curl -s -X POST "$BASE/api/auth/register" -H 'Content-Type: application/json' \
  -d '{"username":"grace","email":"grace@example.com","password":"supersecret123"}'

# 2. wait for the mail. It is sent AFTER the response above, so it isn't there
#    the instant register returns -- poll, don't sleep a guess. This also gives
#    the register transaction time to commit; fire step 3 too fast and you get
#    "Invalid email or password" instead of the answer you want.
until [ "$(curl -s "$MAILPIT/api/v1/messages?limit=1" \
           | python3 -c 'import json,sys; print(json.load(sys.stdin)["total"])')" != "0" ]; do
  sleep 1
done

# 3. login is refused -- and not because of the password
curl -s -X POST "$BASE/api/auth/login" \
  -d 'username=grace@example.com&password=supersecret123'
# {"detail":"Email is not verified"}

# 4. pull the token out of the newest message
MSG_ID=$(curl -s "$MAILPIT/api/v1/messages?limit=1" | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["messages"][0]["ID"])')
LINK=$(curl -s "$MAILPIT/api/v1/message/$MSG_ID" | python3 -c \
  'import json,sys,re; print(re.search(r"href=\"([^\"]+verify-email[^\"]*)\"", json.load(sys.stdin)["HTML"]).group(1))')
VERIFY_TOKEN=${LINK##*token=}

# 5. confirm -- twice, to see it not error
curl -s "$BASE/api/auth/confirmed_email/$VERIFY_TOKEN"   # {"message":"Email confirmed"}
curl -s "$BASE/api/auth/confirmed_email/$VERIFY_TOKEN"   # {"message":"Your email is already confirmed"}

# 6. login now works
curl -s -X POST "$BASE/api/auth/login" \
  -d 'username=grace@example.com&password=supersecret123'
```

To watch a link expire, restart with `VERIFICATION_TOKEN_EXPIRE_MINUTES=0`,
register, and click through.

### Making Mailpit durable

The compose service keeps nothing (see the warning under
[mailpit](#mailpit)). To persist captured mail, give it a database and a volume:

```yaml
  mailpit:
    image: axllent/mailpit
    container_name: cnn10_mailpit
    environment:
      MP_DATABASE: /data/mailpit.db
      MP_MAX_MESSAGES: 0          # 0 = no limit (default is 500)
    volumes:
      - cnn10_mailpit_data:/data
```

…plus `cnn10_mailpit_data:` under the top-level `volumes:`.

### Pointing it at a real SMTP server

Nothing in the code is Mailpit-specific — that's only what the `MAIL_*`
defaults describe. Override them in `.env` (there's a commented Mailtrap block
in [.env.example](cnn-website/.env.example)) **and drop the `MAIL_SERVER`/`MAIL_PORT`
overrides from the `api` service** in
[docker-compose.yaml](cnn-website/docker-compose.yaml), or the compose values keep winning.

Against a real provider, set `MAIL_USE_CREDENTIALS=true`, exactly one of
`MAIL_STARTTLS` / `MAIL_SSL_TLS`, and `MAIL_VALIDATE_CERTS=true` — with certs
unvalidated, TLS buys you nothing.

---

## Redis and caching

[news/cache.py](cnn-website/news/cache.py) — cache-aside on `redis.asyncio`, so a lookup
awaits on the same event loop as the query it exists to avoid.

Keys are `article:<id>`, namespaced because a real Redis is rarely one app's.
Values are the JSON of a validated `ArticleOut`.

### Only `GET /api/articles/{id}` is cached

Not the list route. One row under one stable key invalidates cleanly, whereas a
list response is keyed by `q`/`page`/`per_page` and every article write would
have to fan out across every page it might appear on.

Read path in [news/routers/api.py:79-95](cnn-website/news/routers/api.py#L79-L95): look in
Redis → on a miss query Postgres → validate to `ArticleOut` → fill the key on
the way out.

A **404 is deliberately not cached**. Here it means "not fetched yet", and the
front page creates rows constantly — caching the absence would keep answering
404 for an article that now exists.

Note the ordering: `current_user` is a dependency, so the 401 fires *before* the
route body. A cache hit is still an authenticated read, never a way around the
gate.

### Writes invalidate; the TTL is only a backstop

`Repository.upsert_article` drops the key when a row actually changes
([news/repository.py:115-132](cnn-website/news/repository.py#L115-L132)) — and only then.
The check is `session.is_modified(...)`, asked *before* the flush, because
afterwards the session has reconciled and the history is gone. This matters
more than it looks: the front page re-saves its whole page of articles on every
load, so invalidating unconditionally would evict exactly the popular articles
on a timer and the cache would never serve a hit.

`ARTICLE_CACHE_TTL_SECONDS` (300) is the safety net for anything that misses
that path — including a `RedisError` during invalidation, which is logged and
swallowed and can leave a stale entry until it expires.

### A cache failure is never a request failure

Every function in `cache.py` catches `RedisError` and logs it. Redis being down
makes this app **slower, not broken** — the route falls through to Postgres,
which was always the only source of truth. That's also why the `api` service's
`depends_on` for `redis` is `service_started`, not `service_healthy`.

An entry that no longer parses (written by an older schema) is treated as a
miss and refilled, not as an error.

### JSON, not pickle

A pickled ORM object couples the cache's contents to the class definition —
change the model and every cached entry unpickles into the old shape. A
Pydantic model dumped to JSON round-trips through a schema change or fails
loudly, and is readable with `redis-cli GET`.

### Persistence is off, explicitly

```yaml
command: redis-server --save "" --appendonly no
```

The `redis:7-alpine` default config is *not* a cache config — it ships
`save 3600 1 300 100 60 10000` and writes `/data/dump.rdb`, so even with no
volume the snapshot lives in the container's filesystem and a
`docker compose restart` reloads it ("Done loading RDB, keys loaded: N" in the
logs). `--save ""` is what actually turns snapshotting off. `--appendonly no`
is already the default and is spelled out so both mechanisms are visibly
accounted for.

### Seeing it work

```bash
docker compose exec redis redis-cli FLUSHALL

curl -s -o /dev/null -w '%{time_total}\n' "$BASE/api/articles/12" -H "Authorization: Bearer $TOKEN"  # miss
curl -s -o /dev/null -w '%{time_total}\n' "$BASE/api/articles/12" -H "Authorization: Bearer $TOKEN"  # hit

docker compose exec redis redis-cli GET article:12
docker compose exec redis redis-cli TTL article:12
```

To take Redis out of the picture entirely, stop the container — every function
in `cache.py` swallows `RedisError`, so the app keeps serving from Postgres.

---

## Celery: the worker, beat, and the two tasks

This is the app's **second process type**. Everything before it ran inside a
request — even the verification email, which `BackgroundTasks` sends after the
response but still from the web process. A worker is different in the ways that
matter: it survives the request, it can be scheduled, it retries, and you can
watch it fail.

Three containers, one image (`build: .`, same as `api` — a worker running a
different build from the app it shares a database with is how you get bugs that
only happen in the background):

| service    | what it does                                                    |
| ---------- | --------------------------------------------------------------- |
| `worker` | runs tasks.`celery -A news.celery_app worker --concurrency=2` |
| `beat`   | schedules them, runs none itself                                |
| `flower` | the UI, behind`--profile debug`, on http://localhost:5510     |

A stack with a `beat` and no `worker` queues jobs forever and delivers nothing.

**Two scheduled tasks**, both daily, both defined in
[news/tasks.py](cnn-website/news/tasks.py) and both registered in
[news/celery_app.py](cnn-website/news/celery_app.py)'s `beat_schedule`:

| task                             | when      | what it does                               | who gets mail                  |
| -------------------------------- | --------- | ------------------------------------------ | ------------------------------ |
| `news.tasks.send_newsletter`   | 08:00 UTC | fetch headlines, save them, mail them      | `confirmed AND subscribed`   |
| `news.tasks.send_stats_report` | 07:00 UTC | the same numbers`GET /api/stats` returns | `confirmed AND role='admin'` |

An hour apart on purpose, so the two are not competing for the worker.

```bash
docker compose exec worker celery -A news.celery_app inspect registered
#  * news.tasks.send_newsletter
#  * news.tasks.send_stats_report
```

To fire either one now rather than waiting for its crontab, see
[Triggering the two tasks by hand](#triggering-the-two-tasks-by-hand).

### One task, three steps

There is a single periodic task, [`send_newsletter`](cnn-website/news/tasks.py). Each run
fetches the headlines, upserts them, and mails what it found — the fetch is a
*step of* the newsletter rather than a schedule of its own:

1. `news_api.top_headlines()`
2. `Repository.save_articles(payloads)`
3. keep the first `NEWSLETTER_MAX_ARTICLES` of them
4. recipients = `confirmed AND subscribed`
5. loop over them, sending each one the mail

**This does not replace the front page's own fetch.** `GET /` still calls
NewsAPI on every page load, exactly as it did before. The worker is additive.

### The schedule is a crontab, not an interval

`beat_schedule` accepts three kinds of value — a bare number of seconds, a
`timedelta`, or a `crontab(minute=, hour=, day_of_week=, day_of_month=, month_of_year=)`. This one runs **once a day at 08:00 UTC**
(`NEWSLETTER_HOUR` / `NEWSLETTER_MINUTE`):

```python
"schedule": crontab(hour=settings.newsletter_hour, minute=settings.newsletter_minute)
```

which beat reports as `<crontab: 0 8 * * * (m/h/dM/MY/d)>`.

A number of seconds would be the wrong tool for "every morning": the interval
is measured from the last run, so a restart shifts it and it drifts further
from the clock every time. A crontab is anchored to the clock instead — miss a
run and the next one is still at 08:00, not 24 hours after whenever the worker
last came up.

**It is one task, not a fan-out.** The whole job — fetch, save, and every
send — happens in a single `send_newsletter`. A per-recipient subtask would let
one dead address retry on its own, but it also means ids over JSON, a second
task to register, and re-reading rows the parent already had in hand. Not worth
it for a mailing list this size.

The one thing the loop does take care of: each send is wrapped, so a
`ConnectionErrors` for one address is logged and counted rather than abandoning
the subscribers after it. Those recipients are simply skipped until the next
scheduled run — there is no per-recipient retry. `autoretry_for` covers only
the NewsAPI fetch, which is the part that can fail before anyone has been
mailed.

### Every run mails whatever the fetch returned

There is no bookkeeping of what has already gone out. Each run takes the
headlines NewsAPI hands back, saves them, and mails that list — so a run
repeats stories the previous run already sent, because `top_headlines()`
barely moves between calls.

That is deliberate and it is the trade being made: the task is a page of
headlines on a schedule, not a diff. The alternative — a `newsletter_sent_at`
column stamped after each send — buys "only stories you have not seen" at the
cost of a column, an index, a migration, and a decision about whether to stamp
before or after the fan-out. Not worth it here.

Two consequences to be aware of:

* **Subscribers get the same stories more than once** when the news moves
  slower than the schedule. Once a day at 08:00 this is mild — a story that
  stays on the front page for two days goes out twice.
* **A re-run is not a no-op.** Calling the task twice by hand sends two
  emails. There is nothing to make it idempotent.

A worker killed mid-run is the other way to get duplicates: the task is
acknowledged early, so the subscribers already mailed stay mailed, and a manual
re-run mails them again.

### Subscribing

Explicit opt-in. `confirmed` says the address was proved to exist;
`subscribed` says its owner asked for this. Conflating them is how an app
starts mailing people who never agreed, which is why registration does not set
it and why the migration adding the column deliberately backfills `false` —
the exact opposite of the `confirmed` migration, which had to backfill `true`
to avoid locking existing accounts out.

```bash
curl -s -X PUT "$BASE/api/me/subscription" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"subscribed":true}'    # 204
curl -s "$BASE/api/auth/me" -H "Authorization: Bearer $TOKEN"     # "subscribed": true
```

**One `PUT`, not a `POST`/`DELETE` pair.** The body names the state to end up
in rather than an action to perform, so sending `subscribed: true` twice leaves
the same row as sending it once — a retried or duplicated request cannot flip
anybody back the wrong way, and the front-end toggle calls one URL either
direction. (The like/unlike pair in `api.py` does use two methods on one path;
this diverges from it deliberately, because a boolean on the user row is a
state to set, not a sub-resource to create and destroy.)

**That route is the only way out**, and it needs a bearer token like any other
account change. There is no one-click link in the email:
the footer points at the site and asks the reader to sign in and use the
toggle.

That is a deliberate trade, and it costs something. A link that works straight
from an inbox would need to carry its own credential in the URL — a third token
scope — and that URL then lives in the mail, in every server that relayed it,
and in whatever the reader forwards. Requiring a login means nothing
unsubscribable is sitting in anyone's mailbox.

The cost is real: no `List-Unsubscribe` / `List-Unsubscribe-Post` headers, so a
mail client's built-in unsubscribe button has nothing to call, and a reader who
cannot be bothered to log in has one easy option left — reporting the mail as
spam. For a list of any size, that is the trade to revisit.

### No lifespan

`main.py` has no `lifespan`. There is no httpx pool left to close — `news_api`
opens a client per call — and the Redis and SQLAlchemy pools are released by
the process exiting.

### Sync tasks over an async app

Every I/O helper in `news/` is a coroutine; a Celery task is a plain function.
The task bridges them with `asyncio.run`, which builds a fresh event loop per
call and closes it on the way out.

That has a consequence worth understanding, because it bites in production and
not in a first test. A pooled connection belongs to the event loop that opened
it. Keep a client at module scope and the second `asyncio.run` in the same
worker process reaches into its pool, finds a connection wired to the loop that
just closed, and raises:

```
Task news.tasks.send_newsletter[...] raised unexpected: RuntimeError('Event loop is closed')
  File "/app/news/news_api.py", line 47, in _get
  File "httpx/_client.py", line 1768, in get
```

This is not hypothetical — it failed a real run here, on the *second* task 16
seconds after the first. The stale connection is not reaped on a timer; it sits
in the pool until something tries to use it, so every other run fails.

Two fixes, one per client:

* **httpx** — [news_api.py](cnn-website/news/news_api.py) opens a client per call with
  `async with`, so nothing outlives the loop. Costs a handshake per call, which
  against one NewsAPI request is nothing.
* **redis** — [cache.py](cnn-website/news/cache.py) catches `RuntimeError` alongside
  `RedisError`. A connection on a dead loop is a cache failure like any other,
  and this module's rule is already that a cache failure degrades to a miss
  rather than failing the caller.

SQLAlchemy needs neither: `pool_pre_ping=True` tests the connection before
handing it over, spots the dead one, and reconnects. Measured, three
back-to-back `asyncio.run` calls per client before those fixes:

| client               | result                            |
| -------------------- | --------------------------------- |
| SQLAlchemy`engine` | OK, OK, OK — pre-ping reconnects |
| `httpx`            | OK,**RuntimeError**, OK     |
| `redis`            | OK,**RuntimeError**, OK     |

And after: five consecutive runs through the real task path, all clean.

The alternative to all of this is one long-lived event loop per worker process,
which keeps the pools valid and lets the clients stay at module scope.

### Prefork and inherited connections

Celery's default pool is prefork: it forks *after* importing the tasks, so
children inherit whatever the parent had open. File descriptors survive a fork,
and two children writing into one socket interleave their bytes mid-protocol.
Forced deliberately — by opening a connection in the parent and then forking
four children — that looks like:

```
child 0 FAILED: OperationalError: connection socket closed
child 1 FAILED: OperationalError: sending query failed: another command is already in progress
child 2 FAILED: ProgrammingError: can't change 'autocommit' now: connection in transaction status INTRANS
```

**This app does not trip it**, which is why there is no `worker_process_init`
hook here. Both pools are lazy: nothing in the parent runs a query or a command
before the fork, so at fork time there is nothing to inherit. Measured in the
worker container, immediately after `import news.tasks`:

```
DB pool:  Pool size: 5  Connections in pool: 0  Checked out: 0
redis:    available 0, in-use 0
```

Add anything that touches Postgres or Redis in the parent — a warm-up, a
`worker_boot` hook — and the guard becomes necessary again:
`engine.sync_engine.dispose(close=False)` in a `worker_process_init` handler,
where `close=False` empties this child's pool without closing a socket the
parent and its siblings still consider theirs.

### Redis databases 0, 1 and 2

| db | holds                                                         |
| -- | ------------------------------------------------------------- |
| 0  | the article cache                                             |
| 1  | the Celery broker — queued tasks                             |
| 2  | task results, expiring after`CELERY_RESULT_EXPIRES_SECONDS` |

Not tidiness. This README tells you to run `FLUSHALL` to force cache misses; on
a shared database that command also deletes every queued job and beat's
schedule. Prove the separation holds:

```bash
docker compose exec redis redis-cli -n 1 DBSIZE     # queue
docker compose exec redis redis-cli -n 0 FLUSHDB    # clear the cache
docker compose exec redis redis-cli -n 1 DBSIZE     # unchanged
```

### Watching a run

```bash
docker compose logs -f worker beat
docker compose --profile debug up -d flower          # http://localhost:5510

# run it now instead of waiting for the schedule
docker compose exec worker celery -A news.celery_app call news.tasks.send_newsletter

# what is registered, and who is listening
docker compose exec worker celery -A news.celery_app inspect registered
docker compose exec worker celery -A news.celery_app inspect active
```

A successful run reads like this:

```
send_newsletter[...]: 10 articles to announce to 1 subscribers
send_newsletter[...]: newsletter sent to 1 subscribers, 0 failed
Task news.tasks.send_newsletter[...] succeeded: {'articles': 10, 'sent': 1, 'failed': 0}
```

Run it again and it sends the same thing again — see
[Every run mails whatever the fetch returned](#every-run-mails-whatever-the-fetch-returned).
The only run that mails nobody is one where NewsAPI returned nothing, or where
no reader is both confirmed and subscribed — the log then reports `0 subscribers`.

### The stats report

`send_stats_report` is the smaller of the two. It looks up confirmed admins,
builds the same `Stats` payload the endpoint returns, and mails each of them a
table of per-source article counts
([news/templates/email/stats_report.html](cnn-website/news/templates/email/stats_report.html)).

```bash
docker compose exec worker celery -A news.celery_app call news.tasks.send_stats_report
docker compose logs --tail=20 worker
# 25 articles from 12 sources, reporting to 1 admins
# stats report sent to 1 admins, 0 failed
```

Then read it in Mailpit — subject `CNN Reader stats: 25 articles from 12 sources`.

With no admin it does nothing, and says so rather than failing:

```bash
docker compose exec db psql -U admin -d cnn -c "UPDATE users SET role='user';"
docker compose exec worker celery -A news.celery_app call news.tasks.send_stats_report
docker compose logs --tail=5 worker      # "no confirmed admins; sending nothing"
```

`confirmed` is required as well as `admin` — there is no point mailing an
address nobody proved they can read. `subscribed` is deliberately *not*
checked: that flag is the newsletter opt-in, and an internal report is not the
newsletter. The only way to stop receiving it is to stop being an admin, which
is why the email carries no unsubscribe link.

**The `Stats` construction is duplicated** — once in the `/api/stats` route,
once in the task. They are identical today and nothing enforces that; change
one and the other will not follow.

### Breaking it on purpose

```bash
# 1. SMTP down: every send fails, each one logged and counted, and the task
#    still SUCCEEDS -- {'sent': 0, 'failed': N}. Unlike the verification
#    email, mail.py raises rather than swallowing, so the loop can count it.
docker compose stop mailpit
docker compose exec worker celery -A news.celery_app call news.tasks.send_newsletter
docker compose logs -f worker      # "could not mail ..." then "0 subscribers, 1 failed"
docker compose start mailpit

# 2. Watch beat actually fire, instead of waiting for tomorrow: point the
#    crontab at the next minute (UTC -- `date -u` to check the hour).
printf 'NEWSLETTER_HOUR=%s\nNEWSLETTER_MINUTE=%s\n' $(date -u +%H) $(( $(date -u +%M) + 1 )) >> .env
docker compose up -d --force-recreate beat worker
docker compose logs -f beat        # "Scheduler: Sending due task newsletter"
# same trick for the report: STATS_REPORT_HOUR / STATS_REPORT_MINUTE

# 3. Repeated runs in one process, which is what the per-call httpx client
#    and cache.py's RuntimeError guard exist to survive. All five succeed.
docker compose exec -w /app worker python -c "
import asyncio
from news.tasks import _send_newsletter
for i in range(5):
    print(i, asyncio.run(_send_newsletter()))
"
```

Celery has no `--reload`, unlike the api service — a change to
[news/tasks.py](cnn-website/news/tasks.py) needs `docker compose restart worker`.

---

## Middlewares

[news/middleware.py](cnn-website/news/middleware.py) owns the whole stack, and
`install(app)` is the one call `main.py` makes. **Order is load-bearing.**

| order     | middleware                 | applies to                               |
| --------- | -------------------------- | ---------------------------------------- |
| outermost | `rate_limit`             | `/api/*` only                          |
| inner     | `DebugToolbarMiddleware` | every HTML page, only when`DEBUG=true` |

Starlette's `add_middleware` inserts at position 0, so **the last one
registered is the outermost**. `install()` therefore adds the toolbar first
and the limiter second.

That is not cosmetic. A `429` returned by the limiter never reaches the router,
so `scope["endpoint"]` is never set — and if the toolbar were outside the
limiter it would try to build its panels for a routeless request and raise
`KeyError: 'endpoint'`, turning every rate-limited response into a **500**.

> Anything you add later that returns a response *without* calling
> `call_next` has to be registered after the toolbar for the same reason.
> Ordinary 404s are fine; it is only short-circuited responses that bite.

### The rate limiter

A fixed window per client IP, counted in Redis so the limit holds across
processes rather than per uvicorn worker.

```python
key = f"rl:{client_ip}:{int(time.time()) // window}"
INCR key; EXPIRE key window        # in one pipeline
```

- **`/api/*` only.** HTML pages, `/static`, and `/healthz` are never limited —
  a healthcheck that can be rate-limited into failing is a liability.
- **`RATE_LIMIT_REQUESTS`** (60) per **`RATE_LIMIT_WINDOW_SECONDS`** (60).
- Over the limit → `429` with a `Retry-After` header and
  `{"detail": "Too many requests"}`.
- **Fails open.** `RedisError` and `RuntimeError` are caught and the request
  is allowed through: a broken limiter must not take the API down with it. The
  trade is explicit — someone who can kill Redis bypasses the limit, which is
  better than Redis being a single point of failure for the whole API.

Watch it work:

```bash
# lower the limit so it trips in a handful of requests, not sixty
echo 'RATE_LIMIT_REQUESTS=5' >> .env
docker compose up -d --force-recreate api

docker compose exec redis redis-cli -n 0 FLUSHDB
for i in $(seq 1 8); do
  curl -s -o /dev/null -w "%{http_code}\n" "$BASE/api/articles?per_page=1" \
    -H "Authorization: Bearer $TOKEN"
done
# 200 200 200 200 200 429 429 429

curl -s -i "$BASE/api/articles" -H "Authorization: Bearer $TOKEN" | head -3
# HTTP/1.1 429 Too Many Requests
# retry-after: 60

# the counters themselves
docker compose exec redis redis-cli -n 0 --scan --pattern 'rl:*'
docker compose exec redis redis-cli -n 0 GET 'rl:172.18.0.1:29817256'
```

Then take `RATE_LIMIT_REQUESTS=5` back out of `.env` and recreate `api`.

Prove it fails open:

```bash
docker compose stop redis
curl -s -o /dev/null -w '%{http_code}\n' "$BASE/api/articles?per_page=1" \
  -H "Authorization: Bearer $TOKEN"     # 200 -- allowed, not 500
docker compose start redis
```

**Two known limits.** It is a fixed window, so a client can send the full quota
at the end of one bucket and again at the start of the next — double the rate
for a couple of seconds. And the key is `request.client.host`, which behind a
proxy is the *proxy's* address; a real deployment would read
`X-Forwarded-For` instead.

---

## Configuration

[news/settings.py](cnn-website/news/settings.py) is the single reader of `.env`, via
pydantic-settings. Secrets are typed `SecretStr` so they print as `**********`
rather than leaking into tracebacks and `repr()`. Every variable is commented
in [.env.example](cnn-website/.env.example).

| Group        | Variables                                                                                                                                                                                       |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NewsAPI      | `NEWS_API_KEY`*, `NEWS_API_URL`, `DEFAULT_SOURCE`, `PAGE_SIZE`                                                                                                                          |
| Database     | `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`                                                                                                                             |
| Auth         | `SECRET_KEY`*, `ACCESS_TOKEN_EXPIRE_MINUTES`, `VERIFICATION_TOKEN_EXPIRE_MINUTES`                                                                                                         |
| Cache        | `REDIS_HOST`, `REDIS_PORT`, `ARTICLE_CACHE_TTL_SECONDS`                                                                                                                                   |
| Middleware   | `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`, `DEBUG`                                                                                                                               |
| Mail         | `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`, `MAIL_FROM_NAME`, `MAIL_STARTTLS`, `MAIL_SSL_TLS`, `MAIL_USE_CREDENTIALS`, `MAIL_VALIDATE_CERTS` |
| Worker       | `CELERY_BROKER_DB`, `CELERY_RESULT_DB`, `CELERY_RESULT_EXPIRES_SECONDS`, `PUBLIC_BASE_URL`                                                                                              |
| Newsletter   | `NEWSLETTER_HOUR`, `NEWSLETTER_MINUTE`, `NEWSLETTER_MAX_ARTICLES`                                                                                                                         |
| Stats report | `STATS_REPORT_HOUR`, `STATS_REPORT_MINUTE`                                                                                                                                                  |

\* no default — the app refuses to start without it.

`users.role` is **not** configuration: there is no env var or endpoint for it.
It lives in the database and you set it by hand — see [Roles](#roles).

⚠️ **`.env` is not currently gitignored.** The root [.gitignore](../.gitignore)
has no `.env` rule, so a stray `git add -A` would commit your `NEWS_API_KEY`
and `SECRET_KEY`. Add to it:

```
.env
.env.local
```

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
  schemas.py       Pydantic request/response models
  repository.py    every query; invalidates the cache on write
  security.py      bcrypt + JWT (AuthService), two token scopes, the admin gate
  mail.py          FastMail client + the three emails
  cache.py         cache-aside on Redis
  news_api.py      the httpx client for newsapi.org (a client per call)
  celery_app.py    the Celery app and the beat schedule
  tasks.py         send_newsletter, send_stats_report
  utils.py         pure helpers, no SQLAlchemy and no settings
  routers/
    api.py         /api/articles, /api/stats (admin), /api/me/liked
    auth.py        /api/auth/*
    newsletter.py  /api/me/subscription
    pages.py       the HTML routes
  templates/       Jinja pages, plus email/ for the three message bodies
  static/          auth.js, styles.css
migrations/        Alembic (env.py is the async variant)
```

There is no `tests/` directory here on purpose: this module is the features,
and [module11](../module11/) is the same application with a test suite around
it.

---

## After a code change

| Changed                                   | Do this                                                                                    |
| ----------------------------------------- | ------------------------------------------------------------------------------------------ |
| Code under`news/`                       | Nothing —`--reload` picks it up through the bind mount                                  |
| `news/tasks.py`, `news/celery_app.py` | `docker compose restart worker beat` — Celery has no `--reload`                       |
| `pyproject.toml` / `uv.lock`          | `uv lock` on the host, then `docker compose restart api worker beat`                   |
| `news/models.py`                        | Generate and apply a migration (above)                                                     |
| `Dockerfile`                            | `docker compose up -d --build api worker beat`                                           |
| `docker-compose.yaml`                   | `docker compose up -d`                                                                   |
| `.env`                                  | `docker compose up -d --force-recreate <service>` — a restart keeps the old environment |

No `--build` is needed for a dependency change: `pyproject.toml` and `uv.lock`
arrive through the bind mount, and the container's start command re-runs
`uv sync --frozen`. `--frozen` installs exactly what the lock pins and errors
if the lock is stale rather than quietly resolving something else.

### Starting clean

```bash
docker compose down -v      # drops the Postgres volume too -- schema and data gone
docker compose up --build --wait
```

`-v` also clears beat's schedule volume, which is how you make a schedule fire
immediately again rather than waiting out the remainder of its interval.

---

## Versions

Python 3.13, FastAPI ≥ 0.115,
SQLAlchemy ≥ 2.0.43 (`asyncio`), Alembic ≥ 1.16.5,
psycopg 3, Postgres 15, Redis 7, `python-jose`, `passlib[bcrypt]` (bcrypt
pinned < 4.1), `fastapi-mail` ≥ 1.5, `celery[redis]` ≥ 5.4, `flower` ≥ 2.0.
Dev group: `fastapi-debug-toolbar` ≥ 0.6.3.
