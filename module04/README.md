# Module 04 — asyncio, threads and blocking I/O

Thirteen scripts and four folders, all answering the same question from different sides: **what does
`async` actually buy you, and when does it buy you nothing?**

The honest answer is narrow. Async overlaps *waiting*. It does not add processing power, it does not
make a query faster, and it does not help code that computes. Every file here either demonstrates
the win or takes it away again, and each one prints its own timings — nothing in this module asks you
to take a number on trust.

| # | Section | Files | The idea |
| --- | --- | --- | --- |
| 1 | Why bother | [`02_sync_vs_async.py`](02_sync_vs_async.py) | 16 sites, one by one vs. all at once |
| 2 | asyncio basics | [`01_coroutine_object.py`](01_coroutine_object.py), [`02_await_is_sequential.py`](02_await_is_sequential.py) | A coroutine is not a running coroutine; `await` is not parallelism |
| 3 | Running things together | [`03_gather_with_exeption.py`](03_gather_with_exeption.py), [`04_task_*.py`](.), [`05_wait_first_completed.py`](05_wait_first_completed.py) | `gather`, `create_task`, `wait(FIRST_COMPLETED)` |
| 4 | Blocking code | [`06_thread_pool_*.py`](.) | Threads, the event loop, and the GIL |
| 5 | Files | [`sort-files/`](sort-files/) | `aiopath` + `aioshutil` vs. `pathlib` + `shutil` |
| 6 | HTTP | [`download_files.py`](download_files.py), [`exchange-rate/`](exchange-rate/) | Streaming downloads; a real API, 30 requests |
| 7 | SQLite | [`sqlite-crud/`](sqlite-crud/) | `sqlite3` vs. `aiosqlite` — and what aiosqlite is not |
| 8 | PostgreSQL | [`postgres-crud/`](postgres-crud/) | `psycopg` vs. `asyncpg`, swept by concurrency |

Read them in that order — the numeric prefixes are the reading order, and each folder has its own
README. Full topic list: **[AGENDA.md](AGENDA.md)**.

---

## Prerequisites

```bash
python3 --version          # 3.12+ ; this doc was checked against 3.12.13
uv --version               # checked against 0.11.4
docker --version           # only for postgres-crud/
```

```bash
cd module04
uv sync
```

Every script is standalone and run **from this directory**, so the flat `from libs import ...`
works — the script's own directory is on `sys.path`:

```bash
uv run 02_sync_vs_async.py
```

The two `-crud/` folders and `exchange-rate/` are run from *inside* themselves, because they import
their own siblings (`from chart import save_chart`, `from sync import DSN`):

```bash
cd exchange-rate && uv run sync.py
```

> **Four dependencies are missing from [`pyproject.toml`](pyproject.toml).** The manifest declares
> the database, file and chart packages, but the HTTP examples also need these:
>
> ```bash
> uv add aiohttp aiofiles requests faker
> ```
>
> Without them `02_sync_vs_async.py`, `download_files.py`, `01_coroutine_object.py` and
> `exchange-rate/` fail with `ModuleNotFoundError`. Everything else runs on a bare `uv sync`.

## Four rules that hold for the whole module

1. Calling an `async def` function **runs nothing**. It builds a coroutine object; the loop runs it.
2. `await` means *"suspend me until this is done"* — it is a **sequencing** keyword, not a
   parallelism one. Concurrency comes from `gather`, `create_task` or `wait`, never from `await`
   alone.
3. Anything without `await` in front of it runs **on the event loop**. If it can block for more than
   a millisecond, it belongs in a thread.
4. Threads help code that **waits**. Processes help code that **computes**. Deciding which you have
   is the entire skill.

---

## 1 · Why bother — [`02_sync_vs_async.py`](02_sync_vs_async.py)

An uptime checker over 16 sites. `requests` in a loop, then `aiohttp` inside one `gather`, both
wrapped in the timing decorators from [`libs.py`](libs.py).

```bash
uv run 02_sync_vs_async.py
```

The sync run costs the **sum** of sixteen round trips; the async run costs the **slowest single
one**. The CPU was idle throughout either way — which is the whole point. One `ClientSession` is
shared across all sixteen requests, so they also reuse TCP connections.

