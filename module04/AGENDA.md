# Module 04 — Agenda

Eight sections that answer one question in order: *what does `async` actually buy you, and when
does it buy you nothing at all?* The module opens with the only case where async wins outright —
sixteen HTTP requests that are 99% waiting — then immediately takes it back: a coroutine that is
never awaited does nothing, and three `await`s in a row are as sequential as three function calls.
From there the tools arrive one at a time, each because the previous one could not do the job:
`gather` when you want all the results, a `Task` handle when "do I need this?" is answered later,
`wait` when you only want the first answer. Section 4 draws the line the whole module is built
around — **waiting is not computing** — and everything after it is that line applied to real I/O:
files, HTTP against a live API, SQLite, Postgres. The last file is the honest one: the async driver
wins only when the request count is large enough for a thread's scheduling cost to matter.
Runnable file list, timings and the cheat sheet live in [README.md](README.md).

## Topics

### 1 · Why bother at all
- **Waiting is the whole cost** (`02_sync_vs_async.py`) — sixteen sites checked with `requests` one
  by one, then with `aiohttp` together: the sync version takes the *sum* of the latencies, the async
  version the *slowest single one*
- **The shape of the win** — the CPU is idle either way; concurrency here buys overlap of waiting,
  never more processing power
- **What `@timed` / `@async_timed` do** (`libs.py`) — every claim in this module is printed by a
  decorator, not asserted in prose

### 2 · asyncio basics
- **A coroutine object is not a running coroutine** (`01_coroutine_object.py`) — calling an
  `async def` builds a description of work; `print(coro)` shows it; `await` is what hands it to the
  loop; a coroutine can be awaited exactly once
- **The classic bug** — a coroutine created and dropped: `RuntimeWarning: coroutine ... was never
  awaited`, and the query that never happened
- **`asyncio.run()`** — creates the loop, runs one coroutine to completion, closes the loop, returns
  the value; the single entry point from sync code
- **`asyncio.sleep` vs `time.sleep`** — the async twin that waits without blocking anyone else
- **`await` is not parallelism** (`02_await_is_sequential.py`) — a profile page over three
  independent services, written as three `await`s in a row: 0.4 + 0.6 + 0.5 = 1.5s. `async def`
  alone bought nothing

### 3 · Running things at the same time
- **`asyncio.gather`** (`03_gather_with_exeption.py`) — start these together, wait for all of them;
  total time is the slowest, not the sum; results come back in *argument* order, not completion order
- **One failure kills the batch** — the first exception propagates and the results that already
  succeeded are lost; `return_exceptions=True` turns failures into values instead, which is what a
  page that can degrade actually wants
- **`asyncio.create_task`: start now, decide later** (`04_task_start_now_await_later.py`) — the
  handle is the point: the line that starts the work and the line that awaits it can be different
  lines, with an `if` in between. What `gather` cannot do
- **Fire and forget** (`04_task_fire_and_forget.py`) — don't make the client wait for the welcome
  email; a coroutine that is never scheduled never runs; a Task lives only as long as its loop
- **A lost exception** (`04_task_lost_exception.py`) — an unowned task keeps its failure to itself
  and reports 200; `all_tasks()` is a *weak* set, so keep the handle; `add_done_callback` is the one
  place a background failure is guaranteed to arrive
- **`asyncio.wait` and `FIRST_COMPLETED`** (`05_wait_first_completed.py`) — a hedged request: ask
  three geocoders, take whoever answers first, cancel the rest; `CancelledError` arrives *inside*
  the cancelled coroutine and must be re-raised

### 4 · Blocking code, threads, and the GIL
- **A pool is a queue with N servers** (`06_thread_pool_basics.py`) — `ThreadPoolExecutor` with no
  asyncio at all; `submit` returns a `Future` immediately; `as_completed` yields in *finish* order;
  a worker's exception surfaces at `.result()`, nowhere else; six jobs over three workers is two
  waves, not one
