"""A hint that type-checks is not a guarantee the program is correct — that's
this file's whole subject.

Ten traps, each a signature the checker accepts and the runtime still gets
wrong: a validated-looking parameter that isn't, `Optional` mistaken for an
optional argument, a mutable default shared across calls, `Any` spreading
unchecked, `list`'s invariance, a decorator that erases the signature beneath
it, a class confused with an instance of it, a blanket `# type: ignore`, a
`cast` that lies, and a generator consumed exactly once.

Run: python3 08_pitfalls.py
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, cast

# ---------------------------------------------------------------------------
# 1. A hint is not a check
# ---------------------------------------------------------------------------


def apply_discount(total: float, percent: int) -> float:
    """`percent="10"` type-checks nowhere and crashes here.

    At a trust boundary — HTTP body, env var, CSV, queue — hints are
    documentation, not validation. Inside your own code they're proof; at the
    edge, a wish.
    """
    return total * (1 - percent / 100)


# ---------------------------------------------------------------------------
# 2. `Optional` is not an optional argument
# ---------------------------------------------------------------------------


def notify(user: str, channel: str | None) -> str:
    """`channel` is *required* and may be None — two independent things:

        channel: str | None            required, nullable
        channel: str = "email"         optional, never None
        channel: str | None = None     optional, nullable

    Implicit-Optional (`def f(x: str = None)`) is now an error by default
    (`--no-implicit-optional`, mypy 0.990+).
    """
    return f"{user} via {channel or 'email'}"


# ---------------------------------------------------------------------------
# 3. The mutable default, now visible in the hint
# ---------------------------------------------------------------------------


def add_tag_broken(tag: str, tags: list[str] = []) -> list[str]:  # noqa: B006
    """One list, created once at *definition* time, shared by every call.

    The hint is correct, the code isn't — a checker won't catch this, but
    ruff's B006 will.
    """
    tags.append(tag)
    return tags


def add_tag(tag: str, tags: list[str] | None = None) -> list[str]:
    return [*(tags or []), tag]


@dataclass(slots=True)
class Basket:
    """Same trap in a dataclass — `field` is the fix.

    `items: list[str] = []` raises ValueError at import: the friendliest
    possible outcome.
    """

    items: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 4. `Any` is contagious
# ---------------------------------------------------------------------------


def load_config_any(raw: str) -> Any:
    """Everything downstream of `Any` is silently unchecked.

    `config["timeuot"]`, `config.timeout`, `config + 1` — all fine to mypy.
    `--disallow-any-explicit`/`--warn-return-any` flag this; `dict[str, object]`
    or a `TypedDict` is the real fix.
    """
    return {"timeout": 5} if raw else {}


def load_config(raw: str) -> dict[str, object]:
    return {"timeout": 5} if raw else {}


# ---------------------------------------------------------------------------
# 5. list is invariant (the one from file 02, restated as a rule)
# ---------------------------------------------------------------------------


def total_ints(values: Sequence[int]) -> int:
    """Prefer `Sequence`/`Iterable`/`Mapping` over `list`/`dict` for parameters.

    `Sequence[int]` accepts `list[int]`, `tuple[int, ...]`, `range`; `list[int]`
    accepts only `list[int]` — not even `list[bool]`, a subtype.
    """
    return sum(values)


# ---------------------------------------------------------------------------
# 6. A decorator without ParamSpec erases the signature
# ---------------------------------------------------------------------------


def timed_bad(fn: Callable[..., Any]) -> Callable[..., Any]:
    """After this decorator, `charge("abc", "def", nope=1)` type-checks.

    One `Callable[..., Any]` disables checking for every decorated function —
    see `retry` in file 04 for the `[**P, R]` fix.
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    return wrapper


