# Module 04 — Agenda

- **Why bother at all** (`02_sync_vs_async.py`) — waiting is the whole cost, not computing
- **asyncio basics** (`01_coroutine_object.py`, `02_await_is_sequential.py`) — coroutine objects, `asyncio.run()`, why sequential `await` buys nothing
- **Running things at the same time** (`03-05_*.py`) — `gather`, `create_task`, fire-and-forget, `wait`
- **Blocking code, threads, and the GIL** (`06_*.py`) — `ThreadPoolExecutor`, `to_thread`, where threads stop helping, `ProcessPoolExecutor`
- **Files** (`sort-files/`) — sync vs. async folder walk
- **HTTP requests** (`download_files.py`, `exchange-rate/`) — streaming downloads, concurrent calls to a real API
- **SQLite** (`sqlite-crud/`) — `sqlite3` vs. `aiosqlite`
- **PostgreSQL** (`postgres-crud/`) — `psycopg` vs. `asyncpg`, a concurrency sweep, the honest benchmark
