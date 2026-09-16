# Tests

Three suites. `tests/` runs the app in-process against an in-memory SQLite
with every outside service faked; `tests/e2e/` drives a real Chrome against the
running compose stack with nothing faked at all; `tests/load/` points fifty
simulated readers at one endpoint and reports what that does to its latency.

> The rest of the project is documented in [../../README.md](../../README.md).

## Running them

```bash
uv run pytest                  # everything, ~3s -- no stack needed
uv run pytest -k jwt -v        # one slice, verbosely
uv run pytest -x --lf          # stop at the first failure, rerun last failures
uv run pytest --cov=news --cov-report=term-missing   # coverage, opt-in
uv run pytest --cov=news --cov-report=html           # the same, browsable
```

The suite in `tests/` runs the app in-process against an in-memory SQLite, with
a fake Redis and an outbox that catches mail before the socket. It needs no
Docker and no network.

## Browser tests

`tests/e2e/` is the other kind: a real Chrome, driven by Selenium, against the
running compose stack. Nothing is faked -- the api container writes to
Postgres, really sends mail to Mailpit, and the test reads the verification
link back out of the inbox the way a reader would.

It is marked `e2e` and **deselected by default** (`-m "not e2e"` in
`pyproject.toml`), so the command above never picks it up.

```bash
uv sync --group e2e            # selenium; chromedriver is fetched on first use

DEBUG=false docker compose up -d --wait   # `up -d`, NOT `restart`
uv run pytest -m e2e --no-cov             # ~8s, headless

docker compose up -d api --wait           # back to the development settings
```

```bash
# watch it happen: a second's pause after every navigation, click and keystroke,
# and a visible window (E2E_SLOWMO implies E2E_HEADLESS=0). ~30s instead of ~8s.
E2E_SLOWMO=1 uv run pytest -m e2e --no-cov -k browser_flow

E2E_HEADLESS=0 uv run pytest -m e2e --no-cov -k browser_flow   # visible, full speed
uv run pytest -m e2e --no-cov -k invisible                     # no browser at all, ~2s
```

`E2E_SLOWMO` paces the *actions* -- `get`, `click`, `send_keys`, `clear` -- and
not every Selenium call. A `WebDriverWait` polls `find_element` several times a
second, so slowing those too would put the delay into waiting rather than into
doing, which is the opposite of watchable. Page loads get double the pause,
since they are what changes the whole screen.

The prefix goes on `docker compose`, **never** on `uv run pytest` -- these are
the api container's settings, read at import time in another process, so
nothing exported around the test run reaches it. It works only because
`docker-compose.yaml` spells the variable out as `${DEBUG:-true}`: `env_file:`
outranks the shell, so a setting taken from `.env` alone cannot be switched
from the command line (`--env-file` does not help either -- it changes the
interpolation file, not the literal `env_file: .env`). `RATE_LIMIT_WINDOW_SECONDS=0`
is simply left in `.env`, because the front-end needs it in normal use too.

Neither setting merely slows a browser down. Each one stops this front-end
working, silently:

| Setting                          | What it does to a browser                                                                                                                                                                                                            |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `RATE_LIMIT_WINDOW_SECONDS` > 0| `/liked` asks for`/api/auth/me` and`/api/me/liked` from one`DOMContentLoaded` handler. The second is a 429, `auth.js` swallows a failed fetch by design, and the page renders empty.                                     |
| `DEBUG=true`                   | The toolbar wraps every request in a pyinstrument sampling profiler. Fifteen requests in a few seconds pile up sessions of a quarter-million samples, and the worker stops answering mid-request -- a`register` that 201s and then never mails. |

`tests/e2e/conftest.py` checks for both and skips with that command in the
message, so neither is a silent dependency. Note that `docker compose restart
api` is **not** enough: Compose bakes the environment into a container when it
creates it, so a restarted container keeps whatever it booted with. Only a
recreate (`up -d`) applies a change.

Everything the suite writes -- the reader it registers, the three articles it
likes -- carries a per-run id and is deleted in teardown, including after a
failure.

Knobs, all with the compose defaults: `E2E_BASE_URL`, `E2E_MAILPIT_URL`,
`E2E_DATABASE_URL`, `E2E_HEADLESS`, `E2E_SLOWMO`, `E2E_TIMEOUT`.

## Load tests

`tests/load/` is the third kind, and the only one that asserts about *time*
rather than behaviour: Locust, against the same running stack, on
`GET /api/articles` -- the uncached listing, where a queue forms first. It is
not pytest and no `pytest` command picks it up -- see
[tests/load/README.md](load/README.md).

```bash
uv sync --group e2e --group load          # `--group load` alone removes selenium
DEBUG=false docker compose up -d --wait   # the same two settings as above

LOAD_EMAIL=you@example.com LOAD_PASSWORD=... \
    uv run locust -f tests/load/locustfile.py --headless -u 50 -r 10 -t 30s

docker compose up -d api --wait           # back to the development settings
```

