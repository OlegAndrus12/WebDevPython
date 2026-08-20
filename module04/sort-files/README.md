# sort-files — async file I/O, and the win that isn't

Section 5 of [../AGENDA.md](../AGENDA.md). The job is the Downloads folder everyone has: walk a
tree recursively and copy every file into `<output>/<EXT>/`, so images end up together, documents
together, and so on.

| File | Stack | Writes to |
| --- | --- | --- |
| [`sync.py`](sync.py) | `pathlib` + `shutil` | `Backup/` |
| [`async_ex.py`](async_ex.py) | `aiopath` + `aioshutil` | `Backup-async/` |

The source tree is [`picture/`](picture/) — 10 files, 5 of them one level down in `picture/icons/`,
which is what makes the walk recursive. Both scripts produce the same result: `jpg/` with 6 files and
`png/` with 4.

## Run it

```bash
cd module04/sort-files
uv run sync.py
uv run async_ex.py
```

Both write into a *different* output folder on purpose, so you can diff them:

```bash
diff -r Backup Backup-async && echo "identical"
```

> **Neither script prints anything.** `sync.py` counts the files it copied and imports
> `perf_counter`, but never uses either; `async_ex.py`'s `read_folder`/`copy_file` are annotated
> `-> int` and return `None`. Time them from the shell (`time uv run sync.py`) or add the prints —
> the timing is the interesting part and it is the part that is missing.

## The two versions, side by side

```python
# sync.py
for element in path.iterdir():          # blocking listing
    if element.is_dir():
        copied += read_folder(element, output)
    else:
        shutil.copyfile(file, target_dir / file.name)
```

```python
# async_ex.py
async for element in path.iterdir():    # AsyncPath, so async for
    if await element.is_dir():          # even the stat() is awaited
        tasks.append(read_folder(element, output))
    else:
        tasks.append(copy_file(element, output))
await asyncio.gather(*tasks)            # the whole tree at once
```

Note the recursion in the async version: `read_folder` appends *itself* to `tasks` for
subdirectories, so a subdirectory's own `gather` is nested inside the parent's. The whole tree is
collected into coroutines and then run together, rather than depth-first one file at a time.

`AsyncPath` mirrors `pathlib.Path` — `.suffix`, `/`, `.mkdir(parents=True, exist_ok=True)` — with
`await` in front. `aioshutil.copyfile` mirrors `shutil.copyfile`. Learning the async version is
learning where to put `await`, not learning a new API.

## Read the timings honestly

On a local SSD this is **not** dramatically faster, and on this small a tree the async version is
usually *slower*:

```
sync.py       0.11s total
async_ex.py   0.26s total
```

Two reasons, and both are the lesson:

1. **Copying files is syscall-bound, not latency-bound.** There is no round trip to overlap. The
   kernel is not "waiting" on a local SSD the way it waits on a socket.
2. **`aiopath` and `aioshutil` hand the work to a thread pool anyway.** There is no non-blocking
   `copyfile()` syscall to call — same trick as `aiosqlite` in
   [`../sqlite-crud/`](../sqlite-crud/), and it costs a thread hand-off per file.

What you actually gain is that a web server doing this in the background **keeps answering
requests** — the loop stays free. That is worth having, and it is a different claim from "faster".
Point a large tree on a network share at it and the numbers change again, because then there *is*
latency to overlap.

## Details worth stealing

- `BASE_DIR = Path(__file__).parent` — every path is anchored to the file, not the working
  directory, so the scripts run from anywhere.
- `file.suffix.lstrip(".").lower() or "other"` — `.JPG` and `.jpg` are one folder, and a file with no
  extension has somewhere to go instead of crashing.
- `sync.py` refuses to start if `picture/` is missing (`raise SystemExit`) rather than failing
  halfway through a copy. `async_ex.py` does not — try deleting the folder and compare the errors.

## Reset

```bash
rm -rf Backup Backup-async
```

Both are committed to the repo so you can see the expected shape, but they are pure output — the
scripts recreate them.
