"""
Written to be linted, not to be run.

Every function below trips at least one ruff rule from the six families this
project selects in pyproject.toml: E, F, I, UP, B, SIM. The folder is listed
in `extend-exclude`, so a normal `ruff check .` stays clean — point ruff at
this file explicitly:

    ruff check ruff_demo/messy.py
    ruff check --statistics ruff_demo/messy.py
    ruff check --diff ruff_demo/messy.py        # what --fix would change

Same shape as bandit_demo/insecure.py and mypy_demo/broken.py: wherever it is
useful, the broken version stands next to the fixed one, so you can see both
what is wrong and what it should look like.

Do not copy anything from the first half of each pair.
"""

# ---------------------------------------------------------------------------
# I — import order (isort), and F401 — unused imports
# ---------------------------------------------------------------------------
# Third-party before stdlib, local mixed in with both, and three of these are
# never used. `ruff check --fix` sorts and deletes all of it for you.
import requests
import os, sys
from typing import List, Dict, Optional
import json

import services


# ---------------------------------------------------------------------------
# F — pyflakes: things that are simply wrong
# ---------------------------------------------------------------------------
def describe(name):
    # F541: an f-string with nothing to interpolate. The `f` is left over from
    # an edit that removed the placeholder — the string now lies about itself.
    header = f"service report"

    # F841: assigned and never used. Usually the leftover of a refactor, but
    # sometimes it is the bug — you meant to return it.
    unused_total = len(name)

    return header + ": " + name


def describe_ok(name: str) -> str:
    return f"service report: {name}"


# ---------------------------------------------------------------------------
# E — pycodestyle: comparisons and statements
# ---------------------------------------------------------------------------
def check_flags(value, enabled):
    # E711 / E712: `is` compares identity, `==` compares value. For None and
    # for booleans there is exactly one object each, so `is` is both correct
    # and faster — and `== True` is noise around something already boolean.
    if value == None:
        return "missing"
    if enabled == True:
        return "on"
    return "off"


def check_flags_ok(value: str | None, enabled: bool) -> str:
    if value is None:
        return "missing"
    return "on" if enabled else "off"


# E731: a lambda bound to a name is a function definition with the debugging
# information thrown away — no name in the traceback, no docstring.
slugify = lambda text: text.lower().replace(" ", "-")


def slugify_ok(text: str) -> str:
    return text.lower().replace(" ", "-")


def read_config(path):
    # E722: a bare `except` also swallows KeyboardInterrupt and SystemExit,
    # so Ctrl-C stops working. Name the error you are actually handling.
    try:
        return json.loads(open(path).read())
    except:
        return {}


def read_config_ok(path: str) -> dict:
    try:
        with open(path) as handle:
            return json.loads(handle.read())
    except (OSError, json.JSONDecodeError):
        return {}


# ---------------------------------------------------------------------------
# UP — pyupgrade: syntax that has a newer form
# ---------------------------------------------------------------------------
# UP006 / UP035: since 3.9 the builtins are generic. typing.List and
# typing.Dict are deprecated aliases; Optional[str] is `str | None`.
def summarise(rows: List[Dict[str, str]], title: Optional[str]) -> str:
    # UP015: "r" is the default mode of open().
    with open("services.json", "r") as handle:
        handle.read()

    # UP032: str.format() where an f-string reads better.
    return "{}: {} rows".format(title or "report", len(rows))


def summarise_ok(rows: list[dict[str, str]], title: str | None) -> str:
    with open("services.json") as handle:
        handle.read()

    return f"{title or 'report'}: {len(rows)} rows"


class Board:
    def __init__(self, name):
        self.name = name


class NamedBoard(Board):
    def __init__(self, name):
        # UP008: Python 3 takes no arguments here.
        super(NamedBoard, self).__init__(name)


# ---------------------------------------------------------------------------
# B — flake8-bugbear: real bugs, not style
# ---------------------------------------------------------------------------
# B006: the default list is created ONCE, when the function is defined, and
# shared by every call that does not pass one. Append to it twice and the
# second caller sees the first caller's data. This is the classic Python bug
# and the single best reason to run bugbear.
def collect(url, seen=[]):
    seen.append(url)
    return seen


def collect_ok(url: str, seen: list[str] | None = None) -> list[str]:
    if seen is None:
        seen = []
    seen.append(url)
    return seen


def pair_up(names, urls):
    # B905: zip() silently stops at the shorter argument. If the two lists are
    # supposed to be the same length, `strict=True` turns a silent truncation
    # into a ValueError.
    return [f"{n} -> {u}" for n, u in zip(names, urls)]


def pair_up_ok(names: list[str], urls: list[str]) -> list[str]:
    return [f"{n} -> {u}" for n, u in zip(names, urls, strict=True)]


def fetch(url):
    try:
        return requests.get(url, timeout=5).text
    except requests.RequestException:
        # B904: raising inside `except` without `from` hides the original
        # traceback — you lose the line that actually failed.
        raise RuntimeError("request failed")


def fetch_ok(url: str) -> str:
    try:
        return requests.get(url, timeout=5).text
    except requests.RequestException as error:
        raise RuntimeError("request failed") from error


def count_rows(rows):
    total = 0
    # B007: the loop variable is never used — say so by naming it `_`.
    for row in rows:
        total += 1
    return total


# ---------------------------------------------------------------------------
# SIM — flake8-simplify: correct, but longer than it needs to be
# ---------------------------------------------------------------------------
def status_label(code):
    # SIM108: a four-line if/else that assigns the same name in both branches.
    if code == 200:
        label = "up"
    else:
        label = "down"
    return label


def status_label_ok(code: int) -> str:
    return "up" if code == 200 else "down"


def is_healthy(code):
    # SIM103: the condition is already the boolean you are returning.
    if 200 <= code < 400:
        return True
    else:
        return False


def is_healthy_ok(code: int) -> bool:
    return 200 <= code < 400


def has_https(urls):
    # SIM110: a for-loop that is exactly `any()`. The rewrite also short-
    # circuits the same way, so nothing is lost.
    for url in urls:
        if url.startswith("https://"):
            return True
    return False


def has_https_ok(urls: list[str]) -> bool:
    return any(url.startswith("https://") for url in urls)


def known(name, table):
    # SIM118: iterating a dict already iterates its keys; .keys() builds a
    # view object for nothing.
    return name in table.keys()


def known_ok(name: str, table: dict[str, str]) -> bool:
    return name in table


def load_names(path):
    # SIM115: the handle is never closed. CPython usually collects it soon
    # enough to hide the problem, which is exactly what makes it dangerous.
    handle = open(path)
    return list(json.loads(handle.read()))


def load_names_ok(path: str) -> list[str]:
    with open(path) as handle:
        return list(json.loads(handle.read()))


# `services` is imported at the top and used only here, so the import itself
# is legitimate — it is `os`, `sys` and `requests`… well, requests is used by
# fetch(). Check which ones ruff actually flags; guessing is how you learn to
# read the report instead of trusting it.
def all_names():
    return list(services.load())
