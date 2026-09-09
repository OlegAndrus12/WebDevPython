# Web Development with Python

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)

A teaching repository. Each folder is a small, self-contained project built to make **one idea**
concrete — run it, break it, read why it broke.

<img src="yoda.jpg" alt="May the Force be with you" width="280">

```
├── module01/   Python tooling, typing, and object-oriented design
├── module02/   Docker, networking, and Docker Compose
├── module03/   HTTP by hand, with nothing but the standard library
├── module04/   asyncio, threads, and the limits of both
├── module05/   SQLAlchemy 2.0 and Alembic
├── module06/   A real app: Flask + SQLAlchemy + Alembic + Postgres
├── module07/   The same app on FastAPI, async end to end
├── module08/   A full REST surface: writes, sub-resources and relations
├── module09/   JWT authentication
```

Modules 06 to 09 are four iterations of **one** application — the same news reader, rebuilt as each
new idea arrives. All four publish the same ports, so only one runs at a time.

**Conventions used throughout:**

- Every folder has its own `README.md` explaining that folder and nothing else.
- Design examples come in pairs — `before.py` breaks the principle, `after.py` applies it. Both run.
- Every example project pins its own dependencies (`pyproject.toml` + a lock file), so folders never
  interfere with each other.
- Python 3.12+.

---

# Module 01 — Python tooling, typing and design

Three parts, in order: **how dependencies are managed**, **how types are described**, and **how code is
structured**.

The first part rebuilds `statusboard` three times over. The application code stays identical; only the
manifest changes. When two folders differ by exactly one thing, that one thing is what you learn.

## 📦 Dependency management

| Folder | What it covers |
| --- | --- |
| **[pipenv_ex/](module01/pipenv_ex/)** | `pip`, `venv` and `requirements.txt` — and where pip runs out: no lock file, no dependency groups, and successive installs that break an environment while exiting `0` |
| **[poetry_ex/](module01/poetry_ex/)** | `pyproject.toml` + `poetry.lock` — ranges versus resolved versions, dependency groups, hashes, and a resolver that explains its conflicts as a proof |
| **[uv_ex/](module01/uv_ex/)** | The same manifest, one Rust binary: locking, syncing, and managing Python versions — replacing pip, venv, pip-tools, pipx and pyenv at once |
| **[poetry_vs_uv_compare/](module01/poetry_vs_uv_compare/)** | Measured benchmarks rather than claims — [`bench.html`](module01/poetry_vs_uv_compare/bench.html) charts the results in [`results.json`](module01/poetry_vs_uv_compare/results.json) |
| **[poetry_logger/](module01/poetry_logger/)** | The same app with console and file logging added |
| **[tools/](module01/tools/)** | `pytest`, `ruff`, `bandit`, `mypy`, `pre-commit` — what each one catches, with deliberately broken files to prove it |

The benchmarks are worth seeing before picking a side. Locking and installing the `statusboard`
dependency set, on the same machine:

| | pip | Poetry | uv |
| --- | --- | --- | --- |
| **lock** | 3.52 s | 2.62 s | **0.09 s** |
| **install** (cold cache) | 15.49 s | 9.77 s | **6.86 s** |
| **install** (warm cache) | 9.10 s | 2.34 s | **0.13 s** |

The gap widens with project size — see [`results.json`](module01/poetry_vs_uv_compare/results.json)
for the larger `zoo_api` set.

## 🏷️ Type annotations

**[type_annotation_extras/](module01/type_annotation_extras/)** — ten runnable lessons, meant to be
read in order, since each builds vocabulary the next one assumes.

