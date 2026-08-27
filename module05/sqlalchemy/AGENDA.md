# sqlalchemy/ — Agenda

| файл | тема | ключове |
| --- | --- | --- |
| [00](00_sqlite3_dbapi.py) | чистий `sqlite3`, PEP 249 | cursor, `?`-параметр, commit; рядок — це tuple без типу й імен |
| [01](01_engine_url.py) | Engine і URL | `create_engine()` ні до чого не підключається; пул з'єднань |
| [02](02_connect_and_text.py) | `connect()`, `text()` | зв'язані параметри `:name`; дві транзакційні моделі |
| [03](03_core_tables.py) | Core-схема | `MetaData`, `Table`, `Column`, `create_all` |
| [04](04_orm_models.py) | ORM-моделі | `Mapped[int]` = NOT NULL, `Mapped[int \| None]` = nullable |
| [05](05_session_basics.py) | сесія | `flush` проти `commit`, identity map, `expire_on_commit` |
| [06](06_orm_crud.py) | CRUD | присвоєння проти `update()`/`delete()`; каскад у числах |
| [07](07_select_and_results.py) | результати | `scalars()` → сутності, `execute()` → `Row`, `scalar()` → значення |
| [09](09_filtering.py) | WHERE | `between`, `in_`, `like`, `is_(None)`, `and_/or_`, ORDER BY, OFFSET |
| [10](10_aggregates.py) | агрегати | `func.count/sum/avg`, GROUP BY, HAVING проти WHERE |
| [11](11_relationships.py) | зв'язки | `back_populates`, `any()`/`has()`, `cascade` + `ondelete` |
| [12](12_joins.py) | JOIN | `join`, `outerjoin`, `aliased`, підзапити |
| [13](13_many_to_many.py) | M:M | `secondary=` і коли потрібен association object |

Пастки, на які кожен файл наступає окремо: `is None` замість `.is_(None)`,
`and` замість `and_`, `Row` замість сутності, `len(user.videos)` замість `COUNT`,
цикл у Python замість `func.sum`, і lazy-завантаження в циклі (N+1).
