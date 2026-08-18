# Web Development with Python

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)

A teaching repository. Each folder is a small, self-contained project built to make **one idea**
concrete — run it, break it, read why it broke.

<img src="yoda.jpg" alt="May the Force be with you" width="280">

```
├── module01/   Python tooling, typing, and object-oriented design
```

**Conventions used throughout:**

- Every folder has its own `README.md` explaining that folder and nothing else.
- Design examples come in pairs — `before.py` breaks the principle, `after.py` applies it. Both run.
- Every example project pins its own dependencies (`pyproject.toml` + a lock file), so folders never
  interfere with each other.
- Python 3.12+.

---

# Module 01 — Python tooling, typing and design

Three parts, in order: **how dependencies are managed**, **how types are described**, and **how code is
structured**.

The first part rebuilds `statusboard` three times over. The application code stays identical; only the
manifest changes. When two folders differ by exactly one thing, that one thing is what you learn.

## 📦 Dependency management

| Folder | What it covers |
| --- | --- |
| **[pipenv_ex/](module01/pipenv_ex/)** | `pip`, `venv` and `requirements.txt` — and where pip runs out: no lock file, no dependency groups, and successive installs that break an environment while exiting `0` |
| **[poetry_ex/](module01/poetry_ex/)** | `pyproject.toml` + `poetry.lock` — ranges versus resolved versions, dependency groups, hashes, and a resolver that explains its conflicts as a proof |
| **[uv_ex/](module01/uv_ex/)** | The same manifest, one Rust binary: locking, syncing, and managing Python versions — replacing pip, venv, pip-tools, pipx and pyenv at once |
| **[poetry_vs_uv_compare/](module01/poetry_vs_uv_compare/)** | Measured benchmarks rather than claims — [`bench.html`](module01/poetry_vs_uv_compare/bench.html) charts the results in [`results.json`](module01/poetry_vs_uv_compare/results.json) |
| **[poetry_logger/](module01/poetry_logger/)** | The same app with console and file logging added |
| **[tools/](module01/tools/)** | `pytest`, `ruff`, `bandit`, `mypy`, `pre-commit` — what each one catches, with deliberately broken files to prove it |

The benchmarks are worth seeing before picking a side. Locking and installing the `statusboard`
dependency set, on the same machine:

| | pip | Poetry | uv |
| --- | --- | --- | --- |
| **lock** | 3.52 s | 2.62 s | **0.09 s** |
| **install** (cold cache) | 15.49 s | 9.77 s | **6.86 s** |
| **install** (warm cache) | 9.10 s | 2.34 s | **0.13 s** |

The gap widens with project size — see [`results.json`](module01/poetry_vs_uv_compare/results.json)
for the larger `zoo_api` set.

## 🏷️ Type annotations

**[type_annotation_extras/](module01/type_annotation_extras/)** — ten runnable lessons, meant to be
read in order, since each builds vocabulary the next one assumes.

| | Lesson | | Lesson |
| --- | --- | --- | --- |
| 01 | [Basics](module01/type_annotation_extras/01_basics.py) — hints vs. runtime checks, `Final`, `Any` vs `object` | 06 | [TypedDict & Literal](module01/type_annotation_extras/06_typeddict_literal.py) — describing shaped data, `@overload` |
| 02 | [Collections](module01/type_annotation_extras/02_collections.py) — `collections.abc`, invariance vs. covariance | 07 | [Narrowing](module01/type_annotation_extras/07_narrowing.py) — `TypeGuard`, `assert_never` |
| 03 | [Aliases](module01/type_annotation_extras/03_aliases.py) — three generations of syntax, vs. `NewType` | 08 | [Pitfalls](module01/type_annotation_extras/08_pitfalls.py) — hints that don't check, mutable defaults |
| 04 | [Generics](module01/type_annotation_extras/04_generics.py) — `TypeVar`, PEP 695 syntax, `ParamSpec` | 09 | [Forward refs](module01/type_annotation_extras/09_forward_refs.py) — PEP 563, postponed evaluation |
| 05 | [Protocols](module01/type_annotation_extras/05_protocols.py) — structural vs. nominal typing | 10 | [Deprecations](module01/type_annotation_extras/10_deprecations.py) — old syntax beside its replacement |

## 🧱 SOLID

**[solid/](module01/solid/)** — all five principles, each a runnable `before.py` / `after.py` pair.
Every file opens with a one-sentence docstring naming the principle, so it explains itself when read
alone.

| | Principle | The example |
| --- | --- | --- |
| **S** | [Single Responsibility](module01/solid/S/) | One function that both reshapes an API payload and prints it, split in two |
| **O** | [Open/Closed](module01/solid/O/) | A `match` over notification channels, replaced by one subclass per channel |
| **L** | [Liskov Substitution](module01/solid/L/) | A read-only storage that inherits `save()` only to raise — plus a subtler signature violation |
| **I** | [Interface Segregation](module01/solid/I/) | A four-method interface forcing `NotImplementedError`, split into roles |
| **D** | [Dependency Inversion](module01/solid/D/) | A service that builds its own database and mailer, versus one handed them |

## 🧩 Design patterns

**[patterns/](module01/patterns/)** — six patterns, each with a runnable example.

| Pattern | The example |
| --- | --- |
| **[Adapter](module01/patterns/adapter/)** | Three carrier APIs with three payload shapes, behind one `ShippingQuote` |
| **[Observer](module01/patterns/observer/)** | An event source fanning log lines out to a console and a file |
| **[Proxy](module01/patterns/proxy/)** | Rate limiting, IP blocking as Django middleware, and real WSGI middleware in front of Flask |
| **[Singleton](module01/patterns/singleton/)** | Settings loaded once — the `__new__` textbook version, and the `lru_cache` version you'd actually write |
| **[State](module01/patterns/state/)** | A state machine written twice: `match`/`case` versus one class per state |
| **[Template Method](module01/patterns/template_method/)** | An export routine with one overridable hook — and the Liskov violation it invites |

📋 Full topic list: **[module01/AGENDA.md](module01/AGENDA.md)**

---

