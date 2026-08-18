"""Check a URL, report what happened.

Each item is a plain dict with a fixed set of keys:

    name        the label shown on the board
    url         what was requested
    status      HTTP status code, or None if the request never completed
    latency_ms  round trip in whole milliseconds, or None on failure
    error       exception class name, or None on success
    ok          True when a response came back under 400
"""

from __future__ import annotations

import time

import requests


def check(name: str, url: str, timeout: float = 5.0) -> dict:
    started = time.perf_counter()
    try:
        response = requests.get(url, timeout=timeout)
    except requests.RequestException as err:
        return {
            "name": name,
            "url": url,
            "status": None,
            "latency_ms": None,
            "error": type(err).__name__,
            "ok": False,
        }

    return {
        "name": name,
        "url": url,
        "status": response.status_code,
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "error": None,
        "ok": response.status_code < 400,
    }


def check_all(services: dict[str, str], timeout: float = 5.0) -> list[dict]:
    return [check(name, url, timeout) for name, url in services.items()]