| | Lesson | | Lesson |
| --- | --- | --- | --- |
| 01 | [Basics](module01/type_annotation_extras/01_basics.py) — hints vs. runtime checks, `Final`, `Any` vs `object` | 06 | [TypedDict & Literal](module01/type_annotation_extras/06_typeddict_literal.py) — describing shaped data, `@overload` |
| 02 | [Collections](module01/type_annotation_extras/02_collections.py) — `collections.abc`, invariance vs. covariance | 07 | [Narrowing](module01/type_annotation_extras/07_narrowing.py) — `TypeGuard`, `assert_never` |
| 03 | [Aliases](module01/type_annotation_extras/03_aliases.py) — three generations of syntax, vs. `NewType` | 08 | [Pitfalls](module01/type_annotation_extras/08_pitfalls.py) — hints that don't check, mutable defaults |
| 04 | [Generics](module01/type_annotation_extras/04_generics.py) — `TypeVar`, PEP 695 syntax, `ParamSpec` | 09 | [Forward refs](module01/type_annotation_extras/09_forward_refs.py) — PEP 563, postponed evaluation |
| 05 | [Protocols](module01/type_annotation_extras/05_protocols.py) — structural vs. nominal typing | 10 | [Deprecations](module01/type_annotation_extras/10_deprecations.py) — old syntax beside its replacement |

## 🧱 SOLID

**[solid/](module01/solid/)** — all five principles, each a runnable `before.py` / `after.py` pair.
Every file opens with a one-sentence docstring naming the principle, so it explains itself when read
alone.

| | Principle | The example |
| --- | --- | --- |
| **S** | [Single Responsibility](module01/solid/S/) | One function that both reshapes an API payload and prints it, split in two |
| **O** | [Open/Closed](module01/solid/O/) | A `match` over notification channels, replaced by one subclass per channel |
| **L** | [Liskov Substitution](module01/solid/L/) | A read-only storage that inherits `save()` only to raise — plus a subtler signature violation |
| **I** | [Interface Segregation](module01/solid/I/) | A four-method interface forcing `NotImplementedError`, split into roles |
| **D** | [Dependency Inversion](module01/solid/D/) | A service that builds its own database and mailer, versus one handed them |

## 🧩 Design patterns

**[patterns/](module01/patterns/)** — six patterns, each with a runnable example.

| Pattern | The example |
| --- | --- |
| **[Adapter](module01/patterns/adapter/)** | Three carrier APIs with three payload shapes, behind one `ShippingQuote` |
| **[Observer](module01/patterns/observer/)** | An event source fanning log lines out to a console and a file |
| **[Proxy](module01/patterns/proxy/)** | Rate limiting, IP blocking as Django middleware, and real WSGI middleware in front of Flask |
| **[Singleton](module01/patterns/singleton/)** | Settings loaded once — the `__new__` textbook version, and the `lru_cache` version you'd actually write |
| **[State](module01/patterns/state/)** | A state machine written twice: `match`/`case` versus one class per state |
| **[Template Method](module01/patterns/template_method/)** | An export routine with one overridable hook — and the Liskov violation it invites |

📋 Full topic list: **[module01/AGENDA.md](module01/AGENDA.md)**

---

# Module 02 — Docker, networking and Docker Compose

Nine self-contained examples, meant to be read in order, building from *"run one image"* to
*"orchestrate seven polyglot services with one command."* Every folder has its own README with
the full walkthrough; [module02/README.md](module02/README.md) is the map and carries a full
Docker/Compose cheat sheet at the bottom.

| # | Folder | New idea | Stack |
| --- | --- | --- | --- |
| 0 | [welcome-to-docker/](module02/welcome-to-docker/) | Run an image somebody else built | nginx |
| 1 | [python-script/](module02/python-script/) | `Dockerfile`, `build`, `run` | Python |
| 2 | [ruby-script/](module02/ruby-script/) | Write a Dockerfile yourself (exercise) | Ruby |
| 3 | [java/](module02/java/) | Shipping a pre-built artifact, `.dockerignore` | Java |
| 4 | [flask-node/](module02/flask-node/) | Containers must share a network → Compose | Python + Node + Mongo |
| 5 | [microservices/](module02/microservices/) | Compose at scale, service-to-service calls | Python + Node + Go + Java + React |
| 6 | [postgres_ex/](module02/postgres_ex/) | Compose with no build at all — images + volumes | Postgres + pgAdmin |
| 7 | [statusboard-uv/](module02/statusboard-uv/) | A real project: lock file, dev/runtime split | Python (uv) |
| 8 | [statusboard-poetry/](module02/statusboard-poetry/) | Same app, same lesson, different packaging tool | Python (Poetry) |