## 2 · asyncio basics

### [`01_coroutine_object.py`](01_coroutine_object.py) — a coroutine is a description of work

Two demos in one file (both run). The first prints the coroutine object *before* awaiting it, awaits
it, then awaits it a second time to get the `RuntimeError` — a coroutine is not a reusable recipe —
and finally creates one and drops it, which is the classic beginner bug and produces
`RuntimeWarning: coroutine 'fetch_user' was never awaited`. The second is `asyncio.run()` at its
smallest: create the loop, run one coroutine, close the loop, hand back the return value.

### [`02_await_is_sequential.py`](02_await_is_sequential.py) — `async def` alone buys nothing

A profile page needs a user record (0.4s), their orders (0.6s) and recommendations (0.5s) from three
services, none depending on the others. Written as three `await`s in a row it takes **1.5s** — the
sum. This file exists to be fixed by the next one.

## 3 · Running things together

### [`03_gather_with_exeption.py`](03_gather_with_exeption.py) — all of them, and what a failure does

The same profile page handed to `asyncio.gather`, so total time is the slowest call rather than the
sum. Then the two things people trip over:

- results come back in **argument order**, not completion order;
- by default the **first exception propagates immediately** and the results that already succeeded
  are thrown away. `return_exceptions=True` turns failures into values instead, so a recommendation
  outage degrades the page rather than killing it.

Both variants run: `build_profile` (degrading) and `build_profile_strict` (raising).

> Two things to know about this file: the filename has a typo (`exeption`), and its three services
> all `sleep(5)`, so the closing line still quotes `0.6s instead of 1.5s` from an earlier version of
> the numbers. Read the decorator output, not that line.

### [`04_task_start_now_await_later.py`](04_task_start_now_await_later.py) — the handle is the point

`create_task()` returns a handle, and the value of the handle is that **the line that starts the
work and the line that awaits it can be different lines**, with anything in between — including an
`if` that decides not to await at all. That is exactly what `gather` cannot do: `gather(a(), b())`
starts *and* awaits in one expression, so when you always want both results, `gather` is simpler and
you should use it.

Here `POST /register` sends the welcome email either way. The audit-log write (0.3s) happens while
SMTP is talking, and awaiting the task afterwards is 0.3s cheaper than starting it then.

### [`04_task_fire_and_forget.py`](04_task_fire_and_forget.py) — don't bill the client for SMTP

Same endpoint, 0.05s of `INSERT` and 1.2s of email. `create_task` hands the coroutine to the loop
and returns *now*, so the response goes out at 0.05s. Two traps, both in the file:

- calling `send_welcome_email(user)` with neither `create_task` nor `await` does **nothing at all**;
- a Task lives only as long as its loop. `asyncio.run()` returning cancels it — in a web app the loop
  outlives the request, in this script we have to wait on purpose.

### [`04_task_lost_exception.py`](04_task_lost_exception.py) — where a background failure goes

Nowhere, if nobody owns the task. Registration returns `200`, the email never went out, and the
traceback surfaces as asyncio's destructor complaining on stderr — not through your logger, not
catchable, and only if nothing else holds a reference (`asyncio.all_tasks()` is a *weak* set, which
is why the docs tell you to save the handle).

The fix is two lines: keep the handle, and `task.add_done_callback(report)`. The callback is an
ordinary sync function, runs the instant the task ends, and calls `task.exception()` — which
*returns* the exception instead of raising it. That is where you log, retry, or write to a
dead-letter table.

### [`05_wait_first_completed.py`](05_wait_first_completed.py) — the first answer wins

A hedged request: three geocoding providers, ask all of them, take whoever answers first, cancel the
rest. `asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)` returns `(done, pending)`; you
`cancel()` the pending ones and then `gather(*pending, return_exceptions=True)` to let them actually
unwind. Note where `CancelledError` arrives — *inside* the cancelled coroutine, which catches it to
log and then **re-raises**, as cancellation handlers must.

This is how CDNs and DNS resolvers cut tail latency: total time is the fastest provider, not the
average.

## 4 · Blocking code, threads and the GIL

### [`06_thread_pool_basics.py`](06_thread_pool_basics.py) — a pool is a queue with N servers

