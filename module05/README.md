# module05 — SQLAlchemy 2.0

```
sqlalchemy/   Core і ORM на SQLite — уроки 00-13
postgres/     той самий ORM на Postgres — CRUD у контейнері
```

Все в API 2.0: `select()`, `session.execute()`, `Mapped[...]`. Плану уроків — [AGENDA.md](AGENDA.md).

```bash
uv sync

cd sqlalchemy && uv run 04_orm_models.py          # кожен файл самостійний
cd postgres && docker compose up -d --wait && uv run crud.py
```

| | |
| --- | --- |
| [sqlalchemy/](sqlalchemy/) | 13 уроків + два довідники, SQLite у файлі |
| [postgres/](postgres/) | Postgres 15 + pgAdmin у compose |
| [pyproject.toml](pyproject.toml) | `uv sync` ставить sqlalchemy, faker, psycopg |

> Каталог `sqlalchemy` бібліотеку не перекриває: без `__init__.py` це лише
> namespace-кандидат, справжній пакет із site-packages виграє.
