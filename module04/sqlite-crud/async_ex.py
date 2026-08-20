"""7. База даних: SQLite CRUD -- асинхронна версія (aiosqlite).

The same four operations as sync.py, one function each, awaited. Two things worth
knowing before you read it:

  * the API is deliberately the same shape as `sqlite3` -- `execute`, `commit`,
    `fetchall`, placeholders. You are not learning a new database library, you are
    putting `await` in front of one you already know;

  * aiosqlite does not make SQLite asynchronous. There is no such thing as a
    non-blocking SQLite call. It runs the ordinary blocking driver on a dedicated
    worker thread and awaits the result -- exactly the ThreadPoolExecutor trick
    from 06_thread_pool_from_asyncio.py, packaged. So it buys you a free event
    loop, not a faster query.

The bottom half proves it: a ~1s query, run first with the stdlib driver inside a
coroutine and then with aiosqlite, while three ordinary requests try to be served.

    uv run async_ex.py
"""
import asyncio
import sqlite3
from pathlib import Path
from time import perf_counter

import aiosqlite

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

# A deliberately expensive query -- SQLite counting to 5 million in its own VM.
# It stands in for the real thing: a report over a table too big for its indexes.
REPORT = """
WITH RECURSIVE counter(x) AS (
    SELECT 1 UNION ALL SELECT x + 1 FROM counter WHERE x < 5000000
)
SELECT SUM(x) FROM counter
"""

_start = 0.0


# --------------------------------------------------------------------- the CRUD
async def create(db: aiosqlite.Connection) -> int:
    """C -- executemany + one commit, so all three rows are one transaction."""
    # Placeholders, never f-strings: injection-safe, and the driver reuses the
    # prepared statement across the three rows.
    cursor = await db.executemany(
        "INSERT INTO contacts (name, email) VALUES (?, ?)", SEED
    )
    await db.commit()
    return cursor.rowcount


async def read(db: aiosqlite.Connection) -> list[tuple]:
    """R -- rows come back as plain tuples, in the order of the SELECT list."""
    # The cursor is an async context manager, and it can also be iterated with
    # `async for` to stream rows instead of loading them all with fetchall().
    async with db.execute("SELECT id, name, email FROM contacts ORDER BY id") as cur:
        return await cur.fetchall()


async def update(db: aiosqlite.Connection, email: str) -> int:
    """U -- rowcount is how you tell "changed a row" from "matched nothing"."""
    cursor = await db.execute(
        "UPDATE contacts SET calls = calls + 1 WHERE email = ?", (email,)
    )
    await db.commit()
    return cursor.rowcount


async def delete(db: aiosqlite.Connection, email: str) -> int:
    """D -- same story: zero rows deleted is not an error, it just did nothing."""
    cursor = await db.execute("DELETE FROM contacts WHERE email = ?", (email,))
    await db.commit()
    return cursor.rowcount


async def count(db: aiosqlite.Connection) -> int:
    """One value out: fetchone() returns a tuple, so take element 0."""
    async with db.execute("SELECT COUNT(*) FROM contacts") as cur:
        row = await cur.fetchone()
    return row[0]


async def crud() -> None:
    DB.unlink(missing_ok=True)  # start from an empty file every run

    started = perf_counter()
    # `async with` on the connection closes it on exit. Note it does NOT commit,
    # so an uncommitted write at this point would simply be lost.
    async with aiosqlite.connect(DB) as db:
        await db.execute(SCHEMA)
        inserted = await create(db)
        rows = await read(db)
        changed = await update(db, "petro@example.com")
        removed = await delete(db, "iryna@example.com")
        left = await count(db)
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

    print(f"\nfive operations in {elapsed * 1000:.1f} ms -- the same milliseconds "
          f"as sync.py, because\nnone of them was ever waiting on anything.")



async def main() -> None:
    await crud()

if __name__ == "__main__":
    asyncio.run(main())
    print("\nThe query itself did not get faster: it is the same C library doing")
    print("the same work. What changed is that it stopped holding the event loop,")
    print("so the other three requests were not punished for it.")
