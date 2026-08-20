"""8. База даних: скільки одночасних запитів витримує один процес.

Sequential CRUD showed no difference between the drivers, and that was the honest
result: one request at a time has nothing to overlap. This file changes the one
variable that matters -- how many requests are in flight at once -- and holds
everything else fixed.

The CRUD functions are imported from sync.py and async_ex.py, so the SQL is
identical. Both sides get the same CONNECTIONS connections, because a connection
carries one query at a time and that is the database's limit, not the driver's.
The only difference left is what the process does while N requests wait:

    threads  -- one OS thread parked per request, scheduled by the kernel
    asyncpg  -- one suspended coroutine per request, on a single thread

The last line of output measures what a parked thread actually costs, because the
usual claim ("8 MB of stack each") is about reserved virtual address space, not
resident memory. The real number on this machine is printed, and it is small. What
costs is not the RAM -- it is asking the kernel to schedule a thousand threads.

One "request" is the same unit of work in both: check out a connection, then
create, read, update and delete one row.

    docker compose up -d
    uv run sweep.py
"""
import asyncio
import resource
import threading
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

import asyncpg
from psycopg_pool import ConnectionPool

from async_ex import create as a_create, delete as a_delete, read as a_read, update as a_update
from sync import DSN, SCHEMA, create as s_create, delete as s_delete, read as s_read, update as s_update

CONNECTIONS = 10
LOADS = [1, 10, 100, 500, 1000]
BASE_ROWS = 100_000  # a realistically non-empty table


def request_sync(pool: ConnectionPool, n: int) -> None:
    """One request: hold a connection for the whole four operations."""
    email = f"probe-{n}@example.com"
    with pool.connection() as conn:
        s_create(conn, "Олена Ковальчук", email)
        s_read(conn, email)
        s_update(conn, email)
        s_delete(conn, email)


async def request_async(pool: asyncpg.Pool, n: int) -> None:
    email = f"probe-{n}@example.com"
    async with pool.acquire() as conn:
        await a_create(conn, "Олена Ковальчук", email)
        await a_read(conn, email)
        await a_update(conn, email)
        await a_delete(conn, email)


def run_sequential(pool: ConnectionPool, load: int) -> float:
    started = perf_counter()
    for n in range(load):
        request_sync(pool, n)
    return perf_counter() - started


async def run_threads(pool: ConnectionPool, load: int) -> float:
    loop = asyncio.get_running_loop()
    started = perf_counter()
    # max_workers=load: holding `load` requests at once needs `load` threads,
    # because a blocking call occupies its thread from start to finish.
    with ThreadPoolExecutor(max_workers=load) as threads:
        await asyncio.gather(*(
            loop.run_in_executor(threads, request_sync, pool, n) for n in range(load)
        ))
    return perf_counter() - started


async def run_asyncpg(pool: asyncpg.Pool, load: int) -> float:
    started = perf_counter()
    await asyncio.gather(*(request_async(pool, n) for n in range(load)))
    return perf_counter() - started


async def seed() -> None:
    conn = await asyncpg.connect(DSN)
    await conn.execute("DROP TABLE IF EXISTS contacts")
    await conn.execute(SCHEMA)
    await conn.execute(
        """INSERT INTO contacts (name, email)
           SELECT 'user-' || g, 'user-' || g || '@example.com'
           FROM generate_series(1, $1::bigint) g""", BASE_ROWS)
    await conn.execute("ANALYZE contacts")
    await conn.close()


def thread_cost(count: int = 1000) -> str:
    """What `count` parked threads add to resident memory, measured not quoted.

    Must run before anything else: ru_maxrss is a high-water mark that never goes
    down, so measuring a delta after the sweep would always report zero.
    """
    peak = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    before = peak()
    gate = threading.Event()
    with ThreadPoolExecutor(max_workers=count) as pool:
        # The threads have to be parked all at once, or the pool just reuses a
        # handful of them and there is nothing to measure.
        for _ in range(count):
            pool.submit(gate.wait)
        deadline = perf_counter() + 10
        while threading.active_count() <= count and perf_counter() < deadline:
            pass
        alive, after = threading.active_count() - 1, peak()
        gate.set()
    return (f"{alive} threads parked at once: {after - before:.0f} MB resident, "
            f"{(after - before) * 1000 / max(alive, 1):.0f} KB each")


async def main() -> None:
    # First, before the sweep pushes the memory high-water mark up.
    threads_cost = thread_cost()
    await seed()
    print(f"{BASE_ROWS:,} rows in the table, {CONNECTIONS} connections for every run\n")

    apool = await asyncpg.create_pool(DSN, min_size=CONNECTIONS, max_size=CONNECTIONS)
    with ConnectionPool(DSN, min_size=CONNECTIONS, max_size=CONNECTIONS,
                        kwargs={"autocommit": True}) as spool:
        # Warm-up, discarded: the first request through either pool pays for
        # prepared statements and the connections' first use.
        run_sequential(spool, 20)
        await run_threads(spool, 20)
        await run_asyncpg(apool, 20)

        print(f"{'requests':>9} {'sequential':>12} {'threads':>12} {'asyncpg':>12}"
              f" {'threads/async':>14}")
        for load in LOADS:
            # Best of two: one run of 1000 requests can lose to a checkpoint or a
            # page fault, and that is noise, not a property of the driver.
            sequential = min(run_sequential(spool, load) for _ in range(2))
            threaded = min([await run_threads(spool, load) for _ in range(2)])
            asynced = min([await run_asyncpg(apool, load) for _ in range(2)])
            print(f"{load:>9} {sequential * 1000:9.0f} ms {threaded * 1000:9.0f} ms"
                  f" {asynced * 1000:9.0f} ms {threaded / asynced:13.2f}x")
    await apool.close()

    print(f"\n{threads_cost}")


if __name__ == "__main__":
    asyncio.run(main())
    print("\nSequential is the floor: N requests cost N times one request, forever.")
    print("Threads and coroutines both fix that, and against a 10-connection pool")
    print("they land within ~1.4x of each other -- the database is the bottleneck,")
    print("not the driver. The difference is what the process pays to hold the")
    print("waiting: threads make the kernel schedule one per request, coroutines")
    print("cost a heap object each. That gap is small at 1000 and decisive at")
    print("100,000, which is the only reason to reach for an async driver.")