Unlike the other two suites it uses whatever is already in the database rather
than seeding its own -- a confirmed user and some articles -- and says so if
either is missing.

It needs `DEBUG=false` and `RATE_LIMIT_WINDOW_SECONDS=0` for the same reasons
the browser suite does, and for one more: a load test arrives from a single IP,
so a live limiter turns the whole run into fast 429s and reports them as a
quick endpoint. Both are checked before the ramp, and the run aborts with the
fix in the message.

---

**30 tests, and nothing has to be running** — no Docker, no Postgres, no Redis,
no SMTP. `uv run pytest` in a fresh clone with no `.env` at all passes.

This is deliberately a set of **worked examples, not a safety net**. There is
roughly one test per technique rather than one per branch, and the gaps listed
at the end are left open on purpose. Coverage is not in `addopts` for the same
reason — printing a percentage after every run invites chasing it. Ask for it
when you want it:

```bash
uv run pytest --cov=news --cov-report=term-missing
```

`term-missing` prints the uncovered line numbers next to each percentage, which
is the useful form at the terminal. For anything larger than a glance, ask for
the HTML report instead and read the files with the misses highlighted:

```bash
uv run pytest --cov=news --cov-report=html
open htmlcov/index.html
```

Both reports can be asked for in one run (`--cov-report` is repeatable), and
`htmlcov/` is already in `.gitignore`.

## Layout

```
tests/
  conftest.py           every fixture, plus the two factories -- read this first
  test_security.py      AuthService alone: hashing, scopes, expiry      (6)
  test_auth_flow.py     register -> verify -> login -> use, via routes  (8)
  test_articles_api.py  listing, paging, search, likes, the cache      (14)
  test_tasks.py         the newsletter task -- the file about mocking   (1)
  test_middleware.py    the rate limiter                                (1)
  e2e/                  a real Chrome against the running stack         (2)
  load/                 locust -- latency under concurrency, not pytest
```

## Where each technique lives

| Technique                     | Read                                                          |
| ----------------------------- | ------------------------------------------------------------- |
| Fixtures, scope, teardown     | `engine` /`session` / `password_hash` in conftest.py       |
| `autouse`                   | `fake_redis`, `outbox` — both fail *silently* if forgotten |
| Factories                     | `UserFactory` / `ArticleFactory` in conftest.py            |
| `parametrize` + `param(id=)` | test_security.py (token kinds), test_articles_api.py (paging) |
| `pytest.raises`             | test_security.py                                              |
| Markers                       | `e2e` on the browser suite; `-m "not e2e"` is the default  |
| `monkeypatch`               | everywhere a seam is used                                     |
| `AsyncMock`                 | test_tasks.py                                                 |
| A fake vs a mock              | `FakeRedis` in conftest.py, asserted in test_articles_api.py |
| An end-to-end browser test    | tests/e2e/ -- Selenium, and nothing faked                     |
| A load test                   | tests/load/ -- Locust, and a stopwatch                        |

## What is real and what is not

| Dependency | In the tests                                                     | Where                                    |
| ---------- | ---------------------------------------------------------------- | ---------------------------------------- |
| Postgres   | SQLite`:memory:`, schema built from the models, fresh per test | `engine` fixture                        |
| HTTP       | the ASGI app called in-process — no socket, no port             | `client` fixture, `httpx.ASGITransport` |
| Redis      | `FakeRedis`, a dict that answers get/set/delete                | `fake_redis`, autouse                   |
| SMTP       | `outbox`, a list of the messages that were built                | `outbox`, autouse                       |
| NewsAPI    | an`AsyncMock` standing in for `top_headlines`                | `fetched` fixture                       |
| Celery     | the task bodies are awaited directly; no broker, no worker       | `tasks._send_newsletter()`              |

The two autouse ones are autouse for the same reason: forgetting them would not
fail. An unpatched Redis quietly degrades to a cache miss, and an unpatched
mailer finds mailpit really listening on 1025 when the stack is up. A test that
passes while testing nothing is worse than one that breaks.

## The four seams

Nothing in `news/` was written for the tests, with one exception noted below.
Each fake goes in through a seam the application already had:

1. **`app.dependency_overrides[get_db]`** — FastAPI's own. The routes still say
   `Depends(get_db)`; the override is keyed on the function object, so it
   covers [news/security.py](../news/security.py)'s own `Depends(get_db)` too. One
   line, every caller.
2. **Module-level clients, reached by attribute.** `cache.redis_client` and
   `mail.mailer` are looked up at call time rather than imported into each
   caller, so one `monkeypatch.setattr` covers everything that uses them.
3. **`tasks.get_session`.** The Celery tasks open their own session — there is
   no request to borrow one from — so the context manager itself is the seam.
4. **Settings are a mutable object.** `monkeypatch.setattr(settings, ...)`
   changes one knob for one test and puts it back afterwards.

