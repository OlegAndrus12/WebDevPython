# uv — a single tool for the whole Python toolchain

## What this project is

The same `statusboard` app as in [`../pipenv_ex/`](../pipenv_ex/) and [`../poetry_ex/`](../poetry_ex/) —
same `app.py`, `checks.py`, `services.py`, `incidents.py`, same templates and CSS. Only the dependency
tooling changes. If you want to understand the app itself (routes, templates, the Cloudflare
integration), read [`../pipenv_ex/README.md`](../pipenv_ex/README.md) — this file covers uv only.

**uv** is a Python packaging tool from Astral (the makers of `ruff`), written in Rust. It replaces pip,
venv, pip-tools, pipx, and — for what this exercise cares about — Poetry: one binary that resolves
dependencies, manages virtual environments, and can install Python itself.

## Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or: brew install uv
# or: pipx install uv

uv --version
```

## Running the project

```bash
cd module01/uv_ex
uv run flask --app app run --debug
```

That's it — one command. `uv run` does everything a Poetry user does by hand: it finds (or
**downloads**) a matching Python, creates `.venv/`, reads `uv.lock`, installs whatever's missing, then
runs the command. Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

Running `uv sync` yourself is optional but sometimes useful:

```bash
uv sync              # bring .venv exactly in line with uv.lock
uv sync --no-dev     # without the dev group — what a deploy installs
```

> **`uv sync` reconciles, it doesn't just add.** A package you installed by hand that isn't in the
> lock file gets **removed**. That's `poetry sync` behavior, not `pip install -r`.

The environment lives in `.venv/` right next to `pyproject.toml` — unlike Poetry, which hides it in a
cache directory by default.

## `pyproject.toml`

```toml
[project]
name = "statusboard"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "flask>=3.1.0,<4.0.0",
    "requests>=2.32.3,<3.0.0",
]

