# Module 11 — Agenda

Module 10's application, unchanged, with tests around it. The four levels are
explained in [testing-levels.html](testing-levels.html).

### pytest, in process
- Everything runs with nothing running: no Docker, no Postgres, no Redis, no SMTP, no `.env`
- SQLite `:memory:`, schema built from the models rather than from the migrations
- `httpx.ASGITransport` — the app called in process, no socket and no port
- `asyncio_mode = "auto"`, and a function-scoped event loop
- Fixtures: scope, teardown, and why `password_hash` is session-scoped (bcrypt is slow on purpose)
- `autouse` for the fakes that would fail *silently* if forgotten
- Factories instead of a fixture per row shape — and why not factory_boy here
- `parametrize` with `pytest.param(id=...)`; `pytest.raises`
- Markers: `e2e` deselected by default via `addopts`

### Test doubles and the seams they go through
- Four seams the application already had: `dependency_overrides`, module-level clients,
  `tasks.get_session`, and settings as a mutable object
- Mock vs fake — assert about the *call*, or about the *behaviour*
- `AsyncMock` for the NewsAPI client; `FakeRedis` and an `outbox` for the rest
- Patch the name in the module that *calls* it, not where it was defined
- `RATE_LIMIT_WINDOW_SECONDS=0`: the one switch added for testability, and why it is honest

### Coverage
- Opt-in, never in `addopts` — a number printed every run invites chasing it
- `--cov-report=term-missing` vs `--cov-report=html`
- `concurrency = ["thread", "greenlet"]`, without which async route bodies read as dead code

### End-to-end, in a real browser
- Selenium + `WebDriverWait`, headless by default, `E2E_SLOWMO` to watch it
- Nothing faked: real Postgres, real SMTP, the verification link read back out of Mailpit
- Two settings that silently break the front end (`DEBUG`, the rate limiter), checked and skipped on
- Why the prefix goes on `docker compose` and not on `pytest`, and why `restart` is not enough
- Per-run ids and teardown that runs after a failure

### Load
- Locust: scenarios as plain Python, greenlets rather than threads
- `-u` / `-r` / `-t`; headless vs the live web UI; `--html` reports
- The one suite that asserts about time, and why it uses the database it finds
- What a load test hides: a lost update passes it silently

### Where the four levels differ
- Only in how much of the stack is genuine — everything else follows from that
- The same bug found at four different prices
- Why load sits off to the side of the test pyramid
