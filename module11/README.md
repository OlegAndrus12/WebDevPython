# module11 — testing: unit, integration, end-to-end and load

[module10](../module10/)'s application, unchanged, with three test suites around
it. The point of the module is that the levels differ in exactly **one** way —
how much of the stack is genuine — and everything else follows from that.

| Level | Where | What is real | Needs a stack | Time |
| --- | --- | --- | --- | --- |
| Unit | `tests/test_security.py` | one class, nothing else | no | <1s |
| Integration | `tests/test_*.py` | routes, ORM, SQLite in memory; Redis/SMTP faked | no | ~3s |
| End-to-end | `tests/e2e/` | everything — a real Chrome, Postgres, Mailpit | yes | ~8s |
| Load | `tests/load/` | everything, fifty times over | yes | ~30s |

🧪 The four levels explained before the code:
**[testing-levels.html](testing-levels.html)** — open it in a browser.
[tests/pytest-setup.html](cnn-website/tests/pytest-setup.html) draws this application's
two pytest suites side by side.

**The application itself is documented in [module10's README](../module10/README.md)** —
[email verification](../module10/README.md#emails),
[the Redis cache](../module10/README.md#redis-and-caching),
[the rate limiter and debug toolbar](../module10/README.md#middlewares),
[Celery](../module10/README.md#celery),
[JWT scopes and roles](../module10/README.md#jwt-scopes-and-roles) and the
[API reference](../module10/README.md#api-reference) are identical here. Only the
ports differ: every published port in this module ends in **11**.

---

## Start the project

```bash
cd module11/cnn-website
cp .env.example .env       # then set NEWS_API_KEY and SECRET_KEY

uv run pytest              # ~3s -- and nothing has to be running
docker compose up --build --wait
```

| Service | URL / address | |
| --- | --- | --- |
| **App** | <http://localhost:8011> | `/docs`, `/healthz` |
| **Mailpit** | <http://localhost:8211> | SMTP on `:1011` |
| **pgAdmin** | <http://localhost:5111> | `admin@gmail.com` / `admin` |
| **Postgres** | `localhost:5411` | `admin` / `admin`, database `cnn` |
| **Redis** | `localhost:6311` | 0 cache, 1 broker, 2 results |
| **Flower** | <http://localhost:5511> | opt-in: `docker compose --profile debug up -d flower` |

`NEWS_API_KEY` (<https://newsapi.org/register>) and `SECRET_KEY`
(`openssl rand -hex 32`) have no defaults. Every command below runs from
`cnn-website/`.

---

## In process: pytest, SQLite in memory

```bash
uv run pytest                             # everything, ~3s
uv run pytest -k jwt -v                   # one slice, verbosely
uv run pytest -x --lf                     # stop at the first failure, then rerun it
uv run pytest tests/test_security.py      # one file
```

No Docker, no Postgres, no Redis, no SMTP and no `.env` — a fresh clone passes.
Four things stand in for the outside world, each through a seam the application
already had rather than one added for the tests:

| Dependency | In the tests | Seam |
| --- | --- | --- |
| Postgres | SQLite `:memory:`, schema built from the models | `app.dependency_overrides[get_db]` |
| HTTP | the ASGI app called in-process — no socket, no port | `httpx.ASGITransport` |
| Redis | `FakeRedis`, a dict that answers get/set/delete | `monkeypatch.setattr(cache, "redis_client")` |
| SMTP | `outbox`, a list of the messages that were built | `monkeypatch.setattr(mail, "mailer")` |
| NewsAPI | an `AsyncMock` standing in for `top_headlines` | the `fetched` fixture |
| Celery | the task bodies awaited directly; no broker, no worker | `tasks.get_session` |

The Redis and SMTP fakes are `autouse` for the same reason: forgetting them would
not fail. An unpatched cache quietly degrades to a miss, and an unpatched mailer
finds Mailpit really listening on `:1011` whenever the stack is up. A test that
passes while testing nothing is worse than one that breaks.

**Mock or fake** is a real choice, and both are here on purpose. A mock
(`AsyncMock`) when the test asserts about the *call* — that NewsAPI was reached
once, and with what. A fake (`FakeRedis`, `outbox`) when it asserts about
*behaviour*: a mock returning `None` for every cache read would make every cache
test pass for the wrong reason, because the app treats `None` as a miss.

And the rule that catches everyone once: **patch the name in the module that
calls it.** `news/tasks.py` does `from .mail import send_newsletter_email`, so
patching `news.mail.send_…` does nothing.

### Fixtures and factories

`tests/conftest.py` holds all of it. The two worth knowing:

```python
admin = await users.create(role=Role.ADMIN)   # everything else defaulted
stories = await articles.create_many(5)       # newest first, an hour apart
```

A factory names only what the test is about, so adding one NOT NULL column does
not break every test that builds a user. There is no factory_boy here on purpose:
its async SQLAlchemy support needs a session shimmed onto the class, and the
indirection costs more to explain than the twenty lines it replaces.

`password_hash` is session-scoped for a measurable reason — bcrypt is roughly a
quarter-second a hash at this cost factor, and hashing per user would put most of
the suite's wall clock inside a function no test asserts about.

### Coverage

Opt-in, never in `addopts` — a percentage printed after every run invites chasing
it.

```bash
uv run pytest --cov=news --cov-report=term-missing   # uncovered line numbers
uv run pytest --cov=news --cov-report=html && open htmlcov/index.html
```

One line in `[tool.coverage.run]` is load-bearing:

```toml
concurrency = ["thread", "greenlet"]
```

Without it coverage reports most route bodies as unexecuted even though the tests
plainly run them: SQLAlchemy's asyncio layer runs the sync DBAPI inside a
greenlet, and every `await` on the database switches out of the frame coverage
was tracing. It was costing eight points of reported coverage, none of it real.

---

## End to end: a real browser

Selenium drives a real Chrome against the running stack. Nothing is faked — the
api container writes to Postgres, really sends mail to Mailpit, and the test
reads the verification link back out of the inbox the way a reader would. It is
marked `e2e` and **deselected by default** (`-m "not e2e"` in
[pyproject.toml](cnn-website/pyproject.toml)).

```bash
uv sync --group e2e                       # selenium; chromedriver is fetched on first use

DEBUG=false docker compose up -d --wait   # `up -d`, NOT `restart`
uv run pytest -m e2e --no-cov             # ~8s, headless

docker compose up -d api --wait           # back to the development settings
```

```bash
# watch it happen: a pause after every navigation, click and keystroke, in a
# visible window (E2E_SLOWMO implies E2E_HEADLESS=0). ~30s instead of ~8s.
E2E_SLOWMO=1 uv run pytest -m e2e --no-cov -k browser_flow
```

Two settings are not optional, and neither merely slows the browser down — each
one silently stops this front end working:

| Setting | What it does to a browser |
| --- | --- |
| `RATE_LIMIT_WINDOW_SECONDS` > 0 | `/liked` asks for `/api/auth/me` and `/api/me/liked` from one handler. The second is a 429, `auth.js` swallows a failed fetch by design, and the page renders empty. |
| `DEBUG=true` | The toolbar wraps every request in a sampling profiler. Fifteen requests in a few seconds pile up sessions of a quarter-million samples, and the worker stops answering mid-request. |

The `DEBUG=false` prefix goes on `docker compose`, **never** on `uv run pytest`:
those are the api container's settings, read at import time in another process.
It works only because `docker-compose.yaml` spells the variable out as
`${DEBUG:-true}` — `env_file:` outranks the shell, so a variable taken from
`.env` alone cannot be switched from the command line. And `docker compose
restart api` is not enough: Compose bakes the environment in when it *creates* a
container, so only a recreate (`up -d`) applies a change.
`tests/e2e/conftest.py` checks both and skips with the fix in the message.

Everything the suite writes carries a per-run id and is deleted in teardown,
including after a failure. Knobs, all defaulting to the compose stack:
`E2E_BASE_URL`, `E2E_MAILPIT_URL`, `E2E_DATABASE_URL`, `E2E_HEADLESS`,
`E2E_SLOWMO`, `E2E_TIMEOUT`.

---

## Load: Locust

The only suite that asserts about *time* rather than behaviour — fifty simulated
readers against `GET /api/articles`, the uncached listing, where a queue forms
first. It is not pytest, and no `pytest` command picks it up.

```bash
uv sync --group e2e --group load          # `--group load` alone removes selenium
DEBUG=false docker compose up -d --wait   # the same two settings as above

LOAD_EMAIL=you@example.com LOAD_PASSWORD=... \
    uv run locust -f tests/load/locustfile.py --headless -u 50 -r 10 -t 30s

# ...or with the live web UI at http://localhost:8089 instead of --headless
LOAD_EMAIL=you@example.com LOAD_PASSWORD=... uv run locust -f tests/load/locustfile.py
```

`-u` is the peak user count (a ceiling, not a rate), `-r` how many spawn per
second until it is reached, `-t` the total run time including that ramp. Add
`--html load.html` for a standalone report — [load.html](cnn-website/load.html) is
one such run, checked in so the output can be read without running anything.

Unlike the other two suites it uses whatever is already in the database rather
than seeding its own — a confirmed user and some articles — and says so if either
is missing. It needs the same two settings as the browser suite, plus one reason
of its own: a load test arrives from a single IP, so a live limiter turns the
whole run into fast 429s and reports them as a quick endpoint.

---

## What the suite does not cover

Named out loud, because a short set of examples is not a tested application. This
is deliberately **worked examples, not a safety net** — roughly one test per
technique rather than one per branch.

- **Most branches.** The 404s, the validation errors, the "already confirmed"
  variants, the stats report's failure counting.
- **Postgres-specific behaviour.** The `user_role` ENUM, `ON DELETE CASCADE`
  (SQLite needs a PRAGMA), ILIKE's real collation. SQLite approximates all three.
- **The templates.** `outbox` catches the message above the rendering step, so a
  broken `email/newsletter.html` still passes. The HTML pages are never rendered.
- **The migrations.** The schema comes from `Base.metadata.create_all`, not from
  `alembic upgrade head`. `alembic check` is what catches that drift.
- **Celery itself.** The task *bodies* are awaited directly; the `asyncio.run`
  wrappers, retries, the broker and beat are not exercised.
- **Concurrency.** The rate limiter's fixed-window race and the like endpoint's
  insert race are both untested. `tests/load/` runs them concurrently but asserts
  on latency — a lost update would pass it silently.

[tests/README.md](cnn-website/tests/README.md) is the full reference: every fixture, the
four seams, what is real and what is not.

---

## Layout

```
news/               identical to module10 -- see ../module10/README.md
migrations/         Alembic (env.py is the async variant)
tests/
  conftest.py       every fixture and both factories -- read this first
  test_*.py         security, auth flow, articles, tasks, middleware
  e2e/              Selenium against the running stack, marked `e2e`
  load/             Locust -- latency under concurrency, not pytest
  README.md         the full reference for all three
  pytest-setup.html the two pytest suites, drawn side by side
load.html           a sample Locust report, from one real run
```

In the container, if you want it there — the test dependencies are in the `dev`
group, which `uv sync` installs by default:

```bash
docker compose exec api pytest -q
```

Nothing about the suite needs the container, though. It is the same run.

📋 Topic list: **[AGENDA.md](AGENDA.md)**