[dependency-groups]
dev = ["bandit>=1.9.4", "pre-commit>=4.6.1", "pytest>=9.1.1", "ruff>=0.14.0"]
```

Compare this with [`../poetry_ex/pyproject.toml`](../poetry_ex/pyproject.toml): the `[project]` block
is identical. Both tools read **PEP 621**, so the manifest itself is portable — only how dev
dependencies are declared differs:

- Poetry: `[tool.poetry.group.dev.dependencies]` — a table owned by one tool;
- uv: `[dependency-groups]` — **PEP 735**, a standard that uv, Poetry 2.x, and pip 25.1+ all read.

There is no `[build-system]` section. Its absence is what marks this as an application rather than a
distributable package: uv only manages the environment, it never tries to build anything. That's the
uv equivalent of Poetry's `package-mode = false`.

### The extended reference file

[`pyproject.reference.toml`](pyproject.reference.toml) is a companion to
[`../poetry_ex/pyproject.reference.toml`](../poetry_ex/pyproject.reference.toml): the `[project]` block
is identical in both, so this one is trimmed down and focused on what changes names going from Poetry
to uv — `[dependency-groups]`, `[tool.uv.sources]`, `[[tool.uv.index]]`, `[tool.uv.workspace]`,
`environments`, `conflicts`, `constraint-dependencies`. It's a cheat sheet, not a template — a real
manifest almost never needs a quarter of it. It's valid and checkable:

```bash
mkdir -p /tmp/uref && cp pyproject.reference.toml /tmp/uref/pyproject.toml
cd /tmp/uref && uv lock && uv tree --depth 1
```

### Poetry syntax, read by uv

Partial compatibility, verified:

| Written as                                              | In uv                                                          |
| -------------------------------------------------------- | --------------------------------------------------------------- |
| `"flask (>=3.1.0,<4.0.0)"` — Poetry's parenthesized form | **works** — it's valid PEP 508                                 |
| `"flask^3.1.0"` — caret                                  | **fails**: `` `project.dependencies[0]` must be pep508 ``       |
| `[tool.poetry.group.dev.dependencies]`                    | **silently ignored** — the packages never get installed         |

The last row is the dangerous one: no error, `uv sync` exits 0, and your dev dependencies quietly
disappear. Migrating from Poetry means rewriting groups into `[dependency-groups]` by hand.

Caret equivalents, if you're converting manually:

```
^1.2.3   →   >=1.2.3,<2.0.0
^0.2.3   →   >=0.2.3,<0.3.0
~1.2.3   →   ~=1.2.3
```

## Creating a `pyproject.toml` from scratch

```bash
uv init statusboard          # application (default)
uv init --lib statusboard    # library: src/ layout + [build-system]
uv init --bare statusboard   # just pyproject.toml, nothing else
uv init                      # in the current folder
```

`uv init --app` produces:

```
statusboard/
├── .gitignore
├── .python-version
├── README.md
├── main.py
└── pyproject.toml
```

Two differences from `poetry new` are visible immediately:

- **no `[build-system]`** — nothing needs building;
- **a `.python-version` file** — it pins the interpreter. `uv run` reads it and **downloads** that
  version if it isn't on the machine. Neither pip nor Poetry can do that on their own; they lean on
  `pyenv` for it.

`--bare` skips `main.py`, `README.md` and `.gitignore` — exactly what you want when the code already
exists, as it does here.

## Migrating from `requirements.txt`

Unlike Poetry, this is a **built-in command**:

```bash
uv init --bare --name statusboard
uv add -r requirements.txt
```

That's the whole migration. On this project's file —

```
Flask==3.1.0
requests==2.32.3
```

— it produces:

```toml
dependencies = [
    "flask==3.1.0",
    "requests==2.32.3",
]
```

plus a `uv.lock` and a ready `.venv/`. uv parses comments and blank lines itself — no `grep`/`tr`
needed, unlike the Poetry migration path.

```bash
uv add --dev -r requirements-dev.txt
```

### The same trap as Poetry

`==` carries over literally. That was correct in `requirements.txt`; in `pyproject.toml` it usually
isn't:

| File             | Holds                                                     |
| ---------------- | ---------------------------------------------------------- |
| `pyproject.toml` | **ranges** — the bounds you're willing to update within   |
| `uv.lock`        | **exact versions** — what's actually installed             |

Pinning both means `uv lock --upgrade` can't even pull in a security patch. Relax the ranges after
migrating:

```bash
uv add "flask>=3.1.0,<4.0.0" "requests>=2.32.3,<3.0.0"
```

### Going back

```bash
uv export -o requirements.txt                       # with hashes
uv export --no-hashes --no-dev -o requirements.txt
```

`uv export` is built in — Poetry needs the separate `poetry-plugin-export` for the same thing.

## Adding a dependency to a specific group

```bash
uv add requests                    # into [project] dependencies — a runtime dependency
uv add --dev pytest                # into the dev group (shorthand for --group dev)
uv add --group docs mkdocs         # any group; created if it doesn't exist
uv add --optional postgres psycopg # an extra, not a group — a different mechanism

uv remove --group docs mkdocs      # drop it from just that group
```

**Groups vs. extras** — easy to conflate:

|                                                    | Who needs it                     | Ships with the built package |
| -------------------------------------------------- | --------------------------------- | ------------------------------ |
| `[dependency-groups]` (`--group`)                  | you, while writing the code       | **no**                        |
| `[project.optional-dependencies]` (`--optional`)   | whoever installs your package     | **yes**                        |

`pytest` is a group. "Postgres support" is an extra.

Installing and excluding groups:

```bash
uv sync                      # main + default-groups (["dev"] unless configured otherwise)
uv sync --group docs         # add another one
uv sync --no-dev             # without dev
uv sync --only-group docs    # only that group, no runtime deps
uv sync --all-groups         # everything
```

## `uv.lock`

```bash
head -30 uv.lock
grep -c 'name = ' uv.lock
```

Same idea as `poetry.lock`: exact versions of every package plus a hash of each archive. The format is
its own (TOML) and **not interchangeable** with `poetry.lock` — it gets committed to git, same as any
lock file.

Check that it's not stale (uv's equivalent of `poetry check --lock`):

```bash
uv lock --check
```

CI uses this, plus:

```bash
uv sync --frozen      # never recompute the lock; fail if it doesn't match
uv sync --locked      # same thing, a synonym
```

## Dependency conflicts

uv's resolver is easiest to see with an unsolvable pair. This is throwaway — build it in `/tmp` so
this project's own `pyproject.toml` and `uv.lock` stay untouched:

```bash
mkdir -p /tmp/uv-conflict && cd /tmp/uv-conflict
cat > pyproject.toml <<'EOF'
[project]
name = "conflict-demo"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "flask==3.1.0",
    "werkzeug==2.3.0",
]
EOF
uv lock
```

```
  × No solution found when resolving dependencies:
  ╰─▶ Because flask==3.1.0 depends on werkzeug>=3.1 and your project
      depends on flask==3.1.0, we can conclude that your project depends on
      werkzeug>=3.1.
      And because your project depends on werkzeug==2.3.0, we can conclude
      that your project's requirements are unsatisfiable.
