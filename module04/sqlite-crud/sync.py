"""7. База даних: SQLite CRUD -- синхронна версія (базова лінія).

One function per operation, each timed from main(), with the driver everyone
already knows: the stdlib `sqlite3`. Nothing here is wrong -- this is the right way
to talk to SQLite from a script, a cron job, or a management command.

It becomes wrong the moment it runs inside an event loop, because every call below
blocks the thread it is on. That is what async_ex.py is about.

    uv run sync.py
"""
import sqlite3
from contextlib import closing
from pathlib import Path
from time import perf_counter

DB = Path(__file__).with_name("contacts.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL,
    email TEXT    NOT NULL UNIQUE,
    calls INTEGER NOT NULL DEFAULT 0
)
"""

SEED = [
    ("Олена Ковальчук", "olena@example.com"),
    ("Петро Шевченко", "petro@example.com"),
    ("Ірина Бондаренко", "iryna@example.com"),
]


def create(db: sqlite3.Connection) -> int:
    """C -- executemany + one commit, so all three rows are one transaction."""
    # Placeholders, never f-strings: this is what stops SQL injection, and it also
    # lets the driver reuse the prepared statement across the three rows.
    cursor = db.executemany("INSERT INTO contacts (name, email) VALUES (?, ?)", SEED)
    db.commit()
    return cursor.rowcount


def read(db: sqlite3.Connection) -> list[tuple]:
    """R -- rows come back as plain tuples, in the order of the SELECT list."""
    return db.execute("SELECT id, name, email FROM contacts ORDER BY id").fetchall()


def update(db: sqlite3.Connection, email: str) -> int:
    """U -- rowcount is how you tell "changed a row" from "matched nothing"."""
    cursor = db.execute(
        "UPDATE contacts SET calls = calls + 1 WHERE email = ?", (email,)
    )
    db.commit()
    return cursor.rowcount


def delete(db: sqlite3.Connection, email: str) -> int:
    """D -- same story: zero rows deleted is not an error, it just did nothing."""
    cursor = db.execute("DELETE FROM contacts WHERE email = ?", (email,))
    db.commit()
    return cursor.rowcount


def count(db: sqlite3.Connection) -> int:
    """One value out: fetchone() returns a tuple, so take element 0."""
    return db.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]


def main() -> None:
    DB.unlink(missing_ok=True)  # start from an empty file every run

    started = perf_counter()
    # `closing` is what releases the file handle; the connection's own `with`
    # only commits. Both, in that order, is the complete idiom.
    with closing(sqlite3.connect(DB)) as db, db:
        db.execute(SCHEMA)
        inserted = create(db)
        rows = read(db)
        changed = update(db, "petro@example.com")
        removed = delete(db, "iryna@example.com")
        left = count(db)
    elapsed = perf_counter() - started

    # Printing happens after the clock stops -- writing to a terminal costs more
    # than some of these queries do, and it is not what we are measuring.
    print(f"CREATE   {inserted} rows inserted")
    print("READ")
    for row in rows:
        print(f"         {row}")
    print(f"UPDATE   {changed} row(s) changed")
    print(f"DELETE   {removed} row(s) removed")
    print(f"COUNT    {left} contacts left")

    print(f"\nfive operations in {elapsed * 1000:.1f} ms -- and the thread was "
          f"busy for every one of them.")


if __name__ == "__main__":
    main()
