# alembic_ex/

Minimal Alembic on SQLite: three models, two migrations, a command reference.

```bash
uv run alembic upgrade head    # create/update the database
uv run python main.py          # work with it
```

All commands run **from this directory** — `alembic.ini` is looked up in
the current directory (or via `-c path/to/alembic.ini`), and
`prepend_sys_path = .` puts this exact directory on `sys.path` so
`env.py` can do `from models import Base`.

## Files

| file | what it does |
| --- | --- |
| [alembic.ini](alembic.ini) | `script_location`, `prepend_sys_path`, logging; `sqlalchemy.url` is deliberately empty |
| [migrations/env.py](migrations/env.py) | runs on every command: `target_metadata`, URL from `db.py`, `render_as_batch` |
| [migrations/versions/](migrations/versions/) | the migrations themselves — plain `.py` files that **get committed to git** |
| [migrations/script.py.mako](migrations/script.py.mako) | the template a new migration is generated from |
| [models.py](models.py) | `Author` 1:M `Book` M:1 `Genre` + `NAMING_CONVENTION` |
| [db.py](db.py) | engine, `get_session()`, `drop_db()`; `PRAGMA foreign_keys=ON` |
| [main.py](main.py) | demo: writes and reads via `with get_session()` |

## The main thing

**There's no `create_all()` here.** That's not an oversight — in a
project that uses Alembic, only `alembic upgrade` is allowed to change
the schema. If part of the tables comes from `create_all()` and part
from migrations, `alembic_version` says one thing while the database
looks different, and the next `--autogenerate` will generate nonsense.

**Three things you have to add after `alembic init`** (all in `env.py`):

```python
config.set_main_option("sqlalchemy.url", DB_URL)  # otherwise the URL lives in two places
target_metadata = Base.metadata                   # otherwise autogenerate is empty
context.configure(..., render_as_batch=True)      # otherwise ALTER fails on SQLite
```

**Batch mode.** SQLite's `ALTER TABLE` only supports `RENAME` and
`ADD COLUMN` — no type changes, no `ADD CONSTRAINT`, no `DROP COLUMN` on
older versions. With `render_as_batch=True`, Alembic writes the
migration like this:

```python
with op.batch_alter_table("books") as batch_op:
    batch_op.add_column(sa.Column("pages", sa.Integer(), nullable=True))
```

and creates the table anew itself, copies the rows over, drops the old
one, and renames the new one. On PostgreSQL the same code runs as a
plain `ALTER TABLE`.

**`NAMING_CONVENTION`** in [models.py](models.py) — so indexes and
constraints get predictable names. Without it, `downgrade()` gets a
`drop_constraint(None)`: the database made up a name on its own, and
Alembic doesn't know it. Set it once, at the start of the project.

## Working cycle

```bash
# 1. changed models.py
# 2. generated a migration from the "models vs. database" diff
uv run alembic revision --autogenerate -m "add books.pages"
# 3. READ the generated file in migrations/versions/ and fixed it
# 4. applied it
uv run alembic upgrade head
```

Step 3 is not optional. Autogenerate **does not see**: renaming a table
or column (it shows up as `drop` + `add` — with data loss), changes to
`CHECK`, changes inside stored procedures and triggers. And it doesn't
migrate data: adding a `NOT NULL` column to a non-empty table is three
steps in one migration (nullable → `op.execute` to backfill →
`alter_column(nullable=False)`).

---

# Command reference

Below, `alembic` means `uv run alembic`. `uv` finds `pyproject.toml` in
the parent directory (`module05/`), so it can be run straight from here.

## Starting a project

| command | what it does |
| --- | --- |
| `alembic init migrations` | create `alembic.ini` + the `migrations/` directory |
| `alembic init -t async migrations` | the same, but `env.py` for asyncio |
| `alembic list_templates` | which templates exist (`generic`, `async`, `multidb`) |

## Creating a migration

| command | what it does |
| --- | --- |
| `alembic revision -m "text"` | empty migration — write `upgrade()`/`downgrade()` by hand |
| `alembic revision --autogenerate -m "text"` | generate from the `Base.metadata` ↔ database diff |
| `alembic revision --autogenerate --head base` | a new branch from the start |
| `alembic merge -m "merge" rev1 rev2` | merge two branches (common after a git merge) |

Autogenerate compares against the **actual database**, so the database
must be upgraded to `head` first — otherwise the migration picks up a
diff that a neighboring revision already describes.

## Upgrade / downgrade

| command | what it does |
| --- | --- |
| `alembic upgrade head` | apply everything not yet applied |
| `alembic upgrade +1` | one revision forward |
| `alembic upgrade ae10` | to a specific revision (a few leading characters are enough) |
| `alembic downgrade -1` | one back |
| `alembic downgrade base` | roll back everything, database empty |
| `alembic upgrade head --sql` | don't run it, print the SQL instead (offline mode) |
| `alembic downgrade ae10:head --sql` | SQL for the transition between two revisions |

