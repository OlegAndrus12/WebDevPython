# cnn-website/

A news reader on [newsapi.org](https://newsapi.org/): Flask for the web layer,
SQLAlchemy 2.0 for the data layer, Alembic for the schema, Postgres in Compose.
Minimal MVT — three routes, two tables, and every query in one file.

```bash
cp .env.example .env                 # then put your NewsAPI key in it

docker compose up --build --wait     # everything -> http://localhost:8000

# ...or run the app on the host against the containerised database:
docker compose up -d --wait db
uv run alembic upgrade head
uv run flask --app cnn_website run --debug     # http://localhost:5000
```

`--wait` holds until both healthchecks pass and exits non-zero if they do not,
so it is safe to chain a `curl` after it.

This is [../sqlalchemy/](../sqlalchemy/) and [../alembic_ex/](../alembic_ex/)
put behind HTTP. The engine, the `get_session()` contextmanager and the
migration workflow are the same as in those folders — what is new is that a
request, not a script, is the unit of work.

---

## What it does

Each request asks NewsAPI for stories, stores them, and renders them:

```
GET /?q=ukraine
      │
      ├─ news_api.search("ukraine")        one HTTP call
      ├─ repository.save_articles(...)     upsert sources, upsert articles
      └─ render the rows it just saved
```

The upsert is the reason there is a database at all: `articles.url` is UNIQUE,
so a story seen on ten page loads stays one row instead of ten. The detail page
then reads from those rows and never touches NewsAPI.

> Every page load costs one NewsAPI request, and the free plan allows **100 a
> day**. Refresh sparingly. (An earlier version of this folder cached responses
> with a TTL; it was dropped to keep the example small.)

If NewsAPI is down or the key is rejected, the view shows a banner instead of
returning a 500.

## Tables

```
sources ---1:M--- articles
```

| table | what a row is | notes |
| --- | --- | --- |
| [`sources`](cnn_website/models.py) | a publisher — `cnn`, `bbc-news` | NewsAPI repeats the whole source object inside every article; this stores it once. `slug` is the natural key. |
| `articles` | one story | NewsAPI issues no stable article id, so `url` is UNIQUE and upserts match on it. |

## Routes

| route | what it does |
| --- | --- |
| `GET /` | headlines, or `?q=` search — the one route that calls NewsAPI |
| `GET /article/<id>` | detail page, rendered from the database |
| `GET /api/articles/<id>` | the same row as JSON |
| `GET /api/stats` | how many articles each source accounts for |
| `GET /healthz` | `SELECT 1`, used by the Compose healthcheck |

The two `/api/` routes read the database only. Their field names are ours, not
NewsAPI's (`image_url`, not `urlToImage`) — the upstream names stop at
`repository.py`, so a change on their side does not reach our clients.

```console
$ curl -s localhost:5000/api/stats | jq
{
  "sources": [
    { "slug": "cnn", "name": "CNN", "articles": 10 },
    { "slug": "the-times-of-india", "name": "The Times of India", "articles": 7 }
  ],
  "total_articles": 23,
  "total_sources": 8
}
```

## Layout

| file | what it holds |
| --- | --- |
| [cnn_website/models.py](cnn_website/models.py) | **M** — the two tables, declarations only |
| [cnn_website/views.py](cnn_website/views.py) | **V** — three routes plus two Jinja filters |
| [cnn_website/templates/](cnn_website/templates/) | **T** — `base`, `index`, `article`, `_card` |
| [cnn_website/repository.py](cnn_website/repository.py) | every SQLAlchemy query, one per method |
| [cnn_website/db.py](cnn_website/db.py) | engine, `SessionLocal`, `get_session()` |
| [cnn_website/settings.py](cnn_website/settings.py) | pydantic-settings; the only place `.env` is read |
| [cnn_website/news_api.py](cnn_website/news_api.py) | the NewsAPI client, no Flask and no SQLAlchemy |
| [migrations/](migrations/) | Alembic — `env.py` plus one revision per schema change |

### Why the queries live in one file

`views.py` never imports a model and never writes a `select()`. It asks
`Repository` for what it needs. The rule is greppable:

```bash
grep -rn "select(" cnn_website/     # only ever repository.py
```

Without it, a view that started at eight lines grows joins, flushes and
`joinedload` options until the routing is buried in SQL — which is what
happened to the app this one is modelled on.

`Repository` holds a `Session` but does not own it: no commit, no rollback, no
close. `get_session()` does all three at the edges of the request.

| method | query |
| --- | --- |
| `save_articles(payloads)` | the whole response — calls the two below per article, returns the rows in the order given |
| `save_source(payload)` | find or create a source by `slug` |
| `save_article(payload, source)` | find or create an article by `url`, update it in place |
| `get_article_by_id(id)` | one article with its source (`joinedload`), or `None` |
| `article_counts_by_source()` | `GROUP BY` — `(slug, name, count)`, busiest first |
| `ping()` | `SELECT 1` for `/healthz` |

`save_articles` returns the objects rather than re-reading them, because
NewsAPI ranks its results and there is no column in the schema to `ORDER BY`
that would reproduce the ranking.

## Configuration

Everything comes from `.env` through one `Settings` class. **`.env` is
gitignored; `.env.example` is the committed template.**

| variable | default | what it is |
| --- | --- | --- |
| `NEWS_API_KEY` | *required* | your key. No default — the app refuses to start without it |
| `DB_USER` | `admin` | |
| `DB_PASSWORD` | `admin` | |
| `DB_NAME` | `cnn` | |
| `DB_HOST` | `localhost` | Compose overrides this to `db` for the web container |
| `DB_PORT` | `5433` | host-side port; inside Compose the web container uses `5432` |
| `DEFAULT_SOURCE` | `cnn` | which source the front page shows |
| `PAGE_SIZE` | `12` | how many articles to request |
| `SECRET_KEY` | dev placeholder | Flask session signing |

There is no `DATABASE_URL`. [settings.py](cnn_website/settings.py) assembles it
from the pieces as a `computed_field`:

```python
postgresql+psycopg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}
```

Compose reads the *same* `.env` to configure Postgres itself
(`POSTGRES_USER: ${DB_USER:-admin}`, and the published port), so the app and the
database cannot end up disagreeing about the credentials. The password goes
through `quote_plus` — a URL is parsed by punctuation, and a password
containing `@` or `/` would otherwise split the string in the wrong place and
produce a baffling "could not translate host name" instead of an auth error.

Why `5433` and not `5432`: [../postgres/compose.yaml](../postgres/compose.yaml)
already publishes `5432`, and both stacks have to be able to run at once.

The key is a `SecretStr`, so it prints as `**********` in tracebacks, logs and
debugger frames — that is the reason to use pydantic-settings here instead of
`os.environ.get`. Reading the real value takes an explicit
`.get_secret_value()`, which happens in exactly one place, in `news_api.py`.

It also travels in the `X-Api-Key` **header**, not as `?apiKey=…`. Query
strings end up in access logs, proxy caches and browser history; headers do not.

> The key currently in `.env` has been shared in plaintext (it is also sitting
> in `../../flask_new/src/flask_new/.env`). Rotate it before it matters.

---

# Docker

| service | what it is | where |
| --- | --- | --- |
| `web` | the Flask app | http://localhost:8000 |
| `db` | Postgres 15 | `localhost:5433` (`5432` inside the network) |
| `pgadmin` | optional, behind a profile | `docker compose --profile tools up -d` -> :5051 |

pgAdmin has no healthcheck and takes ~30s to answer after the container starts,
so a `curl` straight after `up` will be refused. Log in with the credentials
from `compose.yaml` (`admin@gmail.com` / `admin`), then connect to host `db`,
port `5432`.

The web container runs
`alembic upgrade head && flask --app cnn_website run --host 0.0.0.0`, so a
stack started on an empty volume migrates itself before serving. `&&` is the
gate: a failed migration stops the container rather than letting it serve
against the wrong schema.

`--host 0.0.0.0` matters — the default `127.0.0.1` is the container's own
loopback, and the published port would never reach it.

This is Flask's development server, and it says so in the log. That is the
right call for a teaching project; a real deployment swaps it for a WSGI
server (gunicorn, uwsgi, waitress) without touching anything else, because
`create_app()` is already a factory.

```console
$ docker compose up --build --wait
$ docker compose logs web | grep "Running upgrade"
INFO  [alembic.runtime.migration] Running upgrade  -> 759161cd8fb3, create sources and articles
INFO  [alembic.runtime.migration] Running upgrade 759161cd8fb3 -> b773fddbe615, removing fetched at
```

`.env` never enters the image — [.dockerignore](.dockerignore) excludes it and
compose passes it at run time through `env_file`, so the key is not baked into
a layer that `docker history` can read back out.

## Getting inside

```bash
docker compose exec web sh                     # a shell in the app container
docker compose exec web python                 # a REPL with the app importable
docker compose exec db psql -U admin -d cnn    # a psql prompt
```

`exec` runs inside a container that is already up; `run --rm web ...` starts a
throwaway one instead, which is what you want when the app will not boot.

| command | what it does |
| --- | --- |
| `docker compose logs -f web` | follow the app log |
| `docker compose exec web alembic current` | which revision the container is on |
| `docker compose exec web alembic upgrade head` | migrate without restarting |
| `docker compose run --rm web alembic revision --autogenerate -m "..."` | generate a migration |
| `docker compose restart web` | pick up a code change |
| `docker compose down -v` | stop everything **and delete the database** |

## Creating an article by hand

Useful when you have spent the day's NewsAPI requests, or want a row whose
`content` is not truncated.

**Through the repository** — the same code path the app uses, so the upsert and
the foreign key are handled for you. The payload is NewsAPI-shaped, because
that is what `save_article` parses:

```bash
docker compose exec -T web python <<'EOF'
from cnn_website.db import get_session
from cnn_website.repository import Repository

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

with get_session() as session:
    repo = Repository(session)
    article = repo.save_article(payload, repo.save_source(payload["source"]))
    print("created id:", article.id)
EOF
```

```console
created id: 1
$ curl -s localhost:8000/api/articles/1 | jq .title
"Written by hand, not by NewsAPI"
```

Drop the `-T` for an interactive REPL instead of a piped heredoc. The
`with get_session()` block is what commits — without it nothing is written.

**Straight SQL**, if you would rather skip the ORM. `articles.source_id` is
`NOT NULL`, so the source has to exist first:

```bash
docker compose exec -T db psql -U admin -d cnn <<'EOF'
INSERT INTO sources (slug, name) VALUES ('hand-sql', 'Hand SQL')
ON CONFLICT (slug) DO NOTHING;

INSERT INTO articles (source_id, url, title, description, published_at)
VALUES ((SELECT id FROM sources WHERE slug = 'hand-sql'),
        'https://example.com/via-sql', 'Straight from psql',
        'No Python involved.', now())
RETURNING id, title;
EOF
```

Either way the row is visible to the app immediately — `/api/stats` counts it,
`/article/<id>` renders it. Inserting the same `url` twice is refused by the
database, and the constraint has a readable name because of the naming
convention in [models.py](cnn_website/models.py):

```
ERROR:  duplicate key value violates unique constraint "uq_articles_url"
```

One caveat: `/` re-saves whatever NewsAPI returns on every load. A hand-made row
with a URL NewsAPI never returns is never overwritten, but it will not show up
on the front page either — reach it at `/article/<id>`.

---

# Alembic guide

Below, `alembic` means `uv run alembic`, run **from this folder** — that is
where `alembic.ini` is, and `prepend_sys_path = .` is what makes
`from cnn_website.models import Base` work inside `env.py`.

## The rule

**There is no `create_all()` anywhere in this project.** Once Alembic is in the
picture, `alembic upgrade` is the only thing allowed to touch the schema. Two
sources of truth end with `alembic_version` claiming one thing and the tables
looking like another, and the next `--autogenerate` producing nonsense.

## What `alembic init` does not give you

Three additions in [migrations/env.py](migrations/env.py):

```python
config.set_main_option("sqlalchemy.url", settings.database_url)  # one source of truth
target_metadata = Base.metadata                                  # else autogenerate is empty
context.configure(..., compare_type=True, compare_server_default=True)
```

`sqlalchemy.url` is left **empty** in [alembic.ini](alembic.ini) on purpose: the
address lives in `.env`, so the app and its migrations cannot drift onto
different databases, and no password goes into a file that is committed.

Unlike [../alembic_ex/](../alembic_ex/) there is **no `render_as_batch`** here.
That flag exists because SQLite's `ALTER TABLE` can only rename and add
columns, so Alembic has to rebuild the table around every other change.
Postgres has a real `ALTER TABLE` and does not need it.

## The workflow

```bash
# 1. edit cnn_website/models.py
# 2. generate the difference between the models and the live database
uv run alembic revision --autogenerate -m "add articles.language"
# 3. READ the generated file in migrations/versions/ and fix it
uv run alembic upgrade head
```

Step 3 is not optional. Autogenerate **does not see**: a renamed table or
column (it emits `drop` + `add`, losing the data), changes to `CHECK`
constraints, or anything inside a trigger or stored procedure. It also never
migrates data — adding a `NOT NULL` column to a table that already has rows is
three steps in one migration, shown below.

Autogenerate compares against the **live database**, so it must be at `head`
first. Otherwise the diff includes changes an existing revision already covers.

## Commands

### Create

| command | what it does |
| --- | --- |
| `alembic init migrations` | scaffold `alembic.ini` + `migrations/` |
| `alembic revision -m "text"` | empty migration — you write `upgrade()`/`downgrade()` |
| `alembic revision --autogenerate -m "text"` | generate from the model ↔ database difference |
| `alembic merge -m "merge" rev1 rev2` | join two heads (happens after a git merge) |

### Apply and roll back

| command | what it does |
| --- | --- |
| `alembic upgrade head` | apply everything outstanding |
| `alembic upgrade +1` | one revision forward |
| `alembic downgrade -1` | one back |
| `alembic downgrade base` | roll everything back |
| `alembic upgrade head --sql` | print the SQL instead of running it (offline mode) |

On Postgres, DDL is transactional: a migration that fails halfway rolls back
whole, and the database stays on the previous revision. On SQLite it does not,
which is why a failed migration there can leave the schema half-changed.

### Inspect

| command | what it does |
| --- | --- |
| `alembic current` | which revision the database is on |
| `alembic current -v` | the same, with the message and file path |
| `alembic history` | all revisions |
| `alembic heads` | branch tips — more than one means you need `merge` |
| `alembic show <rev>` | one revision's contents |
| `alembic check` | **is there model drift not yet in a migration?** For CI |

### Emergency

| command | what it does |
| --- | --- |
| `alembic stamp head` | record a revision **without running it** |
| `alembic stamp base` | forget that anything was applied |

`stamp` is for two situations: the tables already exist because the project used
to call `create_all()`, or a migration had to be applied by hand.

## Writing a migration

| operation | example |
| --- | --- |
| `create_table` | `op.create_table("tags", sa.Column("id", sa.Integer(), primary_key=True))` |
| `drop_table` | `op.drop_table("tags")` |
| `add_column` | `op.add_column("articles", sa.Column("language", sa.String(8)))` |
| `drop_column` | `op.drop_column("articles", "language")` |
| `alter_column` (type) | `op.alter_column("articles", "title", type_=sa.String(600))` |
| `alter_column` (null) | `op.alter_column("articles", "language", nullable=False)` |
| `alter_column` (rename) | `op.alter_column("articles", "image_url", new_column_name="image")` |
| `create_index` | `op.create_index("ix_articles_language", "articles", ["language"])` |
| `drop_index` | `op.drop_index("ix_articles_language", table_name="articles")` |
| `create_unique_constraint` | `op.create_unique_constraint("uq_articles_url", "articles", ["url"])` |
| `create_foreign_key` | `op.create_foreign_key("fk_articles_source_id_sources", "articles", "sources", ["source_id"], ["id"])` |
| `drop_constraint` | `op.drop_constraint("uq_articles_url", "articles", type_="unique")` |
| `execute` | `op.execute("UPDATE articles SET language = 'en'")` |
| `get_bind` | `conn = op.get_bind()` — to run a query inside the migration |

Constraints are dropped **by name**, which is why
[models.py](cnn_website/models.py) sets a `NAMING_CONVENTION` on the
`MetaData`. Without it the database invents its own names and autogenerate
writes `drop_constraint(None, …)`. Agree the convention once, at the start of a
project — changing it later means renaming everything already in the database.

### Migrating data, not schema

A `NOT NULL` column cannot be added to a table that already has rows — the
existing ones have nothing to put in it. Three steps, one migration:

```python
def upgrade() -> None:
    # 1. nullable, so the existing rows are legal
    op.add_column("articles", sa.Column("language", sa.String(8), nullable=True))
    # 2. backfill. Raw SQL on purpose: no ORM models imported here. This
    #    migration must still run in a year, when models.py looks different.
    op.execute("UPDATE articles SET language = 'en' WHERE language IS NULL")
    # 3. and only now the constraint
    op.alter_column("articles", "language", nullable=False)
```

## When it goes wrong

| symptom | cause |
| --- | --- |
| `Target database is not up to date` | `--autogenerate` on a database behind head → `upgrade head` first |
| the migration came out empty | `target_metadata` is `None`, or the models were never imported |
| `Can't locate revision identified by '…'` | the database names a revision whose file is gone (deleted branch) → `stamp` a real one |
| `Multiple head revisions are present` | two branches → `alembic merge` |
| `drop_constraint(None, …)` in a generated file | no `naming_convention` on the `MetaData` |
| `column … contains null values` | added `NOT NULL` to a non-empty table → the three steps above |
| `NotNullViolation` on a column with a Python default | the object was flushed before the attribute was set |
| `DetachedInstanceError` in a template | the view rendered outside `with get_session()` and the repository never loaded that relationship — add `joinedload`, or assign it |
| connects to the wrong database | the `DB_*` values differ between your shell and Compose — `alembic current -v` prints the URL it used |

## Starting over

The database here is disposable, so the fastest fix is to throw it away:

```bash
docker compose down -v          # -v drops the volume, alembic_version with it
docker compose up -d --wait db
uv run alembic upgrade head
```

In a real project that is not available: there it is `alembic downgrade` to the
revision you want, or a new migration that corrects the previous one.