```

Exit code **1**, no `uv.lock` written. Flask 3.1.0's metadata requires `Werkzeug>=3.1`; pinning
`werkzeug==2.3.0` alongside it has no solution. Read the message as a chain of deduction
("because… and…, we can conclude that…") rather than a bare error — on a graph with dozens of
packages that phrasing is the difference between understanding the conflict in a minute versus an
hour.

### The same file, made solvable

Drop the version on Flask:

```bash
sed -i.bak 's/"flask==3.1.0",/"flask",/' pyproject.toml
uv lock
grep -A1 '^name = "flask"' uv.lock
# name = "flask"
# version = "2.3.1"
```

uv **backtracked** to the newest Flask that still accepts Werkzeug 2.3.0. That's dependency
resolution: not "install the newest," but "find versions that satisfy every constraint at once." pip
and Poetry land on the same `Flask 2.3.1` for this pair — they differ in speed and in how the error
reads, not in the answer.

Clean up:

```bash
cd - && rm -rf /tmp/uv-conflict
```

### Why uv (like Poetry) never leaves a broken environment

`uv add` doesn't "install a package" — it recomputes the whole graph, updates the lock file, and
**syncs the environment to match**. If there's no solution, nothing changes: not `pyproject.toml`, not
`uv.lock`, not `.venv`. Compare that with pip, where consecutive `pip install flask==3.1.0` and
`pip install werkzeug==2.3.0` calls leave incompatible packages installed **and exit 0** — see
[`../pipenv_ex/README.md`](../pipenv_ex/README.md) for that failure mode in detail.

|                                             | pip                    | Poetry     | uv               |
| -------------------------------------------- | ------------------------ | ------------ | ------------------ |
| Detect the conflict up front               | `--dry-run`             | `poetry lock`| `uv lock`         |
| Error message                              | states the conflicting pair | a proof   | a step-by-step proof |
| Backtrack to an older version              | yes                     | yes          | yes                |
| Can leave a broken environment installed   | **yes, and exits 0**    | no           | no                 |

## Dev tools — pytest, ruff, bandit, mypy, pre-commit

This project's `dev` group installs `bandit`, `pytest`, `ruff` and `pre-commit`, so they run the same
way as any other `uv run` command:

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format .
uv run bandit -c pyproject.toml -r .    # -c is mandatory; bandit doesn't read pyproject.toml on its own
uv run pre-commit run --all-files
```

For what each of these tools actually catches, the deliberately-broken files that demonstrate it
(`ruff_demo/messy.py`, `bandit_demo/insecure.py`, `mypy_demo/broken.py`), and the full pytest suite,
see [`../tools/README.md`](../tools/README.md) — that folder is the shared home for those
demonstrations across all three dependency-manager exercises.

## uv replaces more than Poetry

That's the whole pitch: one binary instead of five.

| What you used to run                | uv equivalent                          |
| ------------------------------------ | ---------------------------------------- |
| `pyenv install 3.13`                | `uv python install 3.13`               |
| `python -m venv .venv`              | `uv venv`                               |
| `pip install -r requirements.txt`   | `uv pip install -r requirements.txt`    |
| `pip-tools` / `pip-compile`         | `uv lock`                                |
| `pipx install ruff`                 | `uv tool install ruff`                  |
| `poetry install`                    | `uv sync`                               |
| running a tool once, ad hoc         | `uvx ruff check .`                      |

### Python versions, installed by uv itself

```bash
uv python list                    # everything visible: system + uv-downloaded
uv python install 3.13
uv run --python 3.13 python -V
```

If `requires-python` names a version that isn't on the machine, `uv run` **downloads it**. Neither
Poetry nor pip can do that — you'd reach for `pyenv` separately.

### `uvx` — run without installing

```bash
uvx ruff check .
```