No asyncio in this file at all: `ThreadPoolExecutor` is plain stdlib concurrency and works in a
codebase with no event loop. Six report renders (one of which raises), three workers.

- `submit()` returns a `Future` **immediately** — the work is queued, not done. The
  `{future: name}` dict is how you remember which job each Future was.
- `as_completed()` yields in **finish** order, unlike `gather`, which preserves input order.
- A worker's exception is re-raised at `.result()` — not at `submit()`, and not inside the pool
  where it would vanish. Same `try/except` as the sequential version, moved.
- Five slow jobs over three workers is **two waves**. `max_workers` is the number you have to get
  right; a pool is not unlimited parallelism.

### [`06_thread_pool_from_asyncio.py`](06_thread_pool_from_asyncio.py) — one sync call freezes everything

The same renders, now inside an async app that is also serving three cheap requests which *should*
answer at 0.1s, 0.2s and 0.3s. Run it and read the timestamps: with the renders done inline they all
answer at ~2.5s, because a coroutine with no `await` in it never gives the loop back — their sleep
timers never even started.

Then the two fixes, both shown:

| | What it is | Executor |
| --- | --- | --- |
| `asyncio.to_thread(fn, *args)` | The one-liner. Returns an awaitable | The loop's default pool — wide, `min(32, cpu+4)` |
| `loop.run_in_executor(pool, fn, *args)` | The version that takes *your* pool | Yours: a cap, a `thread_name_prefix`, shared with the app |

With `WORKERS = 3` the second one takes two waves rather than one — the same trade-off as the file
above. Note also that leaving the `with ThreadPoolExecutor(...)` block **joins** every thread, and
that join is itself blocking; it is free here only because `gather` already awaited them all.

### [`06_thread_pool_gil_limit.py`](06_thread_pool_gil_limit.py) — where threads stop helping

Four CPU-bound jobs (`sum(i * i for i in range(n))`), no sleep, no socket, nothing to wait for. Four
threads should be ~4x faster and are not: the result lands within a few percent of sequential, either
side, because the GIL lets one thread execute bytecode at a time and they spend their lives handing
it back and forth.

`ProcessPoolExecutor` is the same API with one word changed, and it does deliver — its floor is the
biggest single job, not the total. Two things it costs you: arguments and results are **pickled**
(so give workers small inputs, not big payloads), and the `if __name__ == "__main__":` guard becomes
mandatory, because every child re-imports the module.

> The test is never "is it slow", it is **"is it waiting or computing"**:
> waiting (network, disk, a sync DB driver) → `ThreadPoolExecutor`;
> computing (parsing, image resize, math) → `ProcessPoolExecutor`.

## 5–8 · The four projects

Each folder holds a `sync.py` / `async_ex.py` pair doing identical work, so the only variable is how
the waiting is handled. Each has its own README.

| Folder | Pair | What it really shows |
| --- | --- | --- |
| [`sort-files/`](sort-files/) | `pathlib`+`shutil` / `aiopath`+`aioshutil` | Async file I/O is a thread pool in a costume — barely faster on SSD, but the server keeps answering |
| [`exchange-rate/`](exchange-rate/) | `requests` / `aiohttp` | A real public API, 30 requests, a `Semaphore` because 30 at once is rude |
| [`sqlite-crud/`](sqlite-crud/) | `sqlite3` / `aiosqlite` | There is no non-blocking SQLite call. Same milliseconds, free event loop |
| [`postgres-crud/`](postgres-crud/) | `psycopg` / `asyncpg` | Sequential CRUD: no difference. [`sweep.py`](postgres-crud/sweep.py) changes the one variable that matters |

[`download_files.py`](download_files.py) sits at the top level and belongs to section 6: `aiohttp`
streaming into `aiofiles`, `iter_chunked(64 KB)` instead of `await response.read()`, so a 2 GB file
costs 64 KB of memory. It also deletes the half-written file when a download fails, which is the
part people forget.

---

## asyncio cheat sheet

### Getting into the loop

```python
asyncio.run(main())                 # the only entry point from sync code
asyncio.get_running_loop()          # inside a coroutine, when you need the loop itself
```

### Running more than one thing

