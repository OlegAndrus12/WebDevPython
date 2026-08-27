# postgres/

SQLAlchemy 2.0 ORM проти Postgres у контейнері. Змінюється лише URL у [db.py](db.py) —
код секцій той самий, що в [../sqlalchemy/](../sqlalchemy/). Теми — [AGENDA.md](AGENDA.md).

```bash
docker compose up -d --wait    # `--wait` чекає healthcheck; без нього перший запуск падає
uv run crud.py
docker compose down            # -v щоб і дані з тому знести
```

| файл | що в ньому |
| --- | --- |
| [compose.yaml](compose.yaml) | `postgres:15` + `pgadmin4`, healthcheck на `pg_isready` |
| [db.py](db.py) | engine, `get_session()`, `init_db()` |
| [models.py](models.py) | `Author` 1:M `Book` |
| [crud.py](crud.py) | сім секцій + дані: 8 авторів, 21 книжка, списком у файлі |

## Доступи

| | |
| --- | --- |
| Postgres | `localhost:5432`, база `users`, `admin` / `admin` |
| pgAdmin | <http://localhost:5050>, `admin@gmail.com` / `admin` |

У pgAdmin хост сервера — **`db`**, не `localhost`: pgAdmin у своєму контейнері.

Кожна секція `crud.py` — свій `with get_session()` (коміт на виході, rollback на
винятку). Тому об'єкт із однієї секції в наступній недоступний і його дістають
заново: `select(Author).where(Author.email == LE_GUIN)`.