Runs `ruff` without adding it to your project or to `uv tool list`. The environment isn't discarded
though — it's cached and reused, so the first run is slow and later ones are instant:

```bash
uv cache dir      # ~/.cache/uv
uv cache prune    # remove only unreachable entries
uv cache clean    # wipe it entirely
```

### pip-compatible mode

```bash
uv pip install flask
uv pip freeze
uv pip compile pyproject.toml -o requirements.txt
```

`uv pip` deliberately mirrors pip's interface — a way to speed up an existing project without
rewriting it: swap `pip` for `uv pip` and nothing else changes.

## Managing Python versions

uv is the only tool of the three (pip / Poetry / uv) that **downloads** interpreters itself; the other
two only look for one already on the machine, which is why they're usually paired with `pyenv`.
Versions can be pinned at three independent levels: one command, one folder, the whole machine.

```bash
uv python list                    # installed + what could be installed
uv python list --only-installed
uv python dir                     # ~/.local/share/uv/python
uv python find 3.12               # path to a specific interpreter
```

```bash
uv python install 3.13            # one version
uv python install 3.11 3.12 3.13  # several at once
uv python install 3.13t           # free-threaded, no GIL (PEP 703)
uv python upgrade 3.13            # latest patch within 3.13
uv python uninstall 3.11
```

Everything downloaded lives under `~/.local/share/uv/python/` — the system Python is untouched.

| Level             | Set with                                            | Written to                          | Scope                          |
| ------------------ | ----------------------------------------------------- | -------------------------------------- | -------------------------------- |
| one command        | `uv run --python 3.13 …`                             | nowhere                               | a single invocation             |
| shell session      | `export UV_PYTHON=3.13`                              | nowhere                               | the current terminal            |
| this folder        | `uv python pin 3.13`                                 | `.python-version`                     | this folder and subfolders      |
| the project        | `requires-python` in `pyproject.toml`                | `pyproject.toml`                      | anyone who opens the project     |
| the whole machine  | `uv python pin --global 3.12`                        | `~/.config/uv/.python-version`        | anywhere with no pin above it    |

Priority, in that order: `--python` → `UV_PYTHON` → `.python-version` (walking up from the current
folder) → `requires-python` → the global pin. `requires-python` is a compatibility **range** that ships
in the package's metadata; `.python-version` is a single **choice** for working here, right now, and
never leaves the folder. uv rejects a contradiction between them:

```
$ uv python pin 3.11
error: The requested Python version `3.11` is incompatible with the project `requires-python`
value of `>=3.12`.
```

```bash
uv python pin 3.13     # write .python-version
uv python pin --rm     # remove it
uv python pin --global 3.12   # machine-wide fallback, used only when nothing more specific applies
```

`.python-version` is meant to be committed — everyone who clones the folder then gets the same
interpreter regardless of their own machine defaults.

### Switching an existing project to another version

```bash
uv python pin 3.13
uv sync
```

`.venv` is tied to one interpreter (the path is recorded in `pyvenv.cfg`), so changing versions means
recreating it — but `uv sync` notices the mismatch and does that itself:

```
$ uv python pin 3.13 && uv sync
Updated `.python-version` from `3.12` -> `3.13`
Using CPython 3.13.12
Removed virtual environment at: .venv
Creating virtual environment at: .venv
```

### vs. pyenv

| pyenv                    | uv                                    |
| -------------------------- | ---------------------------------------- |
| `pyenv install 3.13`      | `uv python install 3.13`               |
| `pyenv versions`          | `uv python list`                        |
| `pyenv local 3.13`        | `uv python pin 3.13`                    |
| `pyenv global 3.13`       | `uv python pin --global 3.13`           |
| `pyenv shell 3.13`        | `UV_PYTHON=3.13` or `--python 3.13`     |
| compiles from source, minutes | prebuilt binaries, seconds          |
| shims on `PATH` intercept `python` | nothing intercepted            |

## Recreating the environment

Simplest of the three tools, for an architectural reason: uv **always** keeps the environment in
`.venv/` at the project root. No cache directory of hashed names, no "which environment is even
active right now."

```bash
rm -rf .venv && uv sync
```