Four rules that hold throughout the module:

1. `localhost` inside a container is **that container**, always.
2. Container-to-container traffic uses the **container port**, never the published host port.
3. On a user-defined network, the **service name is the hostname** — never a hard-coded IP.
4. The default `bridge` network has no DNS: only user-defined networks resolve names.

📋 Full topic list: **[AGENDA.md](AGENDA.md)**

---

# Module 03 — HTTP by hand with `http.server`

Two servers written against the standard library and nothing else: no Flask, no Django, no
`pip install`. You write the status line, you pick the `Content-Type`, you count the bytes of the
body — so that later, when a framework does all of it invisibly, you know what it is doing.
[module03/README.md](module03/README.md) is the method-by-method walkthrough.

| # | Folder | New idea | Size |
| --- | --- | --- | --- |
| 0 | [clock-server/](module03/clock-server/) | The smallest handler a browser will render: one `do_GET`, no routing | 18 lines |
| 1 | [blog-server/](module03/blog-server/) | Routing, static files, a JSON API, a form POST, a real 404 | ~185 lines |

`clock-server/` is the whole protocol in four statements, and every limitation it has motivates the
next example. `blog-server/` is what those four statements become once one URL is not enough — a
route table, a static-file branch with a path-traversal guard, a JSON API that reads and writes a
file on disk, and a form POST answered with a redirect so the page still works with JavaScript off.
The module ends by naming what a framework would have done for you, in code you have already
written.

Also here: [mime-type.md](module03/mime-type.md) — why `Content-Type` is not optional.

📋 Full topic list: **[module03/AGENDA.md](module03/AGENDA.md)**

---

# Module 04 — asyncio, threads and blocking I/O

Thirteen scripts and four folders, all circling one question: **what does `async` actually buy you,
and when does it buy you nothing?** The answer is narrower than the hype. Async overlaps *waiting*.
It adds no processing power, makes no query faster, and does nothing at all for code that computes.
Every file here either demonstrates the win or takes it away again, and each prints its own
timings — nothing in the module asks you to take a number on trust.
[module04/README.md](module04/README.md) is the map and carries an asyncio cheat sheet at the bottom.

| # | Section | Where | The idea |
| --- | --- | --- | --- |
| 1 | Why bother | [`02_sync_vs_async.py`](module04/02_sync_vs_async.py) | 16 sites checked one by one, then all at once |
| 2 | asyncio basics | [`01_coroutine_object.py`](module04/01_coroutine_object.py), [`02_await_is_sequential.py`](module04/02_await_is_sequential.py) | A coroutine is not a running coroutine; `await` is not parallelism |
| 3 | Running things together | [`03_gather_with_exeption.py`](module04/03_gather_with_exeption.py), `04_task_*.py`, [`05_wait_first_completed.py`](module04/05_wait_first_completed.py) | `gather`, a `Task` handle, `wait(FIRST_COMPLETED)` |
| 4 | Blocking code | `06_thread_pool_*.py` | Threads, the frozen event loop, and the GIL |
| 5 | Files | [sort-files/](module04/sort-files/) | `aiopath` + `aioshutil` vs. `pathlib` + `shutil` |
| 6 | HTTP | [`download_files.py`](module04/download_files.py), [exchange-rate/](module04/exchange-rate/) | Streaming downloads; a real API, 30 requests |
| 7 | SQLite | [sqlite-crud/](module04/sqlite-crud/) | `sqlite3` vs. `aiosqlite` — and what aiosqlite is not |
| 8 | PostgreSQL | [postgres-crud/](module04/postgres-crud/) | `psycopg` vs. `asyncpg`, swept by concurrency |