## Checking state

| command | what it does |
| --- | --- |
| `alembic current` | which revision the database is on right now |
| `alembic current -v` | the same, with description and file path |
| `alembic history` | list of revisions |
| `alembic history -v -r-3:current` | the last three, in detail |
| `alembic heads` | where branch tips are (more than one → needs a `merge`) |
| `alembic branches` | where branches diverge |
| `alembic show ae10` | contents of a specific revision |
| `alembic check` | whether there are ungenerated changes in the models (for CI) |

## Emergency commands

| command | what it does |
| --- | --- |
| `alembic stamp head` | write the revision into `alembic_version`, **without running** migrations |
| `alembic stamp base` | forget that anything has been applied |
| `alembic edit ae10` | open a revision in `$EDITOR` |

`stamp` is for two cases: the database already has the needed tables
(moving from `create_all()` to Alembic), or a migration had to be
applied by hand.

## What to write in a migration (`op.`)

| operation | example |
| --- | --- |
| `create_table` | `op.create_table("tags", sa.Column("id", sa.Integer(), primary_key=True))` |
| `drop_table` | `op.drop_table("tags")` |
| `rename_table` | `op.rename_table("tags", "labels")` |
| `add_column` | `op.add_column("books", sa.Column("pages", sa.Integer(), nullable=True))` |
| `drop_column` | `op.drop_column("books", "pages")` |
| `alter_column` (type) | `op.alter_column("books", "title", type_=sa.String(300))` |
| `alter_column` (NOT NULL) | `op.alter_column("books", "pages", nullable=False)` |
| `alter_column` (rename) | `op.alter_column("books", "year", new_column_name="published_year")` |
| `create_index` | `op.create_index("ix_books_year", "books", ["year"])` |
| `drop_index` | `op.drop_index("ix_books_year", table_name="books")` |
| `create_unique_constraint` | `op.create_unique_constraint("uq_books_isbn", "books", ["isbn"])` |
| `create_foreign_key` | `op.create_foreign_key("fk_books_author_id_authors", "books", "authors", ["author_id"], ["id"])` |
| `create_check_constraint` | `op.create_check_constraint("ck_books_year", "books", "year > 0")` |
| `drop_constraint` | `op.drop_constraint("uq_books_isbn", "books", type_="unique")` |
| `execute` | `op.execute("UPDATE books SET pages = 0 WHERE pages IS NULL")` |
| `batch_alter_table` | `with op.batch_alter_table("books") as b: b.drop_column("pages")` |
| `get_bind` | `conn = op.get_bind()` — a connection to run a `select` during the migration |

On SQLite, everything except `create_table` / `drop_table` /
`add_column` / `rename_table` needs to be wrapped in
`batch_alter_table`.

### Migrating data, not just schema

```python
def upgrade() -> None:
    # 1. the column appears nullable -- old rows have no value
    op.add_column("books", sa.Column("pages", sa.Integer(), nullable=True))
    # 2. backfill it. op.execute -- raw SQL, ORM models are not imported here:
    #    the migration has to keep working a year from now, when models.py looks different
    op.execute("UPDATE books SET pages = 0 WHERE pages IS NULL")
    # 3. and only now NOT NULL
    with op.batch_alter_table("books") as batch_op:
        batch_op.alter_column("pages", nullable=False)
```

## Common errors

| symptom | cause |
| --- | --- |
| `Target database is not up to date` | `revision --autogenerate` on a database that isn't upgraded → run `upgrade head` first |
| the generated migration is empty | `target_metadata = None` in `env.py`, or the models weren't imported |
| `Can't locate revision identified by 'ae10'` | the database points at a revision whose file doesn't exist (the branch was deleted) → `stamp` to the current one |
| `Multiple head revisions are present` | two parallel branches → `alembic merge` |
| `No support for ALTER of constraints in SQLite` | forgot `render_as_batch=True` |
| `drop_constraint(None, ...)` in the generated file | no `naming_convention` on `MetaData` |
| `Cannot add a NOT NULL column with default value NULL` | a new NOT NULL column on a non-empty table → the three steps above |
| `no such table: alembic_version` | the database was created in a different directory — the URL is relative and depends on where it's run from |

## If everything gets tangled up

The database here is disposable, so the fastest way out is to start
from scratch:

```python
from db import drop_db
drop_db()          # delete library.db along with alembic_version
```

```bash
uv run alembic upgrade head
```

In a real project you can't do that: there it's `alembic downgrade` to
the needed revision, or a new migration that fixes the previous one.
