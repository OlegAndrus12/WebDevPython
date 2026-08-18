"""
An annotation is just an expression, and normally the interpreter evaluates
it the instant it's reached. That's why a forward reference — a name not yet
defined — used to raise `NameError` at import time. `from __future__ import
annotations` (PEP 563) postpones evaluation: annotations become strings,
stored but never evaluated at runtime, left for a type checker to read
lazily. So `SomeClass` can appear in `foo`'s signature before the class is
defined below, or exist only behind a `TYPE_CHECKING` guard, without the
interpreter ever objecting.

Run: python3 09_forward_refs.py
"""

from __future__ import annotations


def foo(x: SomeClass) -> SomeClass:   # fine even if SomeClass is defined later
    return x


class SomeClass:
    def __repr__(self) -> str:
        return "SomeClass()"


if __name__ == "__main__":
    print(foo(SomeClass()))
