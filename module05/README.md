# module05 — SQLAlchemy 2.0 + Alembic

```
sqlalchemy/   Core and ORM on SQLite — lessons 00-13
alembic_ex/   Alembic migrations on SQLite — models, two revisions, command reference
postgres/     the same ORM on Postgres — CRUD in a container
```

All on API 2.0: `select()`, `session.execute()`, `Mapped[...]`. Lesson plan — [AGENDA.md](AGENDA.md).

```bash
uv sync

cd sqlalchemy && uv run 04_orm_models.py          # each file runs on its own
cd alembic_ex && uv run alembic upgrade head && uv run python main.py
cd postgres && docker compose up -d --wait && uv run crud.py
```

| | |
| --- | --- |
| [sqlalchemy/](sqlalchemy/) | 13 lessons + two references, SQLite in a file |
| [alembic_ex/](alembic_ex/) | Alembic on SQLite: models, two revisions, batch mode, full command reference |
| [postgres/](postgres/) | Postgres 15 + pgAdmin in compose |
| [pyproject.toml](pyproject.toml) | `uv sync` installs sqlalchemy, alembic, faker, psycopg |

## Alembic in short

`alembic_ex/` shows how Alembic keeps the schema in sync with the ORM
models: change `models.py` → generate a revision from the diff between
"models vs. database" → read it and apply it. On SQLite (`ALTER TABLE`
only supports `RENAME` and `ADD COLUMN`) every revision is wrapped in
`batch_alter_table`, which Alembic enables on its own via
`render_as_batch=True` in [alembic_ex/migrations/env.py](alembic_ex/migrations/env.py).
Details, the working cycle and the command reference —
[alembic_ex/README.md](alembic_ex/README.md).

> The `sqlalchemy` directory does not shadow the library: without an
> `__init__.py` it's only a namespace-package candidate, and the real
> package from site-packages wins.
