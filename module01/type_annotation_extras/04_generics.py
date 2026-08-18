"""Callables, TypeVars and generics — types with a parameter.

A generic is a type with a hole in it: `list` isn't a type until `list[str]`.
Same for your code — input/output types stay linked, so `first(list[Hit])`
returns `Hit`, not `Any`.

Both syntaxes appear below:

    def first[T](items: Sequence[T]) -> T          # PEP 695 (3.12+)
    T = TypeVar("T"); def first(...) -> T          # PEP 484 (still everywhere)

Domain: a repository, plus a retry decorator.

Run: python3 04_generics.py
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Concatenate, Protocol, Self

# ---------------------------------------------------------------------------
# Callable — a function as a value
# ---------------------------------------------------------------------------

# `Callable[[int, str], bool]`: two positional params, returns bool.
# `Callable[..., bool]`: any signature, returns bool — escape hatch.
Validator = Callable[[str], bool]
KeyFn = Callable[[str], str]


def apply_all(value: str, validators: Iterable[Validator]) -> bool:
    """`Callable` can't express named/optional params, defaults, or `*args` — use
    a callback `Protocol` (`Formatter`, file 05).
    """
    return all(check(value) for check in validators)


class Formatter(Protocol):
    """A callback protocol: named params let callers pass `width` by keyword —
    which `Callable[[str, int], str]` forbids.
    """

    def __call__(self, text: str, /, *, width: int = 40) -> str: ...


def pad(text: str, /, *, width: int = 40) -> str:
    return text.ljust(width, ".")


def render(rows: Iterable[str], fmt: Formatter) -> list[str]:
    return [fmt(row, width=24) for row in rows]


# ---------------------------------------------------------------------------
# Type variables
# ---------------------------------------------------------------------------


def first[T](items: Sequence[T], default: T | None = None) -> T | None:
    """One `T` in two places means "same type in both"; otherwise it's `Any`
    and downstream attribute access is unchecked.
    """
    return items[0] if items else default


def dedupe[T: (str, int)](items: Iterable[T]) -> list[T]:
    """A *constrained* TypeVar: T must be `str` or `int` exactly — no widening,
    so `list[float]` errors.
    """
    seen: set[T] = set()
    out: list[T] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


class Entity(Protocol):
    # A read-only property, not `id: int` (needs a *settable* attribute,
    # which frozen dataclasses lack). See `Check`, file 05.
    @property
    def id(self) -> int: ...


def index_by_id[E: Entity](rows: Iterable[E]) -> dict[int, E]:
    """*Bound* (`E: Entity`) accepts any subtype, so `.id` works; *constrained*
    (`E: (A, B)`) accepts only those listed.
    """
    return {row.id: row for row in rows}


# ---------------------------------------------------------------------------
# Generic classes
# ---------------------------------------------------------------------------


from typing import Generic, TypeVar

T = TypeVar("T")

class Box(Generic[T]):
    def __init__(self, item: T) -> None:
        self.item = item

    def get(self) -> T:
        return self.item

    def set(self, item: T) -> None:
        self.item = item

b: Box[int] = Box(5)
b.get()          # inferred as int
b.set("oops")    # type error — expected int

c = Box("hello")  # Box[str] inferred automatically, no annotation needed


##

class Box[T]:
    def __init__(self, item: T) -> None:
        self.item = item

    def get(self) -> T:
        return self.item

##

#Multiple type parameters
class Pair[K, V]:
    def __init__(self, key: K, value: V) -> None:
        self.key = key
        self.value = value

p = Pair("age", 30)   # Pair[str, int]

class Box[T]:
    def __init__(self, item: T) -> None:
        self.item = item
    def get(self) -> T:
        return self.item

class LoggingBox[T](Box[T]):
    def get(self) -> T:
        print("getting item")
        return super().get()

lb = LoggingBox(5)     # T = int → LoggingBox[int]
lb.get()                 # returns int, logs first

##

class IntBox(Box[int]):     # fixes T = int permanently
    pass

ib = IntBox(5)      # fine
ib2 = IntBox("x")   # type error — IntBox is fixed to int; no [T] to parameterize

class Repository[E: Entity]:
    def add(self, entity: E) -> None: ...
    def get(self, id: int) -> E | None: ...

class UserRepo(Repository[User]): ...   # fine, User is an Entity
class BadRepo(Repository[str]): ...     # type error, str is not an Entity



@dataclass(slots=True)
class Repository[E: Entity]:
    """`Repository[Owner]` and `Repository[Cat]` are different types — the
    parameter, declared once, is seen by every method automatically.
    """

    _rows: dict[int, E] = field(default_factory=dict)

    def add(self, row: E) -> Self:
        """`Self` (PEP 673): the *subclass* type, not this one — returning
        `Repository[E]` would break chaining on subclasses. `Self` tracks
        inheritance correctly.
        """
        self._rows[row.id] = row
        return self

    def get(self, row_id: int) -> E | None:
        return self._rows.get(row_id)

    def all(self) -> list[E]:
        return list(self._rows.values())


class AuditedRepository[E: Entity](Repository[E]):
    def add(self, row: E) -> Self:
        print(f"   audit: stored id={row.id}")
        return super().add(row)


@dataclass(frozen=True, slots=True)
class Owner:
    id: int
    email: str


@dataclass(frozen=True, slots=True)
class Cat:
    id: int
    name: str
    owner_id: int








# ---------------------------------------------------------------------------
# ParamSpec — decorators that keep the signature
# ---------------------------------------------------------------------------


def retry[**P, R](attempts: int = 3) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """`**P` captures the parameter list, `R` the return type — without it,
    decorators default to `Callable[..., Any]`, silently erasing every
    wrapped function's types.
    """

    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            last: Exception | None = None
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except ConnectionError as exc:
                    last = exc
                    print(f"   attempt {attempt} failed: {exc}")
            raise RuntimeError(f"{fn.__name__} failed after {attempts} attempts") from last

        return wrapper

    return decorate


def with_repo[E: Entity, **P, R](
    fn: Callable[Concatenate[Repository[E], P], R],
) -> Callable[Concatenate[Repository[E], P], R]:
    """`Concatenate` types a leading argument plus "whatever else the callee
    takes" — something `Callable[P, R]` alone can't express.
    """

    # `/` after `repo`: `Concatenate`'s prefix is positional — a named param
    # won't match. mypy flags it immediately.
    def wrapper(repo: Repository[E], /, *args: P.args, **kwargs: P.kwargs) -> R:
        print(f"   with_repo: {len(repo.all())} rows in scope")
        return fn(repo, *args, **kwargs)

    # `functools.update_wrapper`, not `@functools.wraps`: typeshed's decorator
    # return type won't unify with `Concatenate`. Same effect, no cast.
    functools.update_wrapper(wrapper, fn)
    return wrapper


_flaky_calls = 0


@retry(attempts=3)
def fetch_owner(owner_id: int, *, verbose: bool = False) -> Owner:
    """Fully typed despite the decorator: `fetch_owner("x")` is an error."""
    global _flaky_calls
    _flaky_calls += 1
    if _flaky_calls < 3:
        raise ConnectionError("upstream reset")
    if verbose:
        print("   fetched")
    return Owner(id=owner_id, email=f"owner{owner_id}@example.com")


@with_repo
def cats_of(repo: Repository[Cat], owner_id: int) -> list[Cat]:
    return [cat for cat in repo.all() if cat.owner_id == owner_id]


def main() -> None:
    print("1. Callable and callback Protocol")
    print(f"   apply_all: {apply_all('ok', [str.isascii, lambda s: len(s) > 1])}")
    for line in render(["timeout", "connection reset"], pad):
        print(f"   {line}")

    print("\n2. TypeVars keep the element type")
    owners = [Owner(1, "a@example.com"), Owner(2, "b@example.com")]
    head = first(owners)
    # `head`: `Owner | None` — mypy wants the None check before `.email`.
    print(f"   first(owners).email -> {head.email if head else '-'}")
    # One signature can't say "`None` only without a default"; `@overload`
    # (file 06) is how you encode that.
    fallback = first([], default=Owner(0, "none@example.com"))
    print(f"   first([], default=...) -> {fallback.email if fallback else '-'}")
    print(f"   dedupe: {dedupe(['a', 'b', 'a', 'c'])} / {dedupe([3, 1, 3])}")

    print("\n3. Generic class")
    cats: Repository[Cat] = Repository()
    cats.add(Cat(10, "Murka", owner_id=1)).add(Cat(11, "Barsik", owner_id=1))
    cats.add(Cat(12, "Rex", owner_id=2))
    print(f"   ids: {sorted(index_by_id(cats.all()))}")
    got = cats.get(10)
    print(f"   get(10).name -> {got.name if got else '-'}")

    print("\n4. Self survives inheritance")
    audited: AuditedRepository[Owner] = AuditedRepository()
    audited.add(owners[0]).add(owners[1])  # chaining stays typed as AuditedRepository
    print(f"   audited holds {len(audited.all())} owners")

    print("\n5. ParamSpec")
    owner = fetch_owner(4001, verbose=True)
    print(f"   {owner}")
    print(f"   cats_of: {[c.name for c in cats_of(cats, 1)]}")


if __name__ == "__main__":
    main()
