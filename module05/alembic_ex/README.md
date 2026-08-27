# alembic_ex/

Мінімальний Alembic на SQLite: три моделі, дві міграції, довідник команд.

```bash
uv run alembic upgrade head    # створити/оновити базу
uv run python main.py          # попрацювати з нею
```

Усі команди запускаються **з цієї теки** — `alembic.ini` шукається в поточній
(або через `-c шлях/до/alembic.ini`), а `prepend_sys_path = .` кладе саме цю
теку в `sys.path`, щоб `env.py` міг зробити `from models import Base`.

## Файли

| файл | що робить |
| --- | --- |
| [alembic.ini](alembic.ini) | `script_location`, `prepend_sys_path`, логування; `sqlalchemy.url` порожній навмисно |
| [migrations/env.py](migrations/env.py) | виконується на кожну команду: `target_metadata`, URL з `db.py`, `render_as_batch` |
| [migrations/versions/](migrations/versions/) | самі міграції — звичайні `.py`, які **комітяться в git** |
| [migrations/script.py.mako](migrations/script.py.mako) | шаблон, з якого генерується нова міграція |
| [models.py](models.py) | `Author` 1:M `Book` M:1 `Genre` + `NAMING_CONVENTION` |
| [db.py](db.py) | engine, `get_session()`, `drop_db()`; `PRAGMA foreign_keys=ON` |
| [main.py](main.py) | демо: пише й читає через `with get_session()` |

## Головне

**`create_all()` тут немає.** Це не забули — у проєкті з Alembic схему змінює
тільки `alembic upgrade`. Якщо частину таблиць створює `create_all()`, а
частину — міграції, то `alembic_version` каже одне, а база виглядає інакше, і
наступний `--autogenerate` згенерує нісенітницю.

**Три речі, які треба дописати після `alembic init`** (усе в `env.py`):

```python
config.set_main_option("sqlalchemy.url", DB_URL)  # інакше URL у двох місцях
target_metadata = Base.metadata                   # інакше autogenerate порожній
context.configure(..., render_as_batch=True)      # інакше ALTER у SQLite падає
```

**Batch mode.** SQLite з `ALTER TABLE` вміє тільки `RENAME` і `ADD COLUMN` —
ні зміни типу, ні `ADD CONSTRAINT`, ні `DROP COLUMN` у старих версіях. З
`render_as_batch=True` Alembic пише міграцію так:

```python
with op.batch_alter_table("books") as batch_op:
    batch_op.add_column(sa.Column("pages", sa.Integer(), nullable=True))
```

і сам створює таблицю заново, переливає рядки, видаляє стару, перейменовує нову.
На PostgreSQL той самий код виконається звичайним `ALTER TABLE`.

**`NAMING_CONVENTION`** у [models.py](models.py) — щоб у індексів і constraint'ів
були передбачувані імена. Без неї `downgrade()` отримує `drop_constraint(None)`:
база вигадала ім'я сама, а Alembic його не знає. Ставиться один раз на старті
проєкту.

## Робочий цикл

```bash
# 1. змінили models.py
# 2. згенерували міграцію з різниці "моделі проти бази"
uv run alembic revision --autogenerate -m "add books.pages"
# 3. ПРОЧИТАЛИ згенерований файл у migrations/versions/ і виправили
# 4. накотили
uv run alembic upgrade head
```

Крок 3 не пропускають. Autogenerate **не бачить**: перейменування таблиці чи
колонки (покаже як `drop` + `add` — з втратою даних), зміни `CHECK`, зміни
всередині збережених процедур і тригерів. І не переносить дані: додати
`NOT NULL` колонку в непорожню таблицю — це три кроки в одній міграції
(nullable → `op.execute` з заповненням → `alter_column(nullable=False)`).

---

# Довідник команд

Далі `alembic` = `uv run alembic`. `uv` знаходить `pyproject.toml` у
батьківській теці (`module05/`), тому запускати можна прямо звідси.

## Старт проєкту

| команда | що робить |
| --- | --- |
| `alembic init migrations` | створити `alembic.ini` + теку `migrations/` |
| `alembic init -t async migrations` | те саме, але `env.py` під asyncio |
| `alembic list_templates` | які шаблони бувають (`generic`, `async`, `multidb`) |

## Створити міграцію

| команда | що робить |
| --- | --- |
| `alembic revision -m "текст"` | порожня міграція — писати `upgrade()`/`downgrade()` руками |
| `alembic revision --autogenerate -m "текст"` | згенерувати з різниці `Base.metadata` ↔ база |
| `alembic revision --autogenerate --head base` | нова гілка від початку |
| `alembic merge -m "merge" rev1 rev2` | звести дві гілки (буває після мержу в git) |

Autogenerate порівнює з **реальною базою**, тому база має бути накочена до
`head`, інакше в міграцію потрапить різниця, яку вже описує сусідня ревізія.

## Накотити / відкотити

