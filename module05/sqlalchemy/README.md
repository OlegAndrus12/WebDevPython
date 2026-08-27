# sqlalchemy/

Core і ORM на SQLite. Кожен файл запускається окремо й друкує, що робить.
Список тем — [AGENDA.md](AGENDA.md).

```bash
uv run 04_orm_models.py
```

## Спільне

| файл | що робить |
| --- | --- |
| [db.py](db.py) | engine, `get_session()`, `init_db()`, `drop_db()`; `PRAGMA foreign_keys=ON` |
| [models.py](models.py) | `User` 1:M `Video` M:M `Tag` через `VideoTag` |
| [seed.py](seed.py) | 10 користувачів, 29 відео, 6 тегів; `Faker.seed(7)` — дані однакові щоразу |

`db.py` при імпорті робить `drop_all` + `create_all` + seed, тому кожен файл
починає з чистої однакової бази і вивід двох файлів можна порівнювати.
Файли 06-13 (ті, що з ORM) влаштовані однаково: кожна секція — свій
`with get_session()` (коміт на виході з блоку, rollback на винятку), а останній
рядок — `drop_db()`, тому після прогону `youtube-channels.db` не залишається.
Файли 00-05 працюють нижче: DB-API, Engine і Core напряму.

## Довідники

| | |
| --- | --- |
| [ORM_CHEATSHEET.md](ORM_CHEATSHEET.md) | усі команди: що робить + приклад |
| [column_definition.md](column_definition.md) | способи оголосити колонку, включно зі старим стилем |

> `05_session_basics.py` зараз падає: імпортує `make_engine`, якого в `db.py` немає.
