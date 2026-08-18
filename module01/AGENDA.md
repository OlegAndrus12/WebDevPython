# Module 01 — Agenda

A small Flask "statusboard" app is rebuilt across `pipenv_ex/` → `poetry_ex/` → `uv_ex/`, each
folder swapping in a different dependency manager while the application code stays identical. The
same app also carries a variant with logging added (`poetry_logger/`) and hosts the shared
pytest/ruff/bandit/mypy demos (`tools/`). From there the module moves to Python's type-annotation
system, then to object-oriented design: SOLID principles and classic design patterns, each shown as
a runnable before/after.

## Topics

### Dependency management
- **pip & venv** (`pipenv_ex/`) — `requirements.txt`, virtual environments, and where pip falls
  short: no lock file, no dependency groups, silent broken environments
- **Poetry** (`poetry_ex/`) — `pyproject.toml`, `poetry.lock`, dependency groups, dependency
  resolution and conflict detection
- **uv** (`uv_ex/`) — the same manifest managed by a single fast Rust binary: locking, syncing,
  Python version management, replacing pyenv/pip-tools/pipx
- **Poetry vs. uv speed** (`poetry_vs_uv_compare/`) — measured lock/install benchmarks
- **Logging** (`poetry_logger/`) — adding console + file logging to the statusboard app
- **Dev tooling** (`tools/`) — pytest, ruff, bandit, mypy, pre-commit: what each catches and how to
  run it, plus deliberately-broken demo files for each

### Type annotations
- **`type_annotation_extras/`** — ten runnable lessons: hints vs. runtime checks, collections and
  variance, aliases vs. `NewType`, generics and `ParamSpec`, `Protocol`, `TypedDict`/`Literal`,
  narrowing, common pitfalls, forward references, and deprecated-vs-modern syntax

### Design principles & patterns
- **SOLID** (`solid/`) — all five principles, each as a before/after: Single Responsibility,
  Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion
- **Design patterns** (`patterns/`) — Adapter, Observer, Proxy, Singleton, State, Template Method
