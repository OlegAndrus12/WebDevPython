# type_annotation_extras


## Lessons

| File                        | Topic                                                                 |
| --------------------------- | ---------------------------------------------------------------------- |
| `01_basics.py`               | Hints vs. checks, `Final`, `Optional`/`X \| None`, `*args`/`**kwargs`, `Any` vs `object` |
| `02_collections.py`          | Builtin generics, `collections.abc` roles, invariance vs. covariance (`list` vs. `Sequence`) |
| `03_aliases.py`              | Type aliases (three generations of syntax) vs. `NewType`               |
| `04_generics.py`             | Generic functions/classes, `TypeVar` vs. PEP 695 `[T]` syntax, `ParamSpec` |
| `05_protocols.py`            | `Protocol` — structural typing vs. nominal (ABC) typing                |
| `06_typeddict_literal.py`    | `TypedDict`, `Literal`, `@overload`, `Annotated` for describing shaped data |
| `07_narrowing.py`            | How the checker narrows unions; `TypeGuard`, `assert_never`            |
| `08_pitfalls.py`             | Common mistakes: hints that don't check, mutable defaults, invariance surprises, and more |
| `09_forward_refs.py`         | Postponed evaluation (`from __future__ import annotations`, PEP 563) and forward references |
| `10_deprecations.py`         | Deprecated typing syntax next to its modern replacement, as a cheat sheet |

Run them in order the first time through — later files assume the vocabulary (`Protocol`,
narrowing, generics) established earlier, and cross-reference each other by number in comments.

## Requirements

Python 3.12+ (several files use PEP 695 generic syntax and the `type` statement, both 3.12+
only). No dependencies beyond the standard library — nothing here needs a venv.
