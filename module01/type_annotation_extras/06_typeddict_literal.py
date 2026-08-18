"""TypedDict, Literal, overload, Annotated — describing data, not just shapes.

These four handle a `dict` fresh off the wire — where ordinary hints fail:
`dict[str, Any]` says nothing, and `dict[str, str | int | None]` forces
narrowing at every access. A `TypedDict` names each key instead.

Caveat: **none of this validates anything.** A `TypedDict` is a plain `dict`
at runtime — a malformed payload passes straight through. Validation is
pydantic's job — see `../../pydantic_ex/`.

Domain: incoming payment-provider webhooks.

Run: python3 06_typeddict_literal.py
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import (
    Annotated,
    Any,
    Literal,
    NotRequired,
    TypedDict,
    cast,
    get_type_hints,
    overload,
)


# ---------------------------------------------------------------------------
# 2. Literal — a type made of values
# ---------------------------------------------------------------------------

Mode = Literal["live", "test"]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE"]


def endpoint(mode: Mode, method: HttpMethod = "GET") -> str:
    """`endpoint("prod")` fails at check time — mypy lists the valid options.

    Literal suits a fixed set of *wire* values you don't control. For values
    you define, `Enum` is usually better: it gets a name, methods, `auto()`.
    `StrEnum` (3.11+) is both — a real enum that *is* a `str`, so it
    serialises and concatenates with no `.value`. Wrinkle: under
    `strict_equality`, mypy rejects `Provider.STRIPE == "stripe"` as
    non-overlapping — convert with `Provider(raw)` at the boundary instead of
    comparing members to raw strings.
    """
    host = "api.example.com" if mode == "live" else "api.sandbox.example.com"
    return f"{method} https://{host}/v1/charges"


class Provider(StrEnum):
    STRIPE = "stripe"
    PADDLE = "paddle"

    @property
    def webhook_path(self) -> str:
        return f"/webhooks/{self.value}"


# ---------------------------------------------------------------------------
# 3. overload — one implementation, several honest signatures
# ---------------------------------------------------------------------------


@overload
def get_setting(key: str) -> str | None: ...
@overload
def get_setting(key: str, default: str) -> str: ...


def get_setting(key: str, default: str | None = None) -> str | None:
    """The return type depends on the *arguments* — one signature can't say so.

    Without overloads, the return is always `str | None`, forcing a None-check
    even when a default was passed. The `...` stubs are checker-only; the real
    body runs, and mypy verifies it's compatible with every overload.
    """
    settings = {"currency": "usd", "mode": "test"}
    value = settings.get(key)
    return default if value is None else value
