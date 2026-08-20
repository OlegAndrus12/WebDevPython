"""8. База даних: PostgreSQL CRUD -- синхронна версія (psycopg).

Four operations, one connection, timed at three table sizes: does CRUD get slower
as the table grows?

    docker compose up -d
    uv run sync.py
"""
from time import perf_counter

import psycopg

DSN = "postgresql://demo:demo@localhost:5433/contacts"
SIZES = [1_000, 100_000, 1_000_000]

SCHEMA = """
CREATE TABLE contacts (
    id    SERIAL PRIMARY KEY,
    name  TEXT    NOT NULL,
    email TEXT    NOT NULL UNIQUE,
    calls INTEGER NOT NULL DEFAULT 0
)
"""


def create(conn: psycopg.Connection, name: str, email: str) -> int:
    """C -- %s placeholders, never f-strings: that is what stops SQL injection."""
    with conn.cursor() as cur:
        cur.execute("INSERT INTO contacts (name, email) VALUES (%s, %s)", (name, email))
        return cur.rowcount


def read(conn: psycopg.Connection, email: str) -> tuple | None:
    """R -- one row back as a plain tuple, in the order of the SELECT list."""
    with conn.cursor() as cur:
        return cur.execute(
            "SELECT id, name, email FROM contacts WHERE email = %s", (email,)
        ).fetchone()


def update(conn: psycopg.Connection, email: str) -> int:
    """U -- rowcount is how you tell "changed a row" from "matched nothing"."""
    with conn.cursor() as cur:
        cur.execute("UPDATE contacts SET calls = calls + 1 WHERE email = %s", (email,))
        return cur.rowcount


def delete(conn: psycopg.Connection, email: str) -> int:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM contacts WHERE email = %s", (email,))
        return cur.rowcount


def grow_to(conn: psycopg.Connection, rows: int) -> None:
    """Fill the table up to `rows` -- generate_series builds them in the server."""
    have = conn.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]
    conn.execute(
        """INSERT INTO contacts (name, email)
           SELECT 'user-' || g, 'user-' || g || '@example.com'
           FROM generate_series(%s::bigint, %s::bigint) g""",
        (have + 1, rows),
    )
    conn.execute("ANALYZE contacts")


def main() -> None:
    with psycopg.connect(DSN, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS contacts")
        conn.execute(SCHEMA)

        print(f"{'rows':>10} {'CREATE':>9} {'READ':>9} {'UPDATE':>9} {'DELETE':>9}")
        for size in SIZES:
            grow_to(conn, size)
            email = f"probe-{size}@example.com"
            timings = []

            for operation, args in (
                (create, ("Олена Ковальчук", email)),
                (read, (email,)),
                (update, (email,)),
                (delete, (email,)),
            ):
                started = perf_counter()
                operation(conn, *args)
                timings.append((perf_counter() - started) * 1000)

            print(f"{size:>10,} " + " ".join(f"{ms:6.2f} ms" for ms in timings))


if __name__ == "__main__":
    main()
