"""8. База даних: PostgreSQL CRUD -- асинхронна версія (asyncpg).

The same four operations as sync.py, one connection, timed at the same three table
sizes.

    docker compose up -d
    uv run async_ex.py
"""
import asyncio
from time import perf_counter

import asyncpg

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


async def create(conn: asyncpg.Connection, name: str, email: str) -> int:
    """C -- asyncpg uses numbered $1, $2 placeholders, not %s."""
    status = await conn.execute(
        "INSERT INTO contacts (name, email) VALUES ($1, $2)", name, email
    )
    return int(status.split()[-1])


async def read(conn: asyncpg.Connection, email: str) -> asyncpg.Record | None:
    """R -- fetchrow() returns one Record: index it, or unpack it like a tuple."""
    return await conn.fetchrow(
        "SELECT id, name, email FROM contacts WHERE email = $1", email
    )


async def update(conn: asyncpg.Connection, email: str) -> int:
    """U -- execute() hands back a status string like 'UPDATE 1', not a rowcount."""
    status = await conn.execute(
        "UPDATE contacts SET calls = calls + 1 WHERE email = $1", email
    )
    return int(status.split()[-1])


async def delete(conn: asyncpg.Connection, email: str) -> int:
    status = await conn.execute("DELETE FROM contacts WHERE email = $1", email)
    return int(status.split()[-1])


async def grow_to(conn: asyncpg.Connection, rows: int) -> None:
    """Fill the table up to `rows` -- generate_series builds them in the server."""
    have = await conn.fetchval("SELECT COUNT(*) FROM contacts")
    await conn.execute(
        """INSERT INTO contacts (name, email)
           SELECT 'user-' || g, 'user-' || g || '@example.com'
           FROM generate_series($1::bigint, $2::bigint) g""",
        have + 1, rows,
    )
    await conn.execute("ANALYZE contacts")


async def main() -> None:
    conn = await asyncpg.connect(DSN)
    try:
        await conn.execute("DROP TABLE IF EXISTS contacts")
        await conn.execute(SCHEMA)

        print(f"{'rows':>10} {'CREATE':>9} {'READ':>9} {'UPDATE':>9} {'DELETE':>9}")
        for size in SIZES:
            await grow_to(conn, size)
            email = f"probe-{size}@example.com"
            timings = []

            for operation, args in (
                (create, ("Олена Ковальчук", email)),
                (read, (email,)),
                (update, (email,)),
                (delete, (email,)),
            ):
                started = perf_counter()
                await operation(conn, *args)
                timings.append((perf_counter() - started) * 1000)

            print(f"{size:>10,} " + " ".join(f"{ms:6.2f} ms" for ms in timings))
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
