"""Narrowing — how the checker turns a union back into one type.

A union is only useful if you can get out of it. Narrowing is control flow
proving a value's type: after `if x is None: return`, `x` is no longer
`str | None`. Most of it is automatic — know the rules and you stop writing
`cast` or `# type: ignore` where a plain `isinstance` would do.

The one non-obvious win: `assert_never` turns "you added a variant and forgot
to handle it" from a production bug into a type error.

Domain: consuming a message queue whose payloads are a tagged union.

Run: python3 07_narrowing.py
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, NoReturn, TypeGuard, assert_never

# ---------------------------------------------------------------------------
# 1. A tagged union of dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Enqueue:
    kind: Literal["enqueue"]
    job: str
    payload: dict[str, str]


@dataclass(frozen=True, slots=True)
class Cancel:
    kind: Literal["cancel"]
    job_id: str


@dataclass(frozen=True, slots=True)
class Drain:
    kind: Literal["drain"]
    queue: str
    grace_seconds: int


# A `Literal` discriminator on each member makes this a *tagged* union —
# the checker narrows on `message.kind` without an isinstance call.
Message = Enqueue | Cancel | Drain


def handle(message: Message) -> str:
    """`match` on the tag, with `assert_never` as the closing arm.

    Add a fourth member to `Message` and mypy fails right here:
        Argument 1 to "assert_never" has incompatible type "Restart"
    That's the point — exhaustiveness, checked. `raise ValueError` in the
    same slot would compile fine and fail in production.
    """
    match message:
        case Enqueue(job=job, payload=payload):
            return f"queued {job} with {len(payload)} args"
        case Cancel(job_id=job_id):
            return f"cancelled {job_id}"
        case Drain(queue=queue, grace_seconds=grace):
            return f"draining {queue}, {grace}s grace"
        case _:
            assert_never(message)


def handle_by_tag(message: Message) -> str:
    """Same narrowing without `match` — on the Literal field alone."""
    if message.kind == "enqueue":
        return message.job  # narrowed to Enqueue; `.job_id` would be an error
    if message.kind == "cancel":
        return message.job_id
    return message.queue


# ---------------------------------------------------------------------------
# 2. The narrowing operations that come for free
# ---------------------------------------------------------------------------


def deadline_of(raw: str | int | None, default: int = 30) -> int:
    """isinstance, `is None`, truthiness, and early return all narrow."""
    if raw is None:
        return default
    if isinstance(raw, int):
        return raw
    # Here `raw` is `str` — nothing else is left in the union.
    return int(raw) if raw.isdigit() else default


def first_word(line: str | None) -> str:
    """`or` and `and` narrow too — no isinstance needed here."""
    if not line:
        return ""
    return line.split()[0]


def widen(value: object) -> str:
    """Narrowing from `object` uses the same machinery, exhaustively.

    Note `type(value) is bool` comes before the int branch: `bool` subclasses
    `int`, so `isinstance(True, int)` is True and order matters.
    """
    if type(value) is bool:
        return f"bool:{value}"
    if isinstance(value, int):
        return f"int:{value}"
    if isinstance(value, (list, tuple)):
        return f"sequence of {len(value)}"
    if hasattr(value, "kind"):
        # `hasattr` narrows in recent mypy — don't rely on it; a
        # Protocol (file 05) states the requirement instead of sniffing.
        return f"message:{value.kind}"
    return f"other:{type(value).__name__}"


# ---------------------------------------------------------------------------
# 3. TypeGuard — narrowing the checker cannot infer
# ---------------------------------------------------------------------------

