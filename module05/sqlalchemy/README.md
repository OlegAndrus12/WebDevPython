# sqlalchemy/

Core and ORM on SQLite. Each file runs on its own and prints what it does.
Topic list — [AGENDA.md](AGENDA.md).

```bash
uv run 04_orm_models.py
```

## Shared

| file | what it does |
| --- | --- |
| [db.py](db.py) | engine, `get_session()`, `init_db()`, `drop_db()`; `PRAGMA foreign_keys=ON` |
| [models.py](models.py) | `User` 1:M `Video` M:M `Tag` via `VideoTag` |
| [seed.py](seed.py) | 10 users, 29 videos, 6 tags; `Faker.seed(7)` — the data is the same every time |

On import, `db.py` does `drop_all` + `create_all` + seed, so every file
starts from a clean, identical database and the output of two files can
be compared. Files 06-13 (the ones using the ORM) are all built the same
way: each section is its own `with get_session()` (commit on block exit,
rollback on exception), and the last line is `drop_db()`, so
`youtube-channels.db` doesn't linger after a run. Files 00-05 work at a
lower level: DB-API, Engine and Core directly.

## References

| | |
| --- | --- |
| [ORM_CHEATSHEET.md](ORM_CHEATSHEET.md) | every command: what it does + an example |
| [column_definition.md](column_definition.md) | ways to declare a column, including the old style |

> `05_session_basics.py` currently fails: it imports `make_engine`, which
> doesn't exist in `db.py`.
