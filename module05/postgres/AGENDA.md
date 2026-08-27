# postgres/ — Agenda

Той самий ORM, інша база. Один файл, сім секцій — [crud.py](crud.py).

| секція | тема |
| --- | --- |
| CREATE | `add`/`add_all`, книжки через relationship (save-update cascade) |
| READ | `get()`, `scalars().one()`, обхід зв'язку |
| FILTER | `>`, `between`, `in_`, `like`, `ilike`, join + where |
| SORT | `order_by`, `.desc()`, два ключі, `limit` |
| AGGREGATE | `count/sum/avg/min/max`, GROUP BY, HAVING |
| UPDATE | присвоєння атрибута проти `update()` на багато рядків |
| DELETE | `delete(obj)` з каскадом проти `delete()` за умовою |

## Чого не побачити на SQLite

| | SQLite | Postgres |
| --- | --- | --- |
| `ILIKE` | емуляція через `lower()`, тільки ASCII | справжній оператор |
| `ondelete="CASCADE"` | треба `PRAGMA foreign_keys=ON` | працює завжди |
| PK `Mapped[int]` | `INTEGER` | `SERIAL` |
| типи | динамічні, `VARCHAR(120)` не перевіряється | справжні, довжина перевіряється |