That's the whole recipe, and it's fast — on this project's ~33 packages, well under a second with a
warm cache (measured above: `uv lock` in 11ms, a full `uv sync` from scratch in ~0.2s). Compare that
with Poetry's `poetry env remove --all && poetry install`, which takes seconds, or pip's
`rm -rf .venv && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.

Same result without `rm -rf`, via `--clear`:

```bash
uv venv --clear && uv sync
```

### When you don't need to recreate anything

Almost never, because `uv sync` **syncs the environment to the lock file** by default:

| Task                                         | Command                                                   |
| ---------------------------------------------- | ------------------------------------------------------------ |
| Bring the environment exactly to the lock     | `uv sync` — this is the **default** behavior                |
| Allow extra packages in the environment       | `uv sync --inexact`                                         |
| Reinstall packages without deleting `.venv`   | `uv sync --reinstall` (or `--reinstall-package flask`)      |
| Recompute versions from scratch               | `uv lock --upgrade && uv sync`                              |
| Switch Python versions                        | `uv python pin 3.13 && uv sync` — recreates `.venv` itself  |
| Clear the package cache                       | `uv cache clean` (or `uv cache prune` for unreachable only) |
| CI: fail if the lock doesn't match            | `uv sync --frozen`                                          |

The first row is the important one. Try it:

```bash
uv pip install httpx
uv sync
```

```
Uninstalled 5 packages in 12ms
 - anyio==4.14.2
 - h11==0.16.0
 - httpcore==1.0.9
 - httpx==0.28.1
 - typing-extensions==4.16.0
```

`pip install -r requirements.txt` has no equivalent to this, which is exactly why environments managed
by plain pip tend to accumulate packages nobody remembers installing.

### Activation

Nothing needs activating: `uv run python app.py`, `uv run pytest`, `uv run flask --app app run` all
find `.venv` on their own. It's a normal venv though, so the usual path still works:

```bash
source .venv/bin/activate      # Windows: .venv\Scripts\activate
```

## Command reference

| Command                             | What it does                                        |
| ------------------------------------- | ------------------------------------------------------ |
| `uv init` / `uv init --app`         | create a new project                                  |
| `uv add flask`                      | add a dependency, update the lock and `.venv`         |
| `uv add --dev ruff`                 | add a dev dependency                                  |
| `uv remove flask`                   | remove a dependency                                   |
| `uv sync`                           | bring `.venv` to match the lock                       |
| `uv sync --no-dev`                  | without the dev group                                 |
| `uv sync --frozen`                  | don't touch the lock; fail if it's stale              |
| `uv lock`                           | recompute the lock                                    |
| `uv lock --check`                   | verify the lock is current                            |
| `uv lock --upgrade`                 | upgrade everything within the declared bounds         |
| `uv run <cmd>`                      | run a command (syncing first)                         |
| `uv tree`                           | dependency tree                                       |
| `uv export -o requirements.txt`     | generate a `requirements.txt`                         |
| `uv venv` / `uv venv --clear`       | create / recreate the venv by hand                    |
| `uv cache clean` / `uv cache prune` | clear the package cache / just unreachable entries    |
| `uv python install 3.13`            | download an interpreter                               |
| `uv python pin 3.13`                | write `.python-version` for this folder               |
| `uv python pin --global 3.12`       | machine-wide default                                  |
| `uv tool install ruff` / `uvx ruff` | install a tool globally / run it once, uncached       |
| `uv build` / `uv publish`           | build a wheel + sdist / publish to PyPI (needs `[build-system]`) |

## What uv gives you over pip and Poetry

| Capability                        | pip           | Poetry     | uv               |
| ------------------------------------ | --------------- | ------------ | ------------------ |
| Lock file with hashes              | no             | yes         | yes               |
| Direct vs. transitive dependencies  | no distinction | separated   | separated         |
| Dependency groups                  | no             | yes         | yes (PEP 735)     |
| Removes what's no longer declared  | no             | `poetry sync` | `uv sync`       |
| Creates the venv                   | no             | yes         | yes               |
| Installs Python itself             | no             | no          | yes               |
| Builds a distributable package     | no             | yes         | yes               |
| Standard manifest (PEP 621)        | no             | yes         | yes               |
| Resolver speed on this project     | —              | seconds     | milliseconds      |

Don't mix package managers in one project: two lock files that know nothing about each other is a
version conflict waiting to surface in production.