def timed[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return fn(*args, **kwargs)

    return wrapper


@timed_bad
def charge_bad(amount_cents: int, currency: str) -> str:
    return f"{amount_cents / 100:.2f} {currency}"


@timed
def charge(amount_cents: int, currency: str) -> str:
    return f"{amount_cents / 100:.2f} {currency}"


# ---------------------------------------------------------------------------
# 7. The class object vs an instance of it
# ---------------------------------------------------------------------------


class Handler:
    def handle(self) -> str:
        return type(self).__name__


def build(handler_cls: type[Handler]) -> Handler:
    """`type[Handler]` is the class; `Handler` is an instance.

    A class registry is `dict[str, type[Handler]]`; mixing these up produces
    "Handler is not callable" or "cannot access .handle on type".
    """
    return handler_cls()


# ---------------------------------------------------------------------------
# 8. `# type: ignore` without a code is a blanket
# ---------------------------------------------------------------------------


def parse_port(raw: str) -> int:
    """`# type: ignore[arg-type]` silences one error; bare `# type: ignore`
    silences every error on that line, including ones added later.

    Always write the code — `--strict` + `warn_unused_ignores = true` then
    flags an ignore once it's unnecessary, usually after a library ships stubs.
    """
    return int(raw)


# ---------------------------------------------------------------------------
# 9. `cast` is a promise, not a conversion
# ---------------------------------------------------------------------------


def lie() -> int:
    """`cast` emits no code — this returns a `str` from an `int` function.

    Every `cast` is where the checker's guarantee stops; use it at boundaries,
    right after the runtime check that makes it true.
    """
    value: object = "not a number"
    return cast(int, value)


# ---------------------------------------------------------------------------
# 10. Hints do not survive into `Iterable` consumption for free
# ---------------------------------------------------------------------------


def sum_all(rows: Iterable[Iterable[int]]) -> int:
    """A generator is consumed once — the type says nothing about that.

    `Iterable` promises "I will loop", not that the caller can loop twice. If
    the body iterates more than once, ask for `Sequence`, or materialise with
    `list(rows)` and say so.
    """
    return sum(sum(row) for row in rows)


def main() -> None:
    print("1. A hint is not a check")
    try:
        apply_discount(100.0, cast(int, "10"))
    except TypeError as exc:
        print(f"   TypeError: {exc}")

    print("\n2. Optional vs default")
    print(f"   {notify('ada', None)}")

    print("\n3. Mutable default")
    print(f"   add_tag_broken: {add_tag_broken('eu')} then {add_tag_broken('billing')}")
    print(f"   add_tag:        {add_tag('eu')} then {add_tag('billing')}")
    print(f"   Basket():       {Basket().items} and {Basket().items} are distinct lists")

    print("\n4. Any is contagious")
    loose = load_config_any("x")
    print("   loose['timeuot'] type-checks; at runtime: ", end="")
    try:
        print(loose["timeuot"])
    except KeyError as exc:
        print(f"KeyError {exc}")
    tight = load_config("x")
    print(f"   dict[str, object] forces a check first: {tight.get('timeout')}")

    print("\n5. Invariance")
    print(f"   total_ints(range(4)) = {total_ints(range(4))}")
    print(f"   total_ints((1, 2))   = {total_ints((1, 2))}")

    print("\n6. Decorators")
    print(f"   charge(2900, 'usd')     = {charge(2900, 'usd')}")
    # mypy: Argument 2 has incompatible type "int"; expected "str"  <- only for `charge`
    print(f"   charge_bad(2900, 'usd') = {charge_bad(2900, 'usd')}  (unchecked signature)")

    print("\n7. Class vs instance")
    print(f"   build(Handler).handle() = {build(Handler).handle()}")

    print("\n8/9. ignore and cast")
    print(f"   parse_port('8000') = {parse_port('8000')}")
    print(f"   lie() returned a {type(lie()).__name__} from an `-> int` function")

    print("\n10. Iterables are consumed")
    rows = (row for row in ([1, 2], [3]))
    print(f"   first pass:  {sum_all(rows)}")
    print(f"   second pass: {sum_all(rows)}  <- the generator is exhausted")


if __name__ == "__main__":
    main()