Each of the four folders holds a `sync.py` / `async_ex.py` pair doing identical work, so the only
variable is how the waiting is handled — and two of them are there to show the win failing to
appear. Copying files on an SSD is syscall-bound, so the async version is no faster; there is no such
thing as a non-blocking SQLite call, so `aiosqlite` buys a free event loop rather than a quicker
query. The module closes with [sweep.py](module04/postgres-crud/sweep.py), which holds the SQL, the
pool and the table fixed and changes only the number of requests in flight: against a 10-connection
pool, threads and coroutines land within ~1.4x of each other, because the database is the
bottleneck. The gap is small at 1 000 concurrent requests and decisive at 100 000, and that is the
only honest reason to reach for an async driver.

Four rules that hold throughout the module:

1. Calling an `async def` function **runs nothing** — it builds a coroutine object; the loop runs it.
2. `await` is a **sequencing** keyword, not a parallelism one. Concurrency comes from `gather`,
   `create_task` or `wait`.
3. Anything without `await` in front of it runs **on the event loop**. If it can block for longer
   than a millisecond, it belongs in a thread.
4. Threads help code that **waits**; processes help code that **computes**. Telling those apart is
   the entire skill.

📋 Full topic list: **[module04/AGENDA.md](module04/AGENDA.md)**

---

# Module 05 — SQLAlchemy 2.0 and Alembic

Three folders, all on the 2.0 API — `select()`, `session.execute()`, `Mapped[...]` — building from Core
and the ORM to schema migrations to a second database. [module05/README.md](module05/README.md) has
the quick-start commands.

| # | Folder | New idea |
| --- | --- | --- |
| 1 | [sqlalchemy/](module05/sqlalchemy/) | Core and ORM on SQLite: engine, schema, models, sessions, CRUD, joins, many-to-many — 13 lessons |
| 2 | [alembic_ex/](module05/alembic_ex/) | Migrations: `--autogenerate`, batch mode on SQLite, naming convention, full command reference |
| 3 | [postgres/](module05/postgres/) | The same ORM code against Postgres in a container — only the URL changes |

📋 Full topic list: **[module05/AGENDA.md](module05/AGENDA.md)**

---

# Module 06 — A real app: Flask + SQLAlchemy + Alembic + Postgres