| команда | що робить |
| --- | --- |
| `alembic upgrade head` | накотити все, що не накочено |
| `alembic upgrade +1` | одну ревізію вперед |
| `alembic upgrade ae10` | до конкретної ревізії (вистачає перших символів) |
| `alembic downgrade -1` | одну назад |
| `alembic downgrade base` | відкотити все, база порожня |
| `alembic upgrade head --sql` | не виконувати, а надрукувати SQL (offline mode) |
| `alembic downgrade ae10:head --sql` | SQL для переходу між двома ревізіями |

## Подивитися стан

| команда | що робить |
| --- | --- |
| `alembic current` | на якій ревізії база зараз |
| `alembic current -v` | те саме з описом і шляхом до файла |
| `alembic history` | список ревізій |
| `alembic history -v -r-3:current` | останні три, детально |
| `alembic heads` | де кінці гілок (їх більше одного → потрібен `merge`) |
| `alembic branches` | де гілки розходяться |
| `alembic show ae10` | вміст конкретної ревізії |
| `alembic check` | чи є незгенеровані зміни в моделях (для CI) |

## Аварійні

| команда | що робить |
| --- | --- |
| `alembic stamp head` | записати ревізію в `alembic_version`, **не виконуючи** міграцій |
| `alembic stamp base` | забути, що щось накочено |
| `alembic edit ae10` | відкрити ревізію в `$EDITOR` |

`stamp` — для двох випадків: база вже має потрібні таблиці (перехід зі
`create_all()` на Alembic), або міграцію довелося застосувати руками.

## Що писати в міграції (`op.`)

| операція | приклад |
| --- | --- |
| `create_table` | `op.create_table("tags", sa.Column("id", sa.Integer(), primary_key=True))` |
| `drop_table` | `op.drop_table("tags")` |
| `rename_table` | `op.rename_table("tags", "labels")` |
| `add_column` | `op.add_column("books", sa.Column("pages", sa.Integer(), nullable=True))` |
| `drop_column` | `op.drop_column("books", "pages")` |
| `alter_column` (тип) | `op.alter_column("books", "title", type_=sa.String(300))` |
| `alter_column` (NOT NULL) | `op.alter_column("books", "pages", nullable=False)` |
| `alter_column` (перейменувати) | `op.alter_column("books", "year", new_column_name="published_year")` |
| `create_index` | `op.create_index("ix_books_year", "books", ["year"])` |
| `drop_index` | `op.drop_index("ix_books_year", table_name="books")` |
| `create_unique_constraint` | `op.create_unique_constraint("uq_books_isbn", "books", ["isbn"])` |
| `create_foreign_key` | `op.create_foreign_key("fk_books_author_id_authors", "books", "authors", ["author_id"], ["id"])` |
| `create_check_constraint` | `op.create_check_constraint("ck_books_year", "books", "year > 0")` |
| `drop_constraint` | `op.drop_constraint("uq_books_isbn", "books", type_="unique")` |
| `execute` | `op.execute("UPDATE books SET pages = 0 WHERE pages IS NULL")` |
| `batch_alter_table` | `with op.batch_alter_table("books") as b: b.drop_column("pages")` |
| `get_bind` | `conn = op.get_bind()` — з'єднання, щоб виконати `select` під час міграції |

На SQLite усе, крім `create_table` / `drop_table` / `add_column` /
`rename_table`, треба загортати в `batch_alter_table`.

### Міграція даних, а не схеми

```python
def upgrade() -> None:
    # 1. колонка з'являється nullable -- у старих рядків значення нема
    op.add_column("books", sa.Column("pages", sa.Integer(), nullable=True))
    # 2. заповнюємо. op.execute -- сирий SQL, ORM-моделі тут не імпортують:
    #    міграція має працювати й через рік, коли models.py виглядає інакше
    op.execute("UPDATE books SET pages = 0 WHERE pages IS NULL")
    # 3. і аж тепер NOT NULL
    with op.batch_alter_table("books") as batch_op:
        batch_op.alter_column("pages", nullable=False)
```

## Типові помилки

| симптом | причина |
| --- | --- |
| `Target database is not up to date` | `revision --autogenerate` при ненакоченій базі → спершу `upgrade head` |
| міграція згенерувалась порожня | `target_metadata = None` в `env.py`, або моделі не імпортовані |
| `Can't locate revision identified by 'ae10'` | у базі стоїть ревізія, файла якої нема (гілку видалили) → `stamp` на актуальну |
| `Multiple head revisions are present` | дві паралельні гілки → `alembic merge` |
| `No support for ALTER of constraints in SQLite` | забули `render_as_batch=True` |
| `drop_constraint(None, ...)` у згенерованому файлі | нема `naming_convention` у `MetaData` |
| `Cannot add a NOT NULL column with default value NULL` | нова NOT NULL колонка в непорожню таблицю → три кроки вище |
| `no such table: alembic_version` | базу створили в іншій теці — URL відносний, залежить від того, звідки запускають |

## Якщо все заплуталося

База тут одноразова, тому найшвидший шлях — почати з нуля:

```python
from db import drop_db
drop_db()          # видалити library.db разом з alembic_version
```

```bash
uv run alembic upgrade head
```

У справжньому проєкті так не можна: там `alembic downgrade` до потрібної
ревізії, або нова міграція, яка виправляє попередню.
