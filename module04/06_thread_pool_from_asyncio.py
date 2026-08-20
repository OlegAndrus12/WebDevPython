"""4. Блокуючий код: один синхронний виклик заморожує весь event loop.

Real job: the same reporting endpoint, now inside an async web app that is also
serving ordinary requests. `render_report` is synchronous, so there is nothing to
await -- and a coroutine that never awaits never gives the loop back. Every other
request on that process stops dead until it returns.

The proof below is three cheap async requests that should answer at 0.1s, 0.2s and
0.3s. Watch the timestamps they actually print.

    poetry run python 06_thread_pool_from_asyncio.py
"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

from libs import async_timed

REPORTS = ["sales-q1", "sales-q2", "sales-q3", "sales-q4", "payroll"]
WORKERS = 3
RENDER = 0.5

_start = 0.0


def render_report(name: str) -> str:
    """Blocking. No `await` is possible here, so asyncio alone cannot help."""
    time.sleep(RENDER)
    return f"{name}.pdf"


async def health_check(n: int) -> None:
    """An ordinary async request: nothing blocking, should answer at n * 0.1s."""
    await asyncio.sleep(n * 0.1)
    print(f"   [request #{n}] answered at {time.perf_counter() - _start:.2f}s")


@async_timed("reports rendered inside the coroutine")
async def render_blocking() -> list[str]:
    # No await in sight. This coroutine owns the loop for the full 2.5s.
    return [render_report(name) for name in REPORTS]


@async_timed("reports handed to asyncio.to_thread")
async def render_in_threads() -> list[str]:
    # to_thread() runs the blocking call on the loop's own default executor and
    # gives back an awaitable -- so the loop is free while the threads wait.
    return await asyncio.gather(
        *(asyncio.to_thread(render_report, name) for name in REPORTS)
    )


@async_timed("reports on a pool we own")
async def render_on_own_pool() -> list[str]:
    loop = asyncio.get_running_loop()
    # run_in_executor is the version that lets you pass *your* pool: a smaller cap,
    # a thread name prefix, a pool shared with the rest of the app. The default
    # executor to_thread uses is wide (min(32, cpu+4)); ours caps at WORKERS, so
    # the same five reports take two waves instead of one.
    with ThreadPoolExecutor(max_workers=WORKERS, thread_name_prefix="pdf") as pool:
        return await asyncio.gather(
            *(loop.run_in_executor(pool, render_report, name) for name in REPORTS)
        )
        # Note: leaving the `with` block joins every thread, and that join is itself
        # blocking. It is free here only because gather already awaited them all.


async def serve(render) -> None:
    """Run one report render alongside three cheap requests, as a real app would."""
    global _start
    _start = time.perf_counter()
    await asyncio.gather(render(), *(health_check(n) for n in (1, 2, 3)))


if __name__ == "__main__":
    asyncio.run(serve(render_blocking))
    print("   ^ nobody was answered until the render was over. The loop was frozen,")
    print("     so their sleep timers never even got a chance to start.\n")

    asyncio.run(serve(render_in_threads))
    print("   ^ 0.1s, 0.2s, 0.3s -- on time, while five reports rendered.\n")

    asyncio.run(serve(render_on_own_pool))
    print(f"   ^ still on time, but the reports took two waves: {WORKERS} workers.\n")

    print("Rule: anything without `await` in front of it runs on the event loop.")
    print("If it can block for longer than a millisecond, it belongs in a thread.")
