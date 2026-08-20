"""Shared helpers for the asyncio examples.

Every example in this folder is a standalone script, run from *this* directory:

    poetry run python 05_gather.py

Because the script's own directory is on ``sys.path``, a flat ``from libs import ...``
is all that is needed.
"""
import asyncio
import time
from functools import wraps


def async_timed(label: str | None = None):
    """Print how long a coroutine function took.
    """

    def wrapper(func):
        @wraps(func)
        async def wrapped(*args, **kwargs):
            name = label or func.__name__
            print(f"-> {name} started")
            start = time.perf_counter()
            try:
                return await func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                print(f"<- {name} finished in {elapsed:.2f}s")

        return wrapped

    return wrapper


def timed(label: str | None = None):
    """Same thing for ordinary (blocking) functions, so the two can be compared."""

    def wrapper(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            name = label or func.__name__
            print(f"-> {name} started")
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                print(f"<- {name} finished in {elapsed:.2f}s")

        return wrapped

    return wrapper
