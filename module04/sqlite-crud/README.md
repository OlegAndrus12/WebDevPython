# sqlite-crud — `sqlite3` vs `aiosqlite`, and what async does *not* buy you

Section 7 of [../AGENDA.md](../AGENDA.md). The same four operations — create, read, update, delete —
written twice against the same file-backed database.

| File | Driver | Notes |
| --- | --- | --- |
| [`sync.py`](sync.py) | `sqlite3` (stdlib) | The baseline. Nothing here is wrong |
| [`async_ex.py`](async_ex.py) | `aiosqlite` | The same code with `await` in front |

`contacts.db` is recreated from scratch on every run (`DB.unlink(missing_ok=True)`) and is
gitignored — you can delete it at any time.

## Run it

```bash
cd module04/sqlite-crud
uv run sync.py
uv run async_ex.py
```

No container, no server, no dependencies beyond `aiosqlite` (already in
[`../pyproject.toml`](../pyproject.toml)). Both print the same thing:

```
CREATE   3 rows inserted
READ
         (1, 'Олена Ковальчук', 'olena@example.com')
         (2, 'Петро Шевченко', 'petro@example.com')
         (3, 'Ірина Бондаренко', 'iryna@example.com')
UPDATE   1 row(s) changed
DELETE   1 row(s) removed
COUNT    2 contacts left

five operations in 12.0 ms -- and the thread was busy for every one of them.
```

…and `async_ex.py` reports single-digit milliseconds for the identical five operations. **That is the
result.** The async driver did not make anything faster, and it was never going to.

## The point of the exercise

There is **no such thing as a non-blocking SQLite call.** SQLite is a C library reading a file on
your disk; there is no socket to wait on and no protocol to suspend mid-flight. So `aiosqlite` runs
the ordinary blocking `sqlite3` driver on a dedicated worker thread and awaits the result — exactly
the trick from [`../06_thread_pool_from_asyncio.py`](../06_thread_pool_from_asyncio.py), packaged
behind a familiar API.

What that buys you is a **free event loop**, not a faster query. Worth having in a web app: the query
runs, and the other requests on that process are still answered. Worth nothing in a script, where
[`sync.py`](sync.py) is the better code.

## Reading the pair side by side

The APIs are deliberately the same shape, which is the other half of the lesson — you are not
learning a new database library, you are putting `await` in front of one you already know.

| | `sqlite3` | `aiosqlite` |
| --- | --- | --- |
| connect | `sqlite3.connect(DB)` | `async with aiosqlite.connect(DB) as db` |
| write | `db.executemany(sql, rows)` | `await db.executemany(sql, rows)` |
| commit | `db.commit()` | `await db.commit()` |
| read | `db.execute(sql).fetchall()` | `async with db.execute(sql) as cur: await cur.fetchall()` |
| placeholders | `?` | `?` — identical |

The one genuine difference is the cursor: in `aiosqlite` it is an async context manager, and it can
also be iterated with `async for` to **stream** rows instead of materialising all of them with
`fetchall()`.

## Details worth stealing

- **Placeholders, never f-strings.** `"... VALUES (?, ?)"` with a tuple is what stops SQL injection,
  and it also lets the driver reuse one prepared statement across all three seed rows.
- **`rowcount` is the answer to "did anything happen?"** Zero rows updated or deleted is not an
  error — it just did nothing. Reporting that difference is the caller's job.
- **`fetchone()` returns a tuple**, so a single `COUNT(*)` is `row[0]`. Easy to forget and it fails
  loudly.
- **`with closing(sqlite3.connect(DB)) as db, db:`** — two context managers on purpose, in that
  order. `closing(...)` releases the file handle; the connection's *own* `with` commits (or rolls
  back). Neither one does the other's job, and only both together are the complete idiom.
- **`async with aiosqlite.connect(...)` closes but does not commit**, so an uncommitted write at that
  point is simply lost. Same trap, opposite direction.
- **Timings are printed after the clock stops.** Writing to a terminal costs more than some of these
  queries do, and that is not what is being measured.

## Two loose ends in `async_ex.py`

The file defines a deliberately expensive recursive `REPORT` query (SQLite counting to 5 000 000) and
a `_start` timestamp for a demo the docstring describes — the ~1s query run first inline and then
through aiosqlite, while three cheap requests try to be served. **That half is not implemented:**
`main()` only calls `crud()`, and the closing lines about "the other three requests" refer to output
you will not see.

The pattern it describes is already fully worked in
[`../06_thread_pool_from_asyncio.py`](../06_thread_pool_from_asyncio.py) with `health_check(n)`
answering at 0.1s / 0.2s / 0.3s — reading that file is the substitute, and porting it to `REPORT` is
a good exercise.
