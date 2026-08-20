# postgres-crud — `psycopg` vs `asyncpg`, and the only benchmark that matters

Section 8 of [../AGENDA.md](../AGENDA.md), and the end of the module. Postgres is a real client/server
database over a real socket, so unlike [`../sqlite-crud/`](../sqlite-crud/) there genuinely *is*
network waiting here for an event loop to overlap.

The question is whether that helps, and the answer arrives in two parts.

| File | What it does |
| --- | --- |
| [`sync.py`](sync.py) | Four operations with `psycopg`, timed at 1 000 / 100 000 / 1 000 000 rows |
| [`async_ex.py`](async_ex.py) | The same four with `asyncpg`, same sizes |
| [`sweep.py`](sweep.py) | Imports both, holds everything fixed, and sweeps **concurrency** 1 → 1000 |
| [`docker-compose.yml`](docker-compose.yml) | A throwaway Postgres 17 on port **5433** |

## Run it

```bash
cd module04/postgres-crud
docker compose up -d          # wait for the healthcheck: docker compose ps
uv run sync.py
uv run async_ex.py
uv run sweep.py
docker compose down           # tmpfs storage, so there is nothing left to clean
```

Port **5433**, not 5432, because 5432 is very likely already taken by another project and this
container is not worth a conflict. The data lives in a `tmpfs` — in RAM, gone with the container. No
volume, nothing to `down -v`.

Connect by hand if you want to look around:

```bash
docker compose exec db psql -U demo -d contacts -c "SELECT COUNT(*) FROM contacts;"
```

## Part one: sequential CRUD shows nothing

Both scripts print the same table — four operations, three table sizes:

```
      rows    CREATE      READ    UPDATE    DELETE
     1,000      x.xx ms   x.xx ms   x.xx ms   x.xx ms
   100,000      ...
 1,000,000      ...
```

Two things to watch for as you read your own numbers:

1. **How little the row count matters.** Every operation here goes through an index —
   `SERIAL PRIMARY KEY`, `UNIQUE (email)` — so growing the table 1000× should move these timings far
   less than intuition says it will. That is what an index is *for*, and checking it is worth the
   million-row insert. Drop the `UNIQUE` from `SCHEMA` and run it again to see the other shape.
2. **How little the driver matters.** Compare the two tables: sequential CRUD shows no meaningful
   difference between `psycopg` and `asyncpg`, which is the honest result rather than a
   disappointment — one request at a time has nothing to overlap. A single coroutine awaiting a
   single query is a thread waiting on a socket with extra steps. That is the finding `sweep.py`
   starts from.

The tables are grown server-side with `generate_series`, so the million rows never cross the wire,
followed by `ANALYZE` so the planner's statistics are current before anything is timed.

### The API differences, since they bite

| | `psycopg` (3.x) | `asyncpg` |
| --- | --- | --- |
| placeholders | `%s`, positional tuple | `$1`, `$2`, loose arguments |
| rows changed | `cur.rowcount` | parse the status string: `int(status.split()[-1])` |
| one row | `cur.execute(...).fetchone()` → tuple | `await conn.fetchrow(...)` → `Record` |
| one value | `.fetchone()[0]` | `await conn.fetchval(...)` |
| cursors | `with conn.cursor() as cur` | no cursor needed for the common cases |

`asyncpg` is not a drop-in replacement for anything. It speaks the Postgres binary protocol itself
rather than wrapping libpq, which is where its speed comes from and also why the API is its own
thing. `execute()` handing back `'UPDATE 1'` as a **string** is the detail that surprises everyone.

## Part two: [`sweep.py`](sweep.py) — change one variable

Sequential CRUD had nothing to overlap, so the sweep changes the one variable that actually decides
this question — **how many requests are in flight at once** — and holds everything else fixed:

- the SQL is *literally* the same functions, imported from `sync.py` and `async_ex.py`;
- both sides get the same `CONNECTIONS = 10` pool, because a connection carries one query at a time
  and that is the database's limit, not the driver's;
- one "request" is the same unit either way: check out a connection, then create, read, update and
  delete one row;
- there is a warm-up run whose numbers are thrown away (first use pays for prepared statements and
  connection setup), and every measurement is the best of two — a run of 1000 requests can lose to a
  checkpoint, and that is noise, not a property of a driver.

So the only difference left is **what the process does while N requests wait**:

| Strategy | Per waiting request |
| --- | --- |
| `sequential` | nothing waits in parallel — the floor |
| `threads` (`psycopg` + `ThreadPoolExecutor`) | one OS thread parked, scheduled by the kernel |
| `asyncpg` | one suspended coroutine on a single thread |

```
 requests   sequential      threads      asyncpg  threads/async
        1          ...          ...          ...          ...x
       10
      100
      500
     1000
```

What it shows, in the file's own words: sequential is the floor and always will be — N requests cost
N times one request, forever. Threads and coroutines both fix that, and against a 10-connection pool
they land within ~1.4× of each other, because **the database is the bottleneck, not the driver.**

### The last line: what a parked thread really costs

`thread_cost()` parks 1000 threads at once and measures the change in resident memory, because the
usual claim — "8 MB of stack each" — is about *reserved virtual address space*, not RAM that exists.
The measured number is small.

Two things make that measurement correct rather than approximately correct, and both are commented in
the code:

- it runs **before** everything else, because `ru_maxrss` is a high-water mark that never goes down;
  measuring a delta after the sweep would always report zero;
- the threads are held parked on a `threading.Event` simultaneously, because a pool handed 1000 quick
  jobs just reuses a handful of threads and there would be nothing to measure.

So the cost of threads is not the memory. It is asking the kernel to schedule a thousand of them.
That gap is small at 1 000 concurrent requests and decisive at 100 000 — which is the only honest
reason to reach for an async driver.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `connection refused` on 5433 | Container not up: `docker compose up -d`, then check `docker compose ps` |
| `the database system is starting up` | The healthcheck has not passed yet; give it a second and retry |
| `port is already allocated` | Something else owns 5433. Change the **left** number in `docker-compose.yml` and the port in both `DSN`s |
| `ModuleNotFoundError: sync` | `sweep.py` imports its siblings — run it from inside this folder |
| `too many clients already` | You raised `CONNECTIONS` past Postgres's `max_connections` (100 by default) |
