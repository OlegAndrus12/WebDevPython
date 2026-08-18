"""Protocol — structural typing, or "typed duck typing".

ABC asks *what did you inherit*; Protocol asks *what do you have*. Anything
with the right shape satisfies a `Protocol` — no import, no registration, no
inheritance. That's why it fits dependency inversion: the interface lives by
the *consumer*, and implementations never learn about it.

    ABC        -> you own the implementations, want shared code
    Protocol   -> you don't own them (stdlib, third party, test fakes)

Domain: outbound notifications for a deployment pipeline.

Run: python3 05_protocols.py
"""

from __future__ import annotations

import io
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# 1. A protocol the implementations do not know about
# ---------------------------------------------------------------------------


class Notifier(Protocol):
    """The consumer's requirement, stated by the consumer.

    `...` marks a declaration, not a callable abstract method —
    instantiating `Notifier()` errors.
    """

    def send(self, subject: str, body: str) -> None: ...


@dataclass(slots=True)
class SlackNotifier:
    """No `(Notifier)` base class, no import either."""

    channel: str
    sent: list[str] = field(default_factory=list)

    def send(self, subject: str, body: str) -> None:
        self.sent.append(subject)
        print(f"   [slack {self.channel}] {subject}: {body}")


@dataclass(slots=True)
class EmailNotifier:
    to: str
    sent: list[str] = field(default_factory=list)

    def send(self, subject: str, body: str) -> None:
        self.sent.append(subject)
        print(f"   [email {self.to}] {subject}")


class NullNotifier:
    """A four-line test double is a first-class implementation here."""

    def send(self, subject: str, body: str) -> None:
        pass


def announce(deploy_id: str, notifiers: Iterable[Notifier]) -> None:
    """Depends on shape, so it never imports a concrete notifier."""
    for notifier in notifiers:
        notifier.send(f"deploy {deploy_id} finished", "all health checks green")


# ---------------------------------------------------------------------------
# 2. Protocols also describe types you could never subclass
# ---------------------------------------------------------------------------


class SupportsWrite(Protocol):
    """Roughly how stdlib types `print(file=...)`.

    `sys.stdout`, a file, `io.StringIO`, a socket wrapper, a logging adapter
    all satisfy it. No ABC covers that set — nobody owns every class.
    """

    def write(self, s: str, /) -> int | None: ...


def dump_report(rows: Iterable[str], out: SupportsWrite) -> None:
    for row in rows:
        out.write(f"{row}\n")


# ---------------------------------------------------------------------------
# 3. Attributes, properties, and read-only members
# ---------------------------------------------------------------------------


class Check(Protocol):
    """A protocol member can be data, not just a method.

    `name: str` needs a *settable* attribute — a setter-less `@property`
    fails it. A read-only property member (below) accepts either, the
    safer default.
    """

    @property
    def name(self) -> str: ...

    @property
    def critical(self) -> bool: ...

    def run(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class HttpCheck:
    name: str  # a frozen attribute satisfies a read-only property member
    url: str
    critical: bool = False

    def run(self) -> bool:
        return "://" in self.url


class MigrationCheck:
    """Satisfies the same protocol with computed properties instead."""

    def __init__(self, pending: int) -> None:
        self._pending = pending

    @property
    def name(self) -> str:
        return f"migrations({self._pending} pending)"

    @property
    def critical(self) -> bool:
        return self._pending > 0

    def run(self) -> bool:
        return self._pending == 0


def gate(checks: Iterable[Check]) -> bool:
    ok = True
    for check in checks:
        passed = check.run()
        flag = "critical" if check.critical else "advisory"
        print(f"   {'PASS' if passed else 'FAIL'} {check.name} ({flag})")
        ok = ok and (passed or not check.critical)
    return ok


# ---------------------------------------------------------------------------
# 4. runtime_checkable — isinstance() at the cost of precision
# ---------------------------------------------------------------------------


@runtime_checkable
class Closeable(Protocol):
    def close(self) -> None: ...


def shutdown(resources: Iterable[object]) -> None:
    """`isinstance` on a protocol needs `@runtime_checkable`; it checks only
    that names exist — never signatures, never data members (raises
    TypeError). Prefer static checking; use this only for real duck-typing
    at boundaries.
    """
    for resource in resources:
        if isinstance(resource, Closeable):
            resource.close()
            print(f"   closed {type(resource).__name__}")
        else:
            print(f"   skipped {type(resource).__name__} (no close())")


# ---------------------------------------------------------------------------
# 5. Explicit inheritance is still allowed — and sometimes wanted
# ---------------------------------------------------------------------------


class PagerNotifier(Notifier, Protocol):
    """Subclassing a Protocol makes a *wider* protocol."""

    def acknowledge(self, incident_id: str) -> None: ...


class OpsGenie(Notifier):
    """Inheriting a Protocol also gives nominal checking.

    Worth it when you own the class: mypy verifies the shape at
    definition, not at each call site — a typo in the method name is
    caught here, not downstream.
    """

    def send(self, subject: str, body: str) -> None:
        print(f"   [pager] {subject}")


class PagerDuty:
    """Wide enough for `PagerNotifier`; `OpsGenie` isn't."""

    def send(self, subject: str, body: str) -> None:
        print(f"   [pagerduty] {subject}")

    def acknowledge(self, incident_id: str) -> None:
        print(f"   [pagerduty] ack {incident_id}")


def escalate(incident_id: str, pager: PagerNotifier) -> None:
    """Requires both methods — `escalate(..., OpsGenie())` is a type error."""
    pager.send(f"incident {incident_id}", "paging on-call")
    pager.acknowledge(incident_id)


def main() -> None:
    slack = SlackNotifier("#deploys")
    email = EmailNotifier("ops@example.com")

    print("1. Structural: three unrelated classes, one parameter type")
    announce("d-8123", [slack, email, NullNotifier(), OpsGenie()])

    print("\n2. Same protocol, unrelated stdlib types")
    buffer = io.StringIO()
    dump_report(["queue-depth=12", "p99=430ms"], buffer)
    print(f"   into StringIO: {buffer.getvalue().strip().splitlines()}")
    dump_report(["   straight to sys.stdout"], sys.stdout)

    print("\n3. Attributes and properties")
    checks: list[Check] = [
        HttpCheck("api", "https://api.example.com", critical=True),
        HttpCheck("docs", "api.example.com"),
        MigrationCheck(pending=2),
    ]
    print(f"   gate open: {gate(checks)}")

    print("\n4. runtime_checkable")
    shutdown([buffer, slack, io.BytesIO()])

    print("\n5. Protocols compose")
    escalate("inc-501", PagerDuty())
    # mypy: Argument 2 has incompatible type "OpsGenie"; expected "PagerNotifier"
    print("   escalate(..., OpsGenie()) -> rejected: no acknowledge()")

    print("\n6. A Protocol is a description, not a class to instantiate")
    try:
        Notifier()  # type: ignore[misc]  # mypy: Cannot instantiate protocol class
    except TypeError as exc:
        print(f"   {exc}")


if __name__ == "__main__":
    main()
