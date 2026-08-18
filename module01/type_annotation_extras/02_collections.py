"""Collections — concrete builtins vs abstract roles, and why the choice matters.

Two rules matter most:

  1. **Accept the widest type you use, return the narrowest you have.**
     A function that only iterates should ask for `Iterable`, not `list`.
  2. **`list` is invariant, `Sequence` is covariant.** `list[Timeout]` is
     *not* acceptable where `list[Check]` is expected, however obviously
     related the types look. `Sequence[Check]` accepts it — the most
     common "but that's clearly fine" error beginners hit.

Domain: aggregating nginx access-log lines.

Run: python3 02_collections.py
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Mapping, MutableMapping, Sequence
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Parameterised builtins (PEP 585, 3.9+ — no typing.List needed)
# ---------------------------------------------------------------------------

RAW_LOG = """\
10.0.0.4 GET /api/v1/cats 200 0.031
10.0.0.9 GET /api/v1/cats 200 0.048
10.0.0.4 POST /api/v1/cats 201 0.194
10.0.0.7 GET /health 200 0.002
10.0.0.9 GET /api/v1/owners 500 1.412
10.0.0.4 GET /api/v1/owners 500 1.288
"""


@dataclass(frozen=True, slots=True)
class Hit:
    ip: str
    method: str
    path: str
    status: int
    seconds: float


def parse(text: str) -> list[Hit]:
    """`list[Hit]` — homogeneous, variable-length.

    Concrete `list` is right here: the caller owns the object and may sort
    or append. `Sequence[Hit]` would promise no mutation — a different,
    often better, contract.
    """
    hits: list[Hit] = []
    for line in text.splitlines():
        ip, method, path, status, seconds = line.split()
        hits.append(Hit(ip, method, path, int(status), float(seconds)))
    return hits


def status_counts(hits: Iterable[Hit]) -> dict[int, int]:
    """`Iterable` in, `dict` out.

    The body only loops, so it shouldn't demand a `list` — a generator,
    a `set`, `dict.values()`, or a file object all satisfy `Iterable`.
    """
    counter: Counter[int] = Counter(hit.status for hit in hits)
    return dict(counter)


def slowest(hits: Sequence[Hit]) -> Hit:
    """`Sequence` needs `len()` and `[i]`, but never mutates.

    A generator wouldn't satisfy this — the signature states the
    requirement instead of hiding it behind `list`.
    """
    return max(hits, key=lambda hit: hit.seconds)


def by_path(hits: Iterable[Hit]) -> dict[str, list[Hit]]:
    """Nested parameterisation. `dict[str, list[Hit]]` reads outside-in."""
    grouped: dict[str, list[Hit]] = {}
    for hit in hits:
        grouped.setdefault(hit.path, []).append(hit)
    return grouped


# ---------------------------------------------------------------------------
# Tuples are two different types wearing one name
# ---------------------------------------------------------------------------


def endpoint_key(hit: Hit) -> tuple[str, str]:
    """Fixed length, position-dependent types: exactly 2 items, both `str`."""
    return hit.method, hit.path


def all_latencies(hits: Iterable[Hit]) -> tuple[float, ...]:
    """Variadic: any number of items, all `float`; `...` is literal syntax.

    `tuple[float]` means a 1-tuple — a mistake that often survives review.
    """
    return tuple(hit.seconds for hit in hits)


# ---------------------------------------------------------------------------
# Mapping vs MutableMapping — read-only by signature
# ---------------------------------------------------------------------------


def render_summary(counts: Mapping[int, int]) -> str:
    """`Mapping` promises the function won't write.

    `counts[500] = 0` here is a type error, so callers can pass a shared
    dict without auditing this code.
    """
    return ", ".join(f"{status}:{n}" for status, n in sorted(counts.items()))


def merge_into(target: MutableMapping[int, int], extra: Mapping[int, int]) -> None:
    """Asymmetric on purpose: one side is written, the other only read."""
    for status, n in extra.items():
        target[status] = target.get(status, 0) + n


# ---------------------------------------------------------------------------
# Iterator vs Iterable — a generator's return type
# ---------------------------------------------------------------------------


def errors(hits: Iterable[Hit]) -> Iterator[Hit]:
    """A generator function's return type is usually `Iterator`, not `Generator`.

    Use `Iterator[Hit]` whenever the caller only iterates; reach for
    `Generator[Y, S, R]` only if `.send()` or a return value matters. The
    annotation describes what the *call* produces, not the `yield`.
    """
    for hit in hits:
        if hit.status >= 500:
            yield hit


# ---------------------------------------------------------------------------
# Invariance, the error everyone hits
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SlowHit(Hit):
    threshold: float = 1.0


def count_hits(hits: list[Hit]) -> int:
    """Accepting `list[Hit]` rejects `list[SlowHit]`, rightly so.

    If allowed, the body could `hits.append(Hit(...))`, leaving a plain
    `Hit` inside the caller's `list[SlowHit]`. Widen to `Sequence[Hit]`
    (see `count_any`) and the problem disappears — a `Sequence` can't be
    appended to.
    """
    return len(hits)


def count_any(hits: Sequence[Hit]) -> int:
    return len(hits)


def main() -> None:
    hits = parse(RAW_LOG)

    print("1. Parsed")
    print(f"   {len(hits)} hits, {len(by_path(hits))} distinct paths")

    print("\n2. Iterable accepts anything iterable")
    print(f"   from a list:      {render_summary(status_counts(hits))}")
    print(f"   from a generator: {render_summary(status_counts(h for h in hits))}")
    print(f"   from a tuple:     {render_summary(status_counts(tuple(hits)))}")

    print("\n3. Sequence needs indexing")
    worst = slowest(hits)
    print(f"   slowest: {worst.path} at {worst.seconds}s")

    print("\n4. Tuple, fixed vs variadic")
    print(f"   endpoint_key: {endpoint_key(worst)}")
    print(f"   latencies:    {all_latencies(hits)}")

    print("\n5. Mapping is read-only, MutableMapping is not")
    totals: dict[int, int] = {}
    merge_into(totals, status_counts(hits))
    merge_into(totals, {200: 5})
    print(f"   merged: {render_summary(totals)}")

    print("\n6. A generator of failures")
    for hit in errors(hits):
        print(f"   {hit.status} {hit.path} from {hit.ip}")

    print("\n7. Invariance")
    slow: list[SlowHit] = [SlowHit("10.0.0.4", "GET", "/api/v1/owners", 500, 1.288)]
    # mypy: Argument 1 has incompatible type "list[SlowHit]"; expected "list[Hit]"
    print(f"   count_hits(list[SlowHit]) = {count_hits(slow)}  <- rejected by mypy")  # type: ignore[arg-type]
    print(f"   count_any(list[SlowHit])  = {count_any(slow)}  <- accepted: Sequence is covariant")


if __name__ == "__main__":
    main()