The exception: `RATE_LIMIT_WINDOW_SECONDS=0` now explicitly disables the rate
limiter ([news/middleware.py](../news/middleware.py)). Without it the *second*
`/api` call in any test would be a 429, since the limit is one request per
second per client IP and the whole suite arrives from one address. Redis
rejects `EX 0` anyway, so the fail-open branch would have let those requests
through by accident; the check says so on purpose instead.

## Fixtures worth knowing

| Fixture                          | Gives you                                        |
| -------------------------------- | ------------------------------------------------ |
| `session`                      | an`AsyncSession` on the empty test database    |
| `client`                       | an`httpx.AsyncClient` wired to the ASGI app    |
| `users` / `articles`         | the two factories, defined in conftest.py        |
| `reader` / `admin`           | a confirmed user / a confirmed admin             |
| `auth_headers` /`admin_headers` | that user's `Authorization` header          |
| `outbox`                       | every email sent during the test                 |
| `fake_redis`                   | the cache, inspectable via`.store`              |
| `password_hash`                | one bcrypt hash, computed once for the whole run |
| `rate_limiter_on`              | the limiter, back on at one request per second   |

`password_hash` is session-scoped for a measurable reason: bcrypt is slow on
purpose, roughly a quarter-second a hash at this cost factor. Hashing per user
would put most of the suite's wall clock inside a function no test asserts
about. The two that genuinely need a fresh hash -- the salting test and the
registration round-trip -- pay for one themselves.

## Factories, not fixtures-full-of-rows

```python
admin = await users.create(role=Role.ADMIN)          # everything else defaulted
stories = await articles.create_many(5)              # newest first, an hour apart
```

A factory names only what the test is about. The alternative — a fixture per
shape, or six keyword arguments at every call site — means that adding one NOT
NULL column breaks every test that builds a user.

There is no factory_boy here, deliberately: its async SQLAlchemy support needs a
session shimmed onto the class, and the indirection costs more to explain than
the twenty lines of `UserFactory` and `ArticleFactory` in
[tests/conftest.py](conftest.py). The pattern is the lesson; the library
is what you reach for when twenty lines becomes two hundred.

## Mock or fake

Both are in the suite on purpose, because they answer different questions:

* **Mock** (`AsyncMock`) when the test asserts about the *call* — that NewsAPI
  was reached once, and with what.
* **Fake** (`FakeRedis`, `outbox`) when the test asserts about *behaviour*. A
  mock returning `None` for every cache read would make every cache test pass
  for the wrong reason — the app treats `None` as a miss. `FakeRedis` really
  stores things, so a hit is a hit.
And the rule that catches everyone once: **patch the name in the module that
calls it.** [news/tasks.py](../news/tasks.py) does
`from .mail import send_newsletter_email`, so patching `news.mail.send_...` does
nothing — tasks.py is already holding its own reference. Patch
`news.tasks.send_newsletter_email`.

## What this suite does not cover

A short set of examples is not a tested application, and the gaps are worth
naming out loud:

* **Most branches.** One example per technique, not one test per path. The 404s,
  the validation errors, the "already confirmed" variants, the stats report's
  failure counting — all real behaviour, none of it here.
* **Postgres-specific behaviour.** The `user_role` ENUM type, `ON DELETE
  CASCADE` (SQLite needs a PRAGMA for it), ILIKE's real collation. SQLite
  approximates all three. A second suite against the compose database is the
  honest fix.
* **The templates.** `outbox` catches the message above the rendering step, so a
  broken `email/newsletter.html` still passes. The HTML pages are not rendered
  by any test at all.
* **The migrations.** The schema comes from `Base.metadata.create_all`, not from
  `alembic upgrade head`. The two can drift and nothing here would notice.
  `alembic check` is what catches that.
* **Celery itself.** The task *bodies* are awaited directly; the sync
  `asyncio.run` wrappers, retries, the broker and beat are not exercised. The
  schedule is checked only for the one failure that is otherwise silent — an
  entry naming a task that is not registered.
* **Concurrency.** Nothing here runs two requests at once, so the rate
  limiter's fixed-window race and the like endpoint's insert race are both
  untested. `tests/load/` does run them concurrently, but it asserts on
  latency and status codes -- a lost update would pass it silently.

## One coverage gotcha

If you do turn coverage on, this line in `[tool.coverage.run]` is load-bearing:

```toml
concurrency = ["thread", "greenlet"]
```

Without it coverage reports most of the route bodies as unexecuted even though
the tests plainly run them. SQLAlchemy's asyncio layer runs the sync DBAPI
inside a greenlet, and every `await` on the database switches out of the frame
coverage was tracing. It was costing eight points of reported coverage, none of
it real.

## In the container

The test dependencies are in the `dev` group, which `uv sync` installs by
default — so they are in the api image too:

```bash
docker compose restart api          # picks up the new dev dependencies
docker compose exec api pytest -q
```

Nothing about the suite needs the container, though. It is the same run.
