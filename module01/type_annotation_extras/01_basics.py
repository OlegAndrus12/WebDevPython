"""

A hint is neither a cast nor a check — a `str` passed where `float` is
annotated still succeeds. Every line has two audiences: mypy, which reads
hints, and the interpreter, which ignores them.

Run: python3 01_basics.py
"""

from typing import Any, Final, Optional

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# `Final` means "assigned once" — mypy enforces it, interpreter doesn't;
# documented, not frozen.
DEFAULT_TIMEOUT: Final = 5.0
MAX_RETRIES: Final[int] = 3  # explicit form; bare `Final` would infer Literal[3]

# A value-less declaration — legal, creates no attribute. See
# `has_no_value()`.
resolved_host: str


# ---------------------------------------------------------------------------
# Function signatures
# ---------------------------------------------------------------------------


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    """Exponential backoff with a ceiling.

    `base: float = 0.5` puts default and hint in one line, never reversed.
    `float` accepts `int` (which accepts `bool`): a numeric-tower special
    case, so `backoff_delay(2, base=1)` type-checks.
    """
    # `2.0**attempt`, not `2**attempt`: typeshed types `int ** int` as `Any`
    # (it can be float for a negative exponent) — under --strict that leak
    # is reported as `no-any-return`.
    return min(cap, base * 2.0**attempt)


def log_attempt(attempt: int, url: str) -> None:
    """`-> None` means "returns nothing useful" — not optional.

    An unannotated function is unchecked: mypy skips its body, treats every
    call as valid. `-> None` makes it checked; `--strict` requires it.
    """
    print(f"  attempt {attempt} -> {url}")


# Pre-3.10 spelling — common in libraries supporting old Pythons, and as
# `Union[int, str]` for multiple members.
LegacyTimeout = Optional[float]  # noqa: UP045  # ruff would rewrite this to `float | None`


def parse_retry_after(header: str | None) -> float | None:
    """`X | None` (PEP 604, 3.10+) is the modern spelling of `Optional[X]` —
    both just mean "this value or None". `Optional` isn't "optional
    argument"; that's what a default value does.
    """
    if header is None:
        return None
    try:
        return float(header)
    except ValueError:
        return None


def fetch(url: str, *, timeout: float = DEFAULT_TIMEOUT, retries: int = MAX_RETRIES) -> str:
    """Keyword-only parameters are annotated exactly like positional ones."""
    for attempt in range(retries):
        log_attempt(attempt, url)
        delay = backoff_delay(attempt)
        if delay > timeout:
            break
    return f"200 OK {url}"


def collect(*urls: str, **headers: str) -> list[str]:
    """`*args`/`**kwargs` annotate the type of a *single* item — `urls`
    appears inside the body as `tuple[str, ...]`, `headers` as
    `dict[str, str]`.
    """
    return [f"{u} ({len(headers)} headers)" for u in urls]


# ---------------------------------------------------------------------------
# The runtime does not care
# ---------------------------------------------------------------------------


def endpoint_of(config: dict[str, str]) -> str:
    return config["endpoint"]


def has_no_value() -> bool:
    """`resolved_host: str` above created no variable — only an annotation."""
    return "resolved_host" in globals()


def annotations_are_data() -> None:
    """Hints are stored as plain data, readable at runtime — see `__annotations__` below."""
    print("  backoff_delay.__annotations__:")
    for name, hint in backoff_delay.__annotations__.items():
        print(f"    {name:8} {hint}")


# ---------------------------------------------------------------------------
# Any — the escape hatch, and the hole it opens
# ---------------------------------------------------------------------------


def dangerous(payload: Any) -> int:
    """`Any` is compatible with everything, both ways: `payload.anything().at.all`
    type-checks, and so does returning it as `int`. `Any` isn't "unknown" —
    it's "stop checking here"; for genuinely unknown values, use `object`,
    which accepts anything but permits almost no operations, forcing a
    narrow before use.

    The `type: ignore` below is the one thing --strict catches: an `Any`
    escaping a declared return type (`--warn-return-any`). The rest of the
    body stays unchecked.
    """
    return payload.total  # type: ignore[no-any-return]


def safe(payload: object) -> int:
    if isinstance(payload, int):  # narrowing — see file 07
        return payload
    return 0


def main() -> None:
    print("1. A well-typed call")
    print(f"   {fetch('https://api.example.com/v1/charges', timeout=2.0)}")

    print("\n2. Retry-After parsing")
    for header in ("1.5", "soon", None):
        print(f"   {header!r:8} -> {parse_retry_after(header)}")

    print("\n3. The interpreter ignores the hints")
    # `endpoint_of` wants `dict[str, str]`; a list has no such keys.
    # mypy: Argument 1 has incompatible type "list[int]"; expected "dict[str, str]"
    try:
        endpoint_of([1, 2, 3])  # type: ignore[arg-type]
    except TypeError as exc:
        print(f"   the hint did not stop the call; the *runtime* did: {exc}")

    print("\n4. A declaration is not an assignment")
    print(f"   'resolved_host' in globals(): {has_no_value()}")

    print("\n5. Hints are ordinary data")
    annotations_are_data()

    print("\n6. Any vs object")
    print(f"   safe('12') -> {safe('12')}   (narrowed away, no crash)")
    try:
        dangerous({"total": 10})
    except AttributeError as exc:
        print(f"   dangerous() type-checks but explodes: {exc}")


if __name__ == "__main__":
    main()