Where module05's pieces come together: **[cnn-website/](module06/cnn-website/)**, a news reader on
[newsapi.org](https://newsapi.org/). Each visit to the front page asks NewsAPI for stories, stores
them in Postgres, and renders them; every other route reads the database only.

Flask for the web layer, SQLAlchemy 2.0 for the data layer, Alembic for the schema, Postgres in
Docker Compose. Minimal MVT: **six routes, two tables**, and every query in one file. Validation and
JSON serialisation are both written by hand here — `int_arg()` returns a `400`, `article_json()`
spells out every field — which is exactly the work the next module hands to the framework.

```bash
cd module06/cnn-website && cp .env.example .env    # add your NewsAPI key
docker compose up --build --wait                   # -> http://localhost:8080
```

📖 Setup, endpoints, curl examples and configuration: **[module06/README.md](module06/README.md)**
📋 Full topic list: **[module06/AGENDA.md](module06/AGENDA.md)**

---

# Module 07 — The same app on FastAPI, async end to end

**[cnn-website/](module07/cnn-website/)** again, ported to FastAPI and taken async all the way down:
`async def` routes, `AsyncSession`, `httpx.AsyncClient`, an async Alembic `env.py`. Same six routes,
same two tables — so what changed is only ever the framework.

FastAPI's core ideas each land somewhere visible: routers composed with `include_router`,
`Depends`-based dependency injection, request validation from type hints (`Query(ge=1)` → `422`),
Pydantic response models that let a route return an ORM object, and docs generated for free at
`/docs`.

Going async is not a free speedup. The module's own benchmark shows no gain on the app's fast
queries and a 6.8× gain only once there is something worth waiting on. It does buy one hard rule:
lazy-loading a relationship, harmless-but-slow under Flask, is a **crash** (`MissingGreenlet`) under
`AsyncSession` — every relationship a route touches has to be eager-loaded up front.

```bash
cd module07/cnn-website && cp .env.example .env    # add your NewsAPI key
docker compose up --build --wait                   # -> http://localhost:8080/docs
```

📖 Setup, endpoints, curl examples and configuration: **[module07/README.md](module07/README.md)**
📋 Full topic list: **[module07/AGENDA.md](module07/AGENDA.md)**

---

# Module 08 — A full REST surface: writes, sub-resources and relations

**[cnn-website/](module08/cnn-website/)** grows the half of REST the read-only modules never showed.
Alongside the article API there is now a **readers** resource with real `POST` / `PATCH` / `DELETE`,
and a **likes** sub-resource joining readers to articles: **fifteen endpoints, four tables**.

The status codes stop being incidental — `201` with the created object, `204` for a delete, `409`
for a name already taken, `422` from `Path(ge=1)` before any query runs. `PATCH` is where it gets
interesting: `model_dump(exclude_unset=True)` is what separates "the client omitted this field" from
"the client sent null", and the uniqueness re-check has to skip a value that did not change, or
patching a row with its own email conflicts with itself. On the data side, a **composite primary
key** makes a duplicate like impossible in the schema rather than in the application, and
`ON DELETE CASCADE` on the join table means deleting a reader takes their likes along.

Nothing authenticates yet. The reader is named in the URL, and the browser picks one from a dropdown
kept in `localStorage` — an explicit stand-in for a session, which makes the identity problem
visible instead of solved. That problem is what module09 answers.

```bash
cd module08/cnn-website && cp .env.example .env    # add your NewsAPI key
docker compose up --build --wait                   # -> http://localhost:8080/docs
```

📖 Setup, endpoints, curl examples and configuration: **[module08/README.md](module08/README.md)**
📋 Full topic list: **[module08/AGENDA.md](module08/AGENDA.md)**

---

# Module 09 — JWT authentication

**[cnn-website/](module09/cnn-website/)** with accounts. Registering stores a bcrypt hash, logging in
returns a signed HS256 token, and every JSON endpoint refuses to answer without one. Likes become
per-user, because there is finally a user to attach them to: **fifteen endpoints, four tables**.

`get_current_user` is one dependency in `security.py`; any route that adds it is protected, and
`/docs` grows a padlock for it. Around that sit the decisions worth arguing about in a lecture — a
signed token is **not** an encrypted one (decode your own and read the claims); an unknown address
and a wrong password must return the *same* message, or login becomes an account-enumeration oracle;
and a bearer token cannot be revoked, which is why there is no logout endpoint and why the expiry is
short. The OAuth2 password flow also brings its own oddity: the body is form-urlencoded, and the
email travels in a field named `username`.

One structural consequence runs through the whole front end: a cookie is attached automatically, an
`Authorization` header is not, and no `<form method="post">` can set one. That single fact is what
pushes `static/auth.js` into existence and turns every page into a shell the browser fills in.

```bash
cd module09/cnn-website && cp .env.example .env    # add your NewsAPI key
openssl rand -hex 32                               # ...and a SECRET_KEY
docker compose up --build --wait                   # -> http://localhost:8080/docs
```

📖 Setup, endpoints, curl examples and configuration: **[module09/README.md](module09/README.md)**
📋 Full topic list: **[module09/AGENDA.md](module09/AGENDA.md)**

---

