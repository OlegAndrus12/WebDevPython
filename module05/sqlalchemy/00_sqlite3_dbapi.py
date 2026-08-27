"""1. Робота з базами даних у Python: DB-API 2.0, тобто чистий sqlite3.

Before any ORM, this is the floor every Python database library stands on: PEP 249,
the DB-API 2.0. Learn its four nouns and the rest of the module is vocabulary.

    connection  -- a session with the database, and the unit of transaction
    cursor      -- the thing you execute a statement on and read rows from
    placeholder -- `?` on sqlite3, `%s` on psycopg. NEVER an f-string
    commit      -- until you call it, nobody else can see your writes

Everything the ORM does, it does through a driver that looks exactly like this.

    uv run 00_sqlite3_dbapi.py
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from faker import Faker

DB = Path(__file__).parent / "dbapi_demo.db"
fake = Faker()


@contextmanager
def create_connection(path: Path = DB):
    """Commit on a clean exit, roll back on an exception, always close.

    Note `conn = None` *before* the try: if `connect()` itself raises there is no
    connection to roll back, and a bare `conn.rollback()` in the handler would
    turn a clear "cannot open database" into a confusing AttributeError.
    """
    conn = None
    try:
        conn = sqlite3.connect(path)
        yield conn
        conn.commit()
    except sqlite3.Error as err:
        print("  ! rolled back:", err)
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     VARCHAR(120) NOT NULL,
    email    VARCHAR(120) NOT NULL,
    password VARCHAR(120) NOT NULL,
    age      NUMERIC CHECK (age >= 10 AND age <= 99)
)
"""


def main() -> None:
    DB.unlink(missing_ok=True)

    with create_connection() as conn:
        conn.execute(SCHEMA)
        print("1. created table users")

    # --- INSERT: placeholders, and one commit for the whole batch -------------
    rows = [
        (fake.name(), fake.email(), fake.password(), fake.random_int(min=10, max=99))
        for _ in range(1_000)
    ]
    with create_connection() as conn:
        cur = conn.cursor()
        # executemany sends the same prepared statement 1000 times. A Python loop
        # around cur.execute() gives the same result and is measurably slower.
        cur.executemany(
            "INSERT INTO users (name, email, password, age) VALUES (?, ?, ?, ?)", rows
        )
        print(f"2. inserted {cur.rowcount} users")
        cur.close()

    # --- SELECT ---------------------------------------------------------------
    with create_connection() as conn:
        cur = conn.cursor()

        # One row, one parameter. The trailing comma makes (4,) a tuple -- without
        # it Python sees a parenthesised int and sqlite3 raises.
        cur.execute("SELECT id, name, age FROM users WHERE id = ?", (4,))
        print("3. fetchone:", cur.fetchone())

        cur.execute(
            "SELECT id, name, age FROM users WHERE age > ? ORDER BY name LIMIT ?",
            (30, 3),
        )
        print("4. fetchall:", cur.fetchall())

        # LIKE is SQL's pattern match: % is "any run of characters", _ is one.
        # The pattern is *data*, so it is a parameter too.
        cur.execute("SELECT name FROM users WHERE name LIKE ? LIMIT 3", ("J%",))
        print("5. LIKE 'J%':", [name for (name,) in cur.fetchall()])
        cur.close()

    # --- The injection this all exists to prevent -----------------------------
    with create_connection() as conn:
        evil = "x' OR '1'='1"
        safe = conn.execute(
            "SELECT COUNT(*) FROM users WHERE name = ?", (evil,)
        ).fetchone()[0]
        # Do not write this line in real code. It is here so you see what it does.
        injected = conn.execute(
            f"SELECT COUNT(*) FROM users WHERE name = '{evil}'"  # noqa: S608
        ).fetchone()[0]
        print(f"6. placeholder -> {safe} rows, f-string -> {injected} rows (!)")

    # --- ALTER + UPDATE -------------------------------------------------------
    with create_connection() as conn:
        conn.execute("ALTER TABLE users ADD COLUMN phone VARCHAR(30)")
        cur = conn.executemany(
            "UPDATE users SET phone = ? WHERE id = ?",
            [(fake.phone_number(), i) for i in range(1, 101)],
        )
        # rowcount is how you tell "changed a row" from "matched nothing".
        print(f"7. added column phone, updated {cur.rowcount} rows")

    # --- What you had to write yourself, and the ORM will not ------------------
    with create_connection() as conn:
        row = conn.execute("SELECT id, name, email FROM users WHERE id = 1").fetchone()
    print("8. a row is a plain tuple:", row)
    print("   -> no type, no attributes, no identity: row[1] is 'name' only")
    print("      because you remember the column order you typed.")
    print("   That gap is the entire reason the next 16 files exist.")


if __name__ == "__main__":
    main()
