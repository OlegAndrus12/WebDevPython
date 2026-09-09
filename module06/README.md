# module06 — Flask + SQLAlchemy + Alembic + Postgres

A news reader on [newsapi.org](https://newsapi.org/). Each visit to the front
page asks NewsAPI for stories, stores them in Postgres, and renders them; every
other route reads the database only. Two tables, six routes, and every query in
one file.

```
cnn-website/
  cnn_website/
    __init__.py       re-exports `app`, so `--app cnn_website` resolves
    views.py          the Flask app object and all six routes
    repository.py     every query in the project
    models.py         Source and Article
    db.py             engine, sessionmaker, get_session()
    news_api.py       the NewsAPI client (requests)
    settings.py       pydantic-settings, validated at import
    utils.py          pure helpers: article_json, int_arg, domain, slugify
    templates/        base, index, article, _card
    static/styles.css
  migrations/         Alembic: env.py + two revisions
  docker-compose.yaml db + web + pgAdmin
```

**Stack:** Flask 3.1 · SQLAlchemy 2.0 (sync) · Alembic 1.19 · psycopg 3 ·
requests · pydantic-settings · Postgres 15 · Python 3.13 · uv

---

## Running it

You need a free NewsAPI key from <https://newsapi.org/register>. The Developer
plan allows 100 requests a day, and the front page spends one per load.

```bash
cd cnn-website
cp .env.example .env          # then put your key in NEWS_API_KEY
```

### Everything in Docker

```bash
docker compose up --build --wait
```

`--wait` blocks until every healthcheck passes and exits non-zero if one does
not, so it is safe to chain a `curl` after it. Migrations run automatically on
container start — the `command:` in `docker-compose.yaml` is
`uv sync && alembic upgrade head && flask run`.

### Open it in a browser

| | |
| --- | --- |
| the reader | <http://localhost:8080> |
| pgAdmin | <http://localhost:5050> — `admin@gmail.com` / `admin` |

Open <http://localhost:8080> and you land on the headlines. The navbar's topic
links and search box both re-query NewsAPI; clicking a card's title opens the
detail page, which is rendered from the database. pgAdmin takes about 25
seconds to finish booting and has the `db` connection preloaded, so there is no
"Register → Server…" dialog to fill in.

### App on the host, database in Docker

Useful when you want a debugger or an editor's reload attached to the app.

```bash
docker compose up -d --wait db        # just Postgres, on localhost:5433
uv run alembic upgrade head
uv run flask --app cnn_website run --debug    # -> http://localhost:5000
```

`--debug` gives you the reloader and the interactive traceback page. The host
app reads `DB_HOST=localhost` / `DB_PORT=5433` from `.env`; the container
overrides both to `db:5432`, because inside the Compose network the database is
a service name rather than a published port.

### Ports and containers

| service | container | host port | what it is |
| --- | --- | --- | --- |
| `web` | `cnn06_web` | 8080 | the Flask app under the dev server |
| `db` | `cnn06_postgres` | 5433 | Postgres 15 (`5432` inside the network) |
| `pgadmin` | `cnn06_pgadmin` | 5050 | <http://localhost:5050> |

All three start with a plain `docker compose up`. pgAdmin logs in with
`admin@gmail.com` / `admin`, and its `db` connection is preloaded from
`pgadmin/servers.json`.

`name: cnn06` at the top of `docker-compose.yaml` is load-bearing. Compose
otherwise derives the project name from the directory, and more than one
project on this machine is called `cnn-website` — without an explicit name a
`docker compose up` could adopt another stack's containers and volumes.

### Everyday commands

```bash
docker compose logs -f web                 # follow the app log
docker compose exec web sh                 # a shell in the app container
docker compose exec db psql -U admin -d cnn    # a psql prompt
docker compose exec web alembic current    # which revision it is on
docker compose down                        # stop; keeps the database volume
docker compose down -v                     # stop and delete the database
```

---

## What this module covers

**Flask as the web layer.** One module-level `app` in `views.py`, with the
routes next to it, and `__init__.py` re-exporting it so both
`flask --app cnn_website run` and `gunicorn cnn_website:app` resolve without
naming the submodule. There is deliberately no `create_app()` factory: what a
factory buys is a second app with different config, and tests here get that
from the environment (`DB_NAME=cnn_test`) instead — the same mechanism
`flask run` and Compose already use.

**Templates and one filter.** Jinja templates with `base.html` inheritance, a
shared `_card.html` partial included by the grid and the lead story, and a
single custom filter registered with `app.add_template_filter(domain, "domain")`
so `{{ article.url | domain }}` renders `edition.cnn.com`.

**A session per unit of work.** `db.py` builds the engine and a `sessionmaker`
at import, then hands out sessions through a `@contextmanager` that commits on
a clean exit, rolls back on an exception, and always closes. Routes use it as
`with get_session() as session:` — the transaction boundary is visible in the
route body.

**The repository pattern.** Every `select()` in the project lives in
`repository.py`; `views.py` contains no SQL at all. Confirm it:

```bash
grep -rn "select(" cnn_website/     # only ever repository.py
```

**Upsert on a natural key.** NewsAPI issues no stable article id, so
`articles.url` is `UNIQUE` and `save_article()` looks a row up by URL before
deciding to insert or update. Without that, every page refresh would insert a
fresh copy of everything on it. Sources work the same way on `sources.slug`.

**Eager loading as a performance choice.** `get_article_by_id()` and
`list_articles()` both state `joinedload(Article.source)`. Drop it and the code
still works — it just issues one extra query per row, the classic N+1, which is
invisible until you profile.

**Alembic owns the schema.** There is no `create_all()` anywhere. `alembic.ini`
leaves `sqlalchemy.url` empty on purpose and `migrations/env.py` fills it in
from `settings.database_url`, so the app and its migrations cannot drift onto
different databases and no password lands in a file that goes into git. A
naming convention on `Base.metadata` means constraints get predictable names
instead of database-invented ones — otherwise an autogenerated downgrade emits
`drop_constraint(None, ...)`.

**Hand-written validation.** Query parameters are parsed by `int_arg()` in
`utils.py`, which returns a bounded int or raises `ValueError` with a message
for the response body. `per_page=-5` is a client bug worth reporting, so it
becomes a `400`, not a silent default.

**Hand-written serialisation.** `article_json()` in `utils.py` is the JSON
shape, written out field by field, including `published_at.isoformat()` —
Flask's JSON provider would otherwise render an HTTP-date. It has to be called
while the session is still open.

**Settings as a validated object.** `settings.py` uses `pydantic-settings` to
read the environment and then `.env`. A missing `NEWS_API_KEY` fails at import
rather than producing a 401 from NewsAPI ten seconds later, and `SecretStr`
keeps the token out of tracebacks and `repr()`. The connection is stored in
pieces rather than as one URL, because Compose needs the same values split up
anyway; `database_url` is a `@computed_field` that assembles them, running the
password through `quote_plus` so an `@` or `/` in it cannot cut the URL in the
wrong place.

**Compose with real healthchecks.** Postgres accepts TCP connections seconds
before it will accept queries, so `depends_on: condition: service_healthy` is
only meaningful because the `db` service has a `pg_isready` healthcheck. The
Dockerfile puts the venv at `/opt/venv`, outside `/app`, so the bind mount of
the source cannot shadow it.

---

## Endpoints

| method | path | what it does |
| --- | --- | --- |
| `GET` | `/` | headlines, or `?q=` search — the only route that calls NewsAPI |
| `GET` | `/article/<int:article_id>` | detail page, rendered from the database |
| `GET` | `/api/articles` | stored articles as JSON: `?q=`, `?page=`, `?per_page=` |
| `GET` | `/api/articles/<int:article_id>` | one stored article as JSON |
| `GET` | `/api/stats` | how many stored articles each source accounts for |
| `GET` | `/healthz` | `SELECT 1`, used by the Compose healthcheck |

Notes worth knowing before you rely on them:

- `/` is the only route that spends a NewsAPI request. Everything else reads
  Postgres, so the JSON API works fine with your daily quota exhausted.
- `?q=` on `/` searches **NewsAPI**; `?q=` on `/api/articles` searches **what
  is already stored**. A story NewsAPI has never handed you is not in the
  second one.
- `/article/<id>` 404s with Flask's HTML error page; `/api/articles/<id>` 404s
  with a JSON body, because a client parsing JSON should not be handed HTML.
- `per_page` is capped at 100, `page` at a minimum of 1. Both are enforced by
  `int_arg()` and reported as `400`.

---

## Testing it with curl

Against the Compose stack on port 8080. If you are running on the host with
`flask run`, use `localhost:5000` instead.

```bash
B=localhost:8080
```

**Is it up, and can it reach the database?**

```bash
curl -s $B/healthz
# {"status":"ok"}
```

**Load the front page once, to put stories in the database.** This is the call
that spends a NewsAPI request.

```bash
curl -s -o /dev/null -w '%{http_code}\n' $B/
# 200
```

**What is stored, and from which sources?**

```bash
curl -s $B/api/stats
# {"sources":[{"articles":28,"name":"CNN","slug":"cnn"}],"total_articles":28,"total_sources":1}
```

**One page of articles.**

```bash
curl -s "$B/api/articles?per_page=1" | python3 -m json.tool
# {
#     "articles": [
#         {
#             "author": "Rebekah Riess",
#             "content": "The defense attorney for ... [+2989 chars]",
#             "description": "The defense attorney for Lindsay Clancy ...",
#             "id": 20,
#             "image_url": "https://media.cnn.com/api/v1/images/...",
#             "published_at": "2026-09-08T13:39:10+00:00",
#             "source": {"name": "CNN", "slug": "cnn"},
#             "title": "Lindsay Clancy's attorney expresses willingness ...",
#             "url": "https://www.cnn.com/2026/09/08/us/lindsay-clancy-..."
#         }
#     ],
#     "page": 1,
#     "pages": 28,
#     "per_page": 1,
#     "query": "",
#     "total": 28
# }
```

**Search what is stored** (not NewsAPI):

```bash
curl -s "$B/api/articles?q=trump&per_page=3" | python3 -c \
  'import json,sys; d=json.load(sys.stdin); print(d["total"], "matches")'
```

**One article by id.**

```bash
curl -s $B/api/articles/1 | python3 -m json.tool | head -5
```

**The validation, which is hand-written here.**

```bash
curl -s -w ' [%{http_code}]\n' "$B/api/articles?page=0"
# {"error":"page must be at least 1, got 0"} [400]

curl -s -w ' [%{http_code}]\n' "$B/api/articles?per_page=500"
# {"error":"per_page must be at most 100, got 500"} [400]
```

**The two shapes of 404.**

```bash
curl -s -w ' [%{http_code}]\n' $B/api/articles/99999
# {"error":"article not found","id":99999} [404]

curl -s -o /dev/null -w '%{http_code}\n' $B/article/99999
# 404   (Flask's HTML error page, not JSON)
```

**The HTML pages.**

```bash
curl -s -o /dev/null -w '%{http_code}\n' $B/                 # 200
curl -s -o /dev/null -w '%{http_code}\n' $B/article/1        # 200
curl -s -o /dev/null -w '%{http_code}\n' "$B/?q=ukraine"     # 200, spends a request
```

---

## Configuration

Read from the environment first, then `.env`. Environment wins, which is how
Compose overrides the database host without editing a file.

| variable | default | what it is |
| --- | --- | --- |
| `NEWS_API_KEY` | *required* | no default — the app refuses to start without it |
| `DB_USER` | `admin` | also fed to Postgres itself by Compose |
| `DB_PASSWORD` | `admin` | a `SecretStr`; URL-escaped into the connection string |
| `DB_NAME` | `cnn` | |
| `DB_HOST` | `localhost` | Compose overrides this to `db` for the web container |
| `DB_PORT` | `5433` | host-side; inside Compose the web container uses `5432` |
| `DEFAULT_SOURCE` | `cnn` | which NewsAPI source the front page shows |
| `PAGE_SIZE` | `12` | how many articles to request **from NewsAPI** |
| `SECRET_KEY` | `dev-only-not-a-real-secret` | Flask session cookies |

Both `.env` and `.env.example` are committed in this repo, so keep anything
genuinely secret out of both — the values checked in are throwaway.

---

## The database

Two tables, both created by migrations.

```
sources    id, slug (unique), name
articles   id, source_id -> sources.id (cascade), url (unique), title,
           description, content, image_url, author, published_at
```

```bash
docker compose exec db psql -U admin -d cnn -c '\dt'
docker compose exec db psql -U admin -d cnn -c '\d articles'
```

Two revisions, `759161cd8fb3` → `b773fddbe615`, and `b773fddbe615` is head.

```bash
uv run alembic current            # where the database is
uv run alembic history            # the chain
uv run alembic upgrade head       # apply everything
uv run alembic downgrade -1       # step back one
```

After changing `models.py`:

```bash
uv run alembic revision --autogenerate -m "what changed"
# then READ the generated file before applying it
uv run alembic upgrade head
```

### Adding an article without spending a NewsAPI request

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

---

## Troubleshooting

**`ModuleNotFoundError` naming a package that is clearly installed**, usually
from `alembic` or `flask`. A copied `.venv` is the cause: console scripts in
`.venv/bin/` carry **absolute** shebangs, so a venv copied from another project
still points at that project's interpreter.

```bash
head -1 .venv/bin/alembic     # is this path in *this* directory?
rm -rf .venv && uv sync       # the fix
```

**`ValidationError: news_api_key Field required` at startup.** There is no
`.env`, or it has no key in it. `cp .env.example .env` and fill it in.

**Port 8080, 5433 or 5050 already in use.** Something else is bound. The
database port can be overridden on the host side without editing the file:

```bash
DB_PORT=5533 docker compose up -d --wait db
```

For the app port, edit the `ports:` mapping for the `web` service — only the
left-hand number matters.

**`rateLimited` or a banner on the front page.** The free plan is 100 requests
a day and `/` spends one per load. The JSON API keeps working; it reads
Postgres.

**The front page is empty and shows no error.** NewsAPI returned no articles
for that source or query. Try `?q=` with a common word, or check
`DEFAULT_SOURCE`.

**`docker compose up` seems to adopt another project's containers.** Check
that `name: cnn06` is still at the top of `docker-compose.yaml`; without it
Compose derives the project name from the directory, which is `cnn-website`
here and in several sibling projects.