- **One sync call freezes the whole loop** (`06_thread_pool_from_asyncio.py`) — three cheap requests
  that should answer at 0.1s / 0.2s / 0.3s and answer at 2.5s instead, because the coroutine
  rendering PDFs never gave the loop back
- **`asyncio.to_thread` vs `loop.run_in_executor`** — the one-liner on the loop's default executor
  (wide: `min(32, cpu+4)`) versus your own pool with your own cap and thread names
- **Where threads stop helping** (`06_thread_pool_gil_limit.py`) — pure CPU work on four threads
  lands within a few percent of sequential, because only one thread runs bytecode at a time;
  `ProcessPoolExecutor` is the same API with one word changed, and it does deliver
- **The test that decides** — not "is it slow" but "is it waiting or computing": waiting → threads,
  computing → processes

### 5 · Files
- **Sorting a folder** (`sort-files/`) — walk a tree recursively, copy every file into
  `output/<EXT>/`; `pathlib` + `shutil` first, then `aiopath` + `aioshutil`
- **The honest reading** — on a local SSD the async version is *not* dramatically faster: copying is
  syscall-bound, and `aiopath`/`aioshutil` hand the work to a thread pool anyway. What you gain is a
  server that keeps answering while it runs
- **Anchoring paths** — `Path(__file__).parent`, so the script works from any working directory

### 6 · HTTP requests
- **Streaming downloads** (`download_files.py`) — `aiohttp` + `aiofiles`; `iter_chunked(64 KB)`
  instead of `await response.read()`, so a 2 GB file costs 64 KB of memory; `raise_for_status()`;
  deleting the truncated file on failure
- **A real API** (`exchange-rate/`) — the NBU exchange-rate endpoint answers one date per request,
  so 30 days is 30 requests; sync baseline versus concurrent, charted with matplotlib
- **Being a good citizen** — one `ClientSession` for the whole batch, a total `ClientTimeout`, and a
  `Semaphore` cap: 30 requests at once against a public API is rude, not clever
- **Per-request error handling** — one bad day must not lose the other 29

### 7 · SQLite
- **CRUD with `sqlite3`** (`sqlite-crud/sync.py`) — one function per operation; placeholders, never
  f-strings; `rowcount` as the difference between "changed a row" and "matched nothing";
  `closing(...)` releases the handle while the connection's own `with` only commits
- **The same four with `aiosqlite`** (`sqlite-crud/async_ex.py`) — deliberately the same API shape
  with `await` in front, plus cursors as async context managers
- **What aiosqlite is not** — there is no such thing as a non-blocking SQLite call: it runs the
  ordinary blocking driver on a worker thread. The section-4 trick, packaged. It buys a free event
  loop, not a faster query — the five operations take the same milliseconds as `sync.py`

### 8 · PostgreSQL, and the honest benchmark
- **`psycopg` vs `asyncpg`** (`postgres-crud/`) — the same four operations, timed at 1 000,
  100 000 and 1 000 000 rows; `%s` placeholders versus numbered `$1`; `rowcount` versus a status
  string like `'UPDATE 1'`; a throwaway Postgres on port 5433 with `tmpfs` storage
- **Sequential CRUD shows no difference** — and that is the correct result: one request at a time
  has nothing to overlap
- **The variable that matters** (`postgres-crud/sweep.py`) — concurrency, swept 1 → 1000, with the
  same SQL, the same 10-connection pool, and only the waiting strategy changed: a parked OS thread
  per request versus a suspended coroutine
- **What a parked thread really costs** — measured resident memory, not the usual "8 MB of stack"
  claim (that is reserved address space); the cost is asking the kernel to schedule a thousand
  threads, not the RAM
- **When to reach for an async driver** — against a 10-connection pool the two land within ~1.4x of
  each other, because the database is the bottleneck. The gap is small at 1 000 concurrent requests
  and decisive at 100 000
