"""6. HTTP-запити до реального API (курс НБУ) — асинхронна версія.

Same job as sync.py -- N days of the USD rate, one request per day -- but the
requests overlap. This is where async genuinely pays: each request spends its time
waiting on the network, and waiting is what an event loop overlaps for free.

What this shows beyond "it is faster":
  * one ClientSession for the whole batch (connection reuse);
  * a total timeout on the session, so a hanging server cannot stall the job;
  * a Semaphore, because hammering a public API with 30 parallel requests is rude;
  * per-request error handling, so one bad day does not lose the other 29.

    uv run async_ex.py
"""
import asyncio
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter

import aiohttp

from chart import save_chart

API = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange"
CURRENCY = "USD"
DAYS = 30
MAX_CONCURRENT = 8

BASE_DIR = Path(__file__).parent
CHART_FILE = BASE_DIR / f"{CURRENCY.lower()}_uah_async.png"

dates = [date.today() - timedelta(days=offset) for offset in range(DAYS)]


def params_for(day: date) -> dict:
    return {"valcode": CURRENCY, "date": day.strftime("%Y%m%d"), "json": ""}


async def rate_for(
    session: aiohttp.ClientSession, semaphore: asyncio.Semaphore, day: date
) -> tuple[str, float | None]:
    async with semaphore:
        try:
            async with session.get(API, params=params_for(day)) as response:
                response.raise_for_status()
                # The NBU serves JSON with a text/plain content type, hence the flag.
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            print(f"   {day}: {type(err).__name__}")
            return str(day), None

    # Some dates (future dates, some holidays) come back as an empty list.
    return str(day), payload[0]["rate"] if payload else None


async def rates_async() -> dict[str, float]:
    """All N requests in flight at once, capped at MAX_CONCURRENT."""
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    timeout = aiohttp.ClientTimeout(total=30, connect=5)
    headers = {"User-Agent": "goit-async-lecture/1.0"}

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        pairs = await asyncio.gather(*(rate_for(session, semaphore, day) for day in dates))

    return {day: rate for day, rate in pairs if rate is not None}


if __name__ == "__main__":
    start = perf_counter()
    rates = asyncio.run(rates_async())
    print(f"async: {DAYS} requests, {MAX_CONCURRENT} at a time -> {len(rates)} trading days "
          f"in {perf_counter() - start:.2f}s")
    save_chart(rates, CHART_FILE, f"{CURRENCY}/UAH, курс НБУ")
