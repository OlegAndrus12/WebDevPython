"""Type aliases and NewType — naming types, and making them distinct.

PEP 484: "Type aliases are defined by simple variable assignments" —
https://peps.python.org/pep-0484/#type-aliases

Consequence: an alias is **not** a new type. `UserId = int` makes the checker
treat `UserId` and `int` as identical, everywhere. For a genuinely distinct
type, use `NewType` — the bug it prevents is the second half of this file.

Three still-valid syntax generations:

    Vector = list[float]                       # PEP 484 — plain assignment
    Vector: TypeAlias = list[float]            # PEP 613 (3.10+) — explicit
    type Vector = list[float]                  # PEP 695 (3.12+) — a statement

Domain: a payout ledger, where account id and order id are both ints —
swapping them moves money to the wrong place.

Run: python3 03_aliases.py
"""

from collections.abc import Sequence
from typing import NewType, TypeAlias

# ---------------------------------------------------------------------------
# 1. PEP 484 aliases — a plain assignment
# ---------------------------------------------------------------------------
# The right-hand side is evaluated — a real runtime object, not a comment.
# Aliases shorten and name: `dict[str, list[tuple[str, float]]]` is unreadable
# nested four deep, so give it one name instead of six repeats.
Money: TypeAlias = float
Currency: TypeAlias = str
Amount: TypeAlias = tuple[Money, Currency]
Ledger: TypeAlias = dict[str, list[Amount]]

# Aliasing a union pays off most: written once, changed once.
Payload: TypeAlias = str | bytes | Sequence[int]

# PEP 695 (3.12+): a real statement, lazily evaluated — no quotes, no
# `TypeAlias` import. Prefer this form in new code.
type PathLike = str | bytes

# Lazy evaluation makes *recursive* aliases painless — this is the canonical
# case, the type of anything `json.loads` returns. PEP 484/613 syntax evaluates
# immediately, so the self-reference needs a string:
# `Json: TypeAlias = "... | list[Json]"`. `from __future__ import annotations`
# doesn't help — an assignment isn't an annotation. File 11 proves both halves.
type Json = None | bool | int | float | str | list[Json] | dict[str, Json]
type Tree = dict[str, Tree | int]


# ---------------------------------------------------------------------------
# 2. An alias is transparent — that is the whole point, and the whole problem
# ---------------------------------------------------------------------------

AccountId: TypeAlias = int
OrderId: TypeAlias = int


def credit_alias(account: AccountId, order: OrderId, amount: Money) -> str:
    return f"credited {amount:.2f} to account {account} for order {order}"


# ---------------------------------------------------------------------------
# 3. NewType — a distinct type at zero runtime cost
# ---------------------------------------------------------------------------

# `NewType` returns a callable the checker treats as a subtype of int, but not
# vice versa. At runtime it's an identity function — `StrictAccountId(7) is 7`.
# No wrapper object, no attribute lookup, no cost.
StrictAccountId = NewType("StrictAccountId", int)
StrictOrderId = NewType("StrictOrderId", int)


def credit_strict(account: StrictAccountId, order: StrictOrderId, amount: Money) -> str:
    """Argument order can no longer be swapped silently.

    mypy on `credit_strict(order, account, ...)`:
        Argument 1 has incompatible type "StrictOrderId"; expected "StrictAccountId"

    A bare int is rejected too — construction is where validation belongs.
    """
    return f"credited {amount:.2f} to account {account} for order {order}"


def load_account_id(raw: str) -> StrictAccountId:
    """The single chokepoint where an untrusted int becomes a domain id."""
    value = int(raw)
    if value <= 0:
        raise ValueError(f"account id must be positive, got {value}")
    return StrictAccountId(value)


# Subtyping is one-directional: a StrictAccountId works anywhere an int does
# (arithmetic, dict keys, f-strings), but not the reverse — unlike a wrapper class.
def shard_for(account: StrictAccountId, shards: int = 4) -> int:
    return account % shards


# ---------------------------------------------------------------------------
# 4. Aliases carry generics too
# ---------------------------------------------------------------------------

# A generic alias leaves a parameter open; the caller fills it in.
type Page[T] = tuple[list[T], str | None]  # (items, next_cursor)


def first_page(rows: list[Amount]) -> Page[Amount]:
    return rows[:2], "cursor-2" if len(rows) > 2 else None


def walk(tree: Tree, depth: int = 0) -> list[str]:
    lines: list[str] = []
    for key, value in tree.items():
        if isinstance(value, dict):
            lines.append(f"{'  ' * depth}{key}/")
            lines.extend(walk(value, depth + 1))
        else:
            lines.append(f"{'  ' * depth}{key} = {value}")
    return lines


def main() -> None:
    ledger: Ledger = {
        "2026-08-01": [(120.50, "USD"), (18.00, "EUR")],
        "2026-08-02": [(9.99, "USD")],
    }

    print("1. Aliases are just names")
    print(f"   Amount at runtime: {Amount}")
    print(f"   Ledger at runtime: {Ledger}")
    print(f"   Payload at runtime: {Payload}")
    print(f"   Tree (PEP 695) is lazy: {Tree} -> {Tree.__value__}")

    print("\n2. The bug an alias cannot catch")
    account, order = 4001, 77
    print(f"   {credit_alias(account, order, 120.50)}")
    # Both parameters are `int` to the checker, so swapping them is silent:
    print(f"   {credit_alias(order, account, 120.50)}   <- wrong, and mypy is happy")

    print("\n3. The same bug with NewType")
    strict_account = load_account_id("4001")
    strict_order = StrictOrderId(77)
    print(f"   {credit_strict(strict_account, strict_order, 120.50)}")
    # mypy: Argument 1 has incompatible type "StrictOrderId"; expected "StrictAccountId"
    print("   swapped -> mypy: incompatible type (runtime would still 'work')")
    print(f"   identity at runtime: StrictAccountId(4001) == 4001 -> {StrictAccountId(4001) == 4001}")
    print(f"   still an int where an int is wanted: shard_for -> {shard_for(strict_account)}")

    print("\n4. Generic alias")
    items, cursor = first_page(ledger["2026-08-01"] + ledger["2026-08-02"])
    print(f"   items={items} cursor={cursor}")

    print("\n5. Recursive alias")
    config: Tree = {"api": {"port": 8000, "workers": 4}, "redis": {"db": 0}, "debug": 1}
    for line in walk(config):
        print(f"   {line}")


if __name__ == "__main__":
    main()
