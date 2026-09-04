# postgres/

SQLAlchemy 2.0 ORM against Postgres in a container. Only the URL in
[db.py](db.py) changes — the section code is the same as in
[../sqlalchemy/](../sqlalchemy/). Topics — [AGENDA.md](AGENDA.md).

```bash
docker compose up -d --wait    # `--wait` waits for the healthcheck; without it the first run fails
uv run crud.py
docker compose down            # add -v to also remove the data volume
```

| file | what's in it |
| --- | --- |
| [compose.yaml](compose.yaml) | `postgres:15` + `pgadmin4`, healthcheck on `pg_isready` |
| [db.py](db.py) | engine, `get_session()`, `init_db()` |
| [models.py](models.py) | `Author` 1:M `Book` |
| [crud.py](crud.py) | seven sections + data: 8 authors, 21 books, listed in the file |

## Access

| | |
| --- | --- |
| Postgres | `localhost:5432`, database `users`, `admin` / `admin` |
| pgAdmin | <http://localhost:5050>, `admin@gmail.com` / `admin` |

In pgAdmin the server host is **`db`**, not `localhost`: pgAdmin runs in
its own container.

Each section of `crud.py` is its own `with get_session()` (commit on
exit, rollback on exception). So an object from one section isn't
available in the next one and gets fetched again:
`select(Author).where(Author.email == LE_GUIN)`.
