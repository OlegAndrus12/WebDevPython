# Module 05 — Agenda

From a tuple returned by `sqlite3` to an object graph the ORM keeps in sync.

| # | тема | де |
| --- | --- | --- |
| 1 | DB-API 2.0: connection, cursor, placeholder, commit — і чому tuple мало | `sqlalchemy/00` |
| 2 | Core: Engine, URL, транзакції, `text()` | `sqlalchemy/01-02` |
| 3 | Core: схема як Python-об'єкти (`MetaData`, `Table`) | `sqlalchemy/03` |
| 4 | ORM: клас → таблиця, `Mapped` / `mapped_column` | `sqlalchemy/04` |
| 5 | Сесія: unit of work, `flush` проти `commit`, `expire_on_commit` | `sqlalchemy/05` |
| 6 | CRUD: об'єктом і statement'ом | `sqlalchemy/06` |
| 7 | `select()` і результати: `scalars()` проти `execute()` | `sqlalchemy/07` |
| 8 | WHERE, ORDER BY, LIMIT | `sqlalchemy/09` |
| 9 | `func`, GROUP BY, HAVING | `sqlalchemy/10` |
| 10 | Зв'язки: 1:M, M:1, `any()`/`has()`, cascade | `sqlalchemy/11` |
| 11 | JOIN, OUTER JOIN, `aliased` | `sqlalchemy/12` |
| 12 | M:M: `secondary=` і association object | `sqlalchemy/13` |
| 13 | Той самий ORM на Postgres: змінюється тільки URL | `postgres/` |

## Що має залишитись у голові

- `scalars()` для сутностей, `execute()` для колонок, `scalar()` для одного числа.
- `flush()` надсилає SQL, `commit()` завершує транзакцію. Інші з'єднання бачать тільки друге.
- `.is_(None)`, ніколи `is None`. `and_/or_/not_`, ніколи `and/or/not`.
- Рахує база, не Python: `func.sum()` замість `sum(...)` по завантажених об'єктах.
- Зв'язок за замовчуванням lazy — цикл по `user.videos` це N+1.
- Каскад потрібен у двох місцях: `cascade=` в ORM і `ondelete=` на FK.