| Call | Waits for | Order of results | On failure |
| --- | --- | --- | --- |
| `await a(); await b()` | each in turn | n/a — sequential | raises at that line |
| `asyncio.gather(a(), b())` | all | **argument** order | first exception propagates, rest lost |
| `asyncio.gather(..., return_exceptions=True)` | all | argument order | exceptions become values |
| `asyncio.create_task(a())` | nothing yet | you `await` the handle later | silent, unless you add a callback |
| `asyncio.wait(tasks, return_when=...)` | as configured | `(done, pending)` sets | you inspect each task |
| `async with asyncio.TaskGroup() as tg:` | all, at block exit | via each task handle | cancels siblings, raises `ExceptionGroup` |

`return_when` takes `ALL_COMPLETED` (default), `FIRST_COMPLETED`, `FIRST_EXCEPTION`.

`TaskGroup` (3.11+) is the modern default for "these must all finish"; this module uses `gather` and
raw tasks because they are what the failure modes are easiest to *see* with.

### Tasks

```python
task = asyncio.create_task(coro(), name="welcome-email")
task.done()                       # bool, no waiting
task.cancel()                     # raises CancelledError *inside* the coroutine
task.exception()                  # returns the exception (or None); does not raise it
task.result()                     # the value — or re-raises what the task raised
task.add_done_callback(fn)         # sync fn, called by the loop the instant it ends
await task                        # fine to do twice: the result is cached
```

Keep a reference to every task you create. `asyncio.all_tasks()` is a weak set and will not keep it
alive for you.

### Blocking calls

```python
await asyncio.to_thread(blocking_fn, arg)              # default executor, simplest
await loop.run_in_executor(my_pool, blocking_fn, arg)  # your pool, your cap
await asyncio.sleep(1)        # never time.sleep(1) inside a coroutine
```

### Throttling and timeouts

```python
sem = asyncio.Semaphore(8)
async with sem: ...                                    # at most 8 in flight

async with asyncio.timeout(5): ...                     # 3.11+, cancels the block
await asyncio.wait_for(coro, timeout=5)                # older spelling, one awaitable

aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30, connect=5))
```

### concurrent.futures

```python
with ThreadPoolExecutor(max_workers=3, thread_name_prefix="pdf") as pool:
    futures = {pool.submit(fn, x): x for x in jobs}    # returns immediately
    for future in as_completed(futures):               # finish order
        future.result()                                # re-raises the worker's exception
    list(pool.map(fn, jobs))                           # input order, no per-item handling
```

`ProcessPoolExecutor` is the same interface. `__exit__` waits for every worker, and that wait
blocks.

---

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `RuntimeWarning: coroutine '...' was never awaited` | You called an `async def` and dropped the result. Add `await` or `create_task`. |
| `ModuleNotFoundError: No module named 'libs'` | You are not running from `module04/`. `cd module04` first. |
| `ModuleNotFoundError: aiohttp` / `requests` / `faker` / `aiofiles` | See the note in [Prerequisites](#prerequisites) — `uv add` them. |
| `RuntimeError: cannot reuse already awaited coroutine` | A coroutine object is single-use. Call the function again, or use a Task (which caches its result). |
| `RuntimeError: asyncio.run() cannot be called from a running event loop` | You are already inside one — `await` instead. |
| Nothing is concurrent, timings equal the sum | Three `await`s in a row. See [`02_await_is_sequential.py`](02_await_is_sequential.py). |
| Other requests hang while one handler runs | A blocking call on the loop. See [`06_thread_pool_from_asyncio.py`](06_thread_pool_from_asyncio.py). |
| Threads gave no speed-up at all | The work computes rather than waits. See [`06_thread_pool_gil_limit.py`](06_thread_pool_gil_limit.py). |
| `Task was destroyed but it is pending!` | The loop closed with a task still running. Await it, or keep the loop alive. |
| A background task fails silently | Nobody owns it. See [`04_task_lost_exception.py`](04_task_lost_exception.py). |
| `connection refused` on port 5433 | The `postgres-crud/` container is not up: `cd postgres-crud && docker compose up -d`. |

> The docstrings in a few files still name earlier filenames (`03_coroutine_object.py`,
> `05_gather.py`, `18_download_files.py`) and `poetry run` rather than `uv run`. The commands in
> this README are the current ones.
