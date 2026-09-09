# Module 06 — Agenda

- Flask app object and routes in one module; no `create_app()` factory
- Jinja: template inheritance, a shared card partial, a custom filter
- SQLAlchemy 2.0 declarative models: `Mapped[...]`, `mapped_column`
- A session per unit of work: `get_session()` as a contextmanager
- The repository pattern — no SQL outside `repository.py`
- Upsert on a natural key (`articles.url`)
- `joinedload` and the N+1 it avoids
- Alembic: naming conventions, URL from settings, autogenerate, upgrade/downgrade
- Hand-written query validation (`int_arg` → 400)
- Hand-written JSON serialisation (`article_json`)
- `pydantic-settings` + `SecretStr`; connection in pieces, URL as a computed field
- Docker Compose: healthchecks, `service_healthy`, a venv outside the bind mount
