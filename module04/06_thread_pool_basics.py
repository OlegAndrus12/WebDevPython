"""4. Блокуючий код: ThreadPoolExecutor -- пул це черга з N виконавцями.

Real job: a reporting endpoint. The PDF library is synchronous, ten years old, and
nobody is going to rewrite it as `async def`. Five reports one after another take
five times as long as one -- and the process spends all of it *waiting* on the
library, not computing. That is what a thread pool is for.

No asyncio in this file: ThreadPoolExecutor is plain stdlib concurrency and works
the same in a codebase that has no event loop at all.

    poetry run python 06_thread_pool_basics.py
"""
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from libs import timed

BROKEN = "vat"  # raises instead of rendering, to show where a worker's error goes

# One workload, shared by both runs below, so the timings compare execution
# strategies and nothing else -- same six jobs, same failing one among them.
JOBS = ["sales-q1", "sales-q2", "sales-q3", "sales-q4", "payroll", BROKEN]
WORKERS = 3
RENDER = 0.5


def render_report(name: str) -> str:
    """The blocking call. `time.sleep` stands in for a sync library we cannot await."""
    if name == BROKEN:
        raise ValueError(f"{name}: template missing")
    time.sleep(RENDER)
    return f"{name}.pdf"


@timed(f"{len(JOBS)} reports, one by one")
def render_sequential() -> list[str]:
    done = []
    for name in JOBS:
        try:
            done.append(render_report(name))
        except ValueError as err:
            print(f"   skipped {name}: {err}")
    return done


@timed(f"{len(JOBS)} reports, pool of {WORKERS}")
def render_in_pool() -> list[str]:
    # The pool is a context manager: __exit__ waits for every worker to finish.
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        # submit() returns a Future *immediately* -- the work is queued, not done.
        # The dict remembers which name each Future belongs to.
        futures = {pool.submit(render_report, name): name for name in JOBS}

        done = []
        # as_completed yields Futures in the order they *finish*, not the order they
        # were submitted -- unlike asyncio.gather, which preserves input order.
        for future in as_completed(futures):
            try:
                # Same try/except as the sequential version, moved: the worker's
                # exception is re-raised here at .result(), not at submit() and
                # not inside the pool, where it would be lost.
                done.append(future.result())
            except ValueError as err:
                print(f"   skipped {futures[future]}: {err}")
        return done


if __name__ == "__main__":
    one_by_one = render_sequential()
    pooled = render_in_pool()

    # Same jobs in, same reports out -- as_completed only changed the order.
    assert sorted(one_by_one) == sorted(pooled)
    print(f"\nboth runs produced the same {len(pooled)} PDFs "
          f"(the pool just returned them out of order).")

    slow = len(JOBS) - 1  # vat fails instantly, so it never occupies a worker
    waves = math.ceil(slow / WORKERS)
    print(f"\n{slow} slow reports over {WORKERS} workers = {waves} waves, "
          f"so ~{waves * RENDER:.1f}s, not {RENDER:.1f}s.")
    print("A pool is a queue with a fixed number of servers, not unlimited")
    print("parallelism. max_workers is the number you have to get right.")
