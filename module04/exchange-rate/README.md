# exchange-rate — 30 requests to a real API

Section 6 of [../AGENDA.md](../AGENDA.md), and the example where async genuinely pays. The National
Bank of Ukraine publishes one exchange rate per date, one date per request — so a 30-day chart is 30
HTTP requests, each spending almost all of its time waiting on the network. Waiting is exactly what
an event loop overlaps for free.

No API key, no registration:

```
https://bank.gov.ua/NBUStatService/v1/statdirectory/exchange?valcode=USD&date=20260819&json
```

| File | Stack | Writes |
| --- | --- | --- |
| [`sync.py`](sync.py) | `requests.Session` | `usd_uah_sync.png` |
| [`async_ex.py`](async_ex.py) | `aiohttp.ClientSession` | `usd_uah_async.png` |
| [`chart.py`](chart.py) | `matplotlib` | shared by both |

`chart.py` is imported by both, so the two scripts differ **only** in how they make the requests —
same data, same chart, same PNG shape.

## Run it

```bash
cd module04/exchange-rate
uv run sync.py
uv run async_ex.py
```

Both print one line and save a PNG:

```
sync:  30 requests one by one -> N trading days in X.XXs
   chart saved to usd_uah_sync.png
async: 30 requests, 8 at a time -> N trading days in Y.YYs
   chart saved to usd_uah_async.png
```

Both timings depend entirely on your link to `bank.gov.ua`, so run them yourself; the *ratio* is the
point, and it should be somewhere near `MAX_CONCURRENT`. Fewer than 30 trading days is normal —
weekends and holidays come back as an empty list, and both scripts skip them.

> Needs `requests` and `aiohttp`, which are missing from [`../pyproject.toml`](../pyproject.toml):
> `uv add aiohttp requests`. See [../README.md](../README.md#prerequisites).

## What the async version does beyond "await it"

Speed is the easy part. These four lines are the ones worth copying into real code:

```python
semaphore = asyncio.Semaphore(MAX_CONCURRENT)          # 8, not 30
timeout = aiohttp.ClientTimeout(total=30, connect=5)
headers = {"User-Agent": "goit-async-lecture/1.0"}
async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
```

- **One `ClientSession` for the whole batch.** It owns a connection pool; a session per request
  throws away every TCP handshake and TLS negotiation. This is the single most common aiohttp
  mistake.
- **A `Semaphore`.** Firing 30 parallel requests at somebody's free public API is rude, and it is
  also how you get rate-limited or blocked. `MAX_CONCURRENT = 8` keeps eight in flight and queues the
  rest — one line, and the code still reads top to bottom.
- **A total timeout.** Without it, one hanging server stalls the whole `gather` forever. `total=30`
  bounds the request end to end; `connect=5` bounds just the handshake.
- **Per-request error handling.** `rate_for` catches `aiohttp.ClientError` and
  `asyncio.TimeoutError`, prints the day, and returns `None`. One bad day must not lose the other 29
  — which is the same lesson as `return_exceptions=True` in
  [`../03_gather_with_exeption.py`](../03_gather_with_exeption.py), solved one level lower down.

## Two API quirks the code works around

```python
payload = await response.json(content_type=None)
```

The NBU serves JSON with a `text/plain` content type. aiohttp is strict by default and raises
`ContentTypeError`; `content_type=None` tells it to parse anyway. `requests` never checks, which is
why `sync.py` needs no equivalent.

```python
return str(day), payload[0]["rate"] if payload else None
```

Weekends, holidays and future dates return `[]`, not a 404. An empty list is a valid answer meaning
"no trading happened" — indexing it blindly is a `IndexError` waiting for the next Sunday.

## The chart

`chart.py` sets `matplotlib.use("Agg")` **before** importing `pyplot`: render to a file, no GUI, no
window server needed — the right choice in a script or a container, and the reason for the two
`# noqa: E402` comments (imports after code, deliberately).

`mdates.DateFormatter("%d.%m")` is there because the default axis labels on 22 dates overlap into an
unreadable smear. `plt.close(fig)` releases the figure; leaving figures open in a loop is how a
long-running process leaks memory through matplotlib.

## Changing the experiment

| Constant | In | Try |
| --- | --- | --- |
| `CURRENCY` | both | `"EUR"`, `"PLN"`, `"GBP"` |
| `DAYS` | both | `90` — the sync version gets painful, the async one barely moves |
| `MAX_CONCURRENT` | `async_ex.py` | `1` (should match `sync.py`), `30` (all at once) |

Setting `MAX_CONCURRENT = 1` is the honest control experiment: it turns the async version back into
the sync one and confirms the speed-up came from concurrency, not from aiohttp being a faster
library.
