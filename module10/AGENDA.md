# Module 10 — Agenda

### Email verification and transactional mail
- `fastapi-mail` + `ConnectionConfig`; Mailpit as a dev SMTP sink that delivers nothing
- Jinja email templates rendered by FastMail, separate from the page templates
- A second token scope: `verification_token` beside `access_token`, one signer
- `users.confirmed`; login refused with `401 "Email is not verified"` until the link is clicked
- `BackgroundTasks`: the mail is sent *after* the response, so registering stays fast
- An idempotent confirm endpoint — a link clicked twice is not an error
- Resend that answers the same for a known and an unknown address
- The verification mail swallows SMTP failures; the worker's mail does not — and why

### Redis: cache-aside and a rate-limit middleware
- Cache-aside on exactly one route (`GET /api/articles/{id}`), invalidated on write
- TTL as a backstop, not the mechanism
- JSON, not pickle — a cache entry is data, not a Python object
- A cache failure is never a request failure: every Redis error logged and swallowed
- `RuntimeError` alongside `RedisError`: a pooled connection belongs to the loop that opened it
- Persistence turned off explicitly — `--save ""`, because the stock image is not a cache config
- A fixed-window rate limiter on `/api/*`: `SET key 1 EX n NX`, `429` + `Retry-After`
- Fails open — a dead limiter must not take the API down with it
- Middleware order is load-bearing: `add_middleware` inserts at position 0
- The debug toolbar as opt-in middleware (`DEBUG=true`), and its two upstream patches

### Celery: a worker, a beat, and two scheduled tasks
- A second process type: work no request is waiting for
- Worker, beat and Flower from the same image as the app, differing only in command
- `beat_schedule` with a `crontab`, not an interval — an interval drifts on every restart
- Redis databases 0 / 1 / 2: cache, broker, result backend, kept apart on purpose
- Sync tasks over an async app: `asyncio.run` around the real coroutine
- Prefork and inherited connections — the `worker_process_init` hook
- No lifespan in a worker; a client per call
- `autoretry_for`, `retry_backoff`, `retry_jitter`, `max_retries`
- Two tasks: the reader newsletter, and an admin stats report
- Newsletter subscription as one `PUT /api/me/subscription`
- Roles as a Postgres `ENUM` and a `get_current_admin` dependency — who the report goes to
- Exactly one beat replica, always; a schedule file that must not live in the bind mount

### Compose
- Six services plus two profile-gated UIs; `depends_on` conditions that mean something
- Only one container may run `alembic upgrade head` — the worker waits on a *healthy* api
- Published ports all ending in the module number, so every module can run at once
