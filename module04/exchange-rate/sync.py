"""6. HTTP-запити до реального API (курс НБУ) — синхронна версія.

Real-life task: build a chart of the USD exchange rate for the last N days. The
National Bank of Ukraine API answers one date per request, so N days = N requests.
No API key, no registration.

    https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=USD&date=20260819&json

This is the baseline: one session, N requests, each one waiting for the previous
to come back. Compare with async_ex.py in the same folder.

    uv run sync.py
"""
from datetime import date, timedelta
from pathlib import Path
from time import perf_counter

import requests

from chart import save_chart

API = "https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange"
CURRENCY = "USD"
DAYS = 30

BASE_DIR = Path(__file__).parent
CHART_FILE = BASE_DIR / f"{CURRENCY.lower()}_uah_sync.png"

dates = [date.today() - timedelta(days=offset) for offset in range(DAYS)]


def params_for(day: date) -> dict:
    return {"valcode": CURRENCY, "date": day.strftime("%Y%m%d"), "json": ""}


def rates_sync() -> dict[str, float]:
    """One request at a time, reusing a single connection."""
    rates = {}
    with requests.Session() as session:
        for day in dates:
            try:
                response = session.get(API, params=params_for(day), timeout=10)
                response.raise_for_status()
                payload = response.json()
            except (requests.RequestException, ValueError) as err:
                # One bad day must not lose the other 29.
                print(f"   {day}: {type(err).__name__}")
                continue
            # Some dates (future dates, some holidays) come back as an empty list.
            if payload:
                rates[str(day)] = payload[0]["rate"]
    return rates


if __name__ == "__main__":
    start = perf_counter()
    rates = rates_sync()
    print(f"sync:  {DAYS} requests one by one -> {len(rates)} trading days "
          f"in {perf_counter() - start:.2f}s")
    save_chart(rates, CHART_FILE, f"{CURRENCY}/UAH, курс НБУ")
