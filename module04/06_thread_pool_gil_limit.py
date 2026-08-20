"""4. Блокуючий код: де потоки перестають допомагати -- GIL.

Threads help code that *waits*. They do nothing for code that *computes*, because
the GIL lets only one thread execute Python bytecode at a time.

So this file drops the reporting story and uses the simplest CPU-bound function
there is: add up n squares. No sleep, no socket, no file -- nothing to wait for,
nothing for threads to overlap. Same ThreadPoolExecutor as the other two files,
four independent jobs, and the speed-up simply does not appear.

    poetry run python 06_thread_pool_gil_limit.py
"""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor

from libs import timed

# Four independent jobs, listed once and given to all three runs below, so the
# timings compare executors and nothing else. Different sizes on purpose: with
# four identical numbers you cannot tell a real result from a lucky one.
JOBS = [5_000_000, 6_000_000, 4_000_000, 7_000_000]
WORKERS = len(JOBS)


def sum_of_squares(n: int) -> int:
    """Pure CPU. Every iteration needs the GIL, and none of them ever waits."""
    return sum(i * i for i in range(n))


@timed(f"{len(JOBS)} jobs, one by one")
def run_sequential() -> list[int]:
    return [sum_of_squares(n) for n in JOBS]


@timed(f"{len(JOBS)} jobs, {WORKERS} threads")
def run_in_threads() -> list[int]:
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        # map() is the shortcut when you want results in input order and no
        # per-item error handling -- same signature as the builtin map().
        return list(pool.map(sum_of_squares, JOBS))


@timed(f"{len(JOBS)} jobs, {WORKERS} processes")
def run_in_processes() -> list[int]:
    # Identical API, one word changed. Each worker is a separate interpreter with
    # its own GIL, so they run on real cores. Note what crosses the process
    # boundary: one int in, one int out. Arguments and results are pickled, so
    # workers should be given small inputs, not big payloads.
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(sum_of_squares, JOBS))


if __name__ == "__main__":  # required: child processes re-import this module
    one_by_one = run_sequential()
    threaded = run_in_threads()
    processed = run_in_processes()

    # Same jobs, same answers, three executors: the only difference is who ran it.
    assert one_by_one == threaded == processed
    print(f"\nall three computed the same {len(JOBS)} sums, "
          f"{sum(JOBS):,} iterations each time.")

    print(f"\n{len(JOBS)} independent jobs on {WORKERS} threads should be "
          f"~{WORKERS}x faster.")
    print("It is not: it lands within a few percent of sequential, either side,")
    print("because the threads spend their time handing the GIL back and forth")
    print("instead of running at once.")
    print("\nProcesses do deliver it -- their floor is the biggest single job")
    print(f"({max(JOBS):,} iterations), not the total ({sum(JOBS):,}).")
    print("\nThe test is not 'is it slow', it is 'is it waiting or computing':")
    print("  waiting   (network, disk, sync DB driver) -> ThreadPoolExecutor")
    print("  computing (parsing, image resize, math)   -> ProcessPoolExecutor")
