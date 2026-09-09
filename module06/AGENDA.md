# Module 06 — Agenda

**Flask MVT over Postgres.** A news reader on NewsAPI: two tables, six routes,
every query in one file.

- Flask app object and routes in one module — why no `create_app()` factory
- Jinja: template inheritance, a shared card partial, one custom filter
- SQLAlchemy 2.0 declarative models, `Mapped[...]` / `mapped_column`
- A session per unit of work: `get_session()` as a contextmanager
- The repository pattern — no SQL outside `repository.py`
- Upsert on a natural key (`articles.url`), because NewsAPI has no stable id
- `joinedload` and the N+1 it avoids
- Alembic: naming conventions, URL from settings, autogenerate, upgrade/downgrade
- Hand-written query validation (`int_arg` → 400) and JSON (`article_json`)
- `pydantic-settings` + `SecretStr`; config in pieces, URL as a computed field
- Docker Compose: healthchecks, `service_healthy`, a venv outside the bind mount

Run it, endpoints, curl examples and config — see [README.md](README.md).
