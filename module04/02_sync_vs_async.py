"""1. Вступ: навіщо взагалі асинхронність.

Real-life task: an uptime checker. We have a list of sites and we want to know
which of them are alive right now.

The work is 99% *waiting for the network*. The CPU is idle the whole time -- so
doing the requests one after another is pure waste. Run the file and compare the
two timings at the bottom.

    poetry run python 02_sync_vs_async.py
"""
import asyncio

import aiohttp
import requests

from libs import async_timed, timed

SITES = [
    "https://www.python.org",
    "https://docs.python.org",
    "https://pypi.org",
    "https://github.com",
    "https://duckduckgo.com",
    "https://www.wikipedia.org",
    "https://httpbin.org/get",
    "https://api.github.com",
    "https://stackoverflow.com",
    "https://developer.mozilla.org",
    "https://www.djangoproject.com",
    "https://flask.palletsprojects.com",
    "https://fastapi.tiangolo.com",
    "https://docs.aiohttp.org",
    "https://www.postgresql.org",
    "https://redis.io",
]

TIMEOUT = 10


@timed("sync (requests, one by one)")
def check_all_sync(urls: list[str]) -> list[tuple[str, str]]:
    results = []
    for url in urls:
        try:
            response = requests.get(url, timeout=TIMEOUT)
            results.append((url, str(response.status_code)))
        except requests.RequestException as err:
            results.append((url, f"ERROR: {type(err).__name__}"))
    return results


async def check_one(session: aiohttp.ClientSession, url: str) -> tuple[str, str]:
    try:
        async with session.get(url) as response:
            return url, str(response.status)
    except (aiohttp.ClientError, asyncio.TimeoutError) as err:
        return url, f"ERROR: {type(err).__name__}"


@async_timed("async (aiohttp, all at once)")
async def check_all_async(urls: list[str]) -> list[tuple[str, str]]:
    timeout = aiohttp.ClientTimeout(total=TIMEOUT)
    # One session for all requests -- it keeps a pool of TCP connections open.
    async with aiohttp.ClientSession(timeout=timeout) as session:
        return await asyncio.gather(*(check_one(session, url) for url in urls))


def report(title: str, results: list[tuple[str, str]]) -> None:
    print(f"\n{title}")
    for url, status in results:
        print(f"  {status:>25}  {url}")


if __name__ == "__main__":
    report("SYNC", check_all_sync(SITES))
    report("ASYNC", asyncio.run(check_all_async(SITES)))
    print(
        "\nThe async version takes about as long as the *slowest single site*,\n"
        "the sync one takes the *sum of all of them*."
    )
