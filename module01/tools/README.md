# tools

The same `statusboard` app as `../poetry_ex/`, `../pipenv_ex/`, etc., kept here as one shared home
for the dev-tool demos: pytest, ruff, bandit, mypy and pre-commit. All five are configured once, in
[`pyproject.toml`](pyproject.toml).

## Setup

```bash
cd module01/tools
uv sync
```

Every command below assumes `uv run <tool>` from this folder.

## pytest — does the app still behave?

**Problem it solves:** confirms the app's actual behavior (add/delete a service, reject bad input)
without opening a browser, and catches regressions the moment someone changes `app.py`.

```bash
uv run pytest -q          # 5 tests, tests/test_app.py
uv run pytest -v
uv run pytest -k delete   # one test by name
```

## ruff — linter + formatter

**Problem it solves:** catches unused imports, dead code, real bug patterns (mutable default
arguments, bare `except`), and outdated syntax — then reformats the file — all in one fast binary.

```bash
uv run ruff check .              # find problems
uv run ruff check --fix .        # fix what's auto-fixable
uv run ruff format .             # reformat
uv run ruff format --check .     # CI mode: fail if unformatted, change nothing
```

Broken on purpose, so excluded from the folder-wide check: [`ruff_demo/messy.py`](ruff_demo/messy.py).
Point ruff at it directly:

```bash
uv run ruff check ruff_demo/messy.py
uv run ruff check --diff ruff_demo/messy.py   # preview what --fix would change
```

## bandit — security scanner

**Problem it solves:** finds actual vulnerabilities that ruff doesn't look for — hardcoded
passwords, `shell=True`, requests without a timeout, weak crypto.

```bash
uv run bandit -c pyproject.toml -r .        # -c is mandatory, or it scans .venv too
uv run bandit -c pyproject.toml -r . -ll    # medium severity and up only
```

Broken on purpose: [`bandit_demo/insecure.py`](bandit_demo/insecure.py) (33 findings across 29
rules). It exists to be scanned, not run:

```bash
uv run bandit -r bandit_demo/
```

## mypy — static type checking

**Problem it solves:** catches type mismatches Python itself never checks at runtime — `None`
where an attribute is accessed, wrong argument types, unreachable branches — before the code runs.

```bash
uv run mypy                  # everything listed in [tool.mypy] files
uv run mypy app.py           # one file
uv run mypy --install-types  # fetch missing stubs (e.g. types-requests)
```

Broken on purpose: [`mypy_demo/broken.py`](mypy_demo/broken.py) (46 errors across 33 codes,
including cases mypy can't catch at all — see the file's last section). Point mypy at it directly:

```bash
uv run mypy mypy_demo/broken.py
```

## pre-commit — run the above automatically on `git commit`

**Problem it solves:** stops broken code from being committed at all, instead of relying on
someone remembering to run the checks by hand.

```bash
uv run pre-commit install          # wire the hook into .git/hooks (once)
uv run pre-commit run --all-files  # run every hook now, on everything
uv run pre-commit run ruff-check   # one hook only
```

Config: [`.pre-commit-config.yaml`](.pre-commit-config.yaml). It runs `ruff-check`, `ruff-format`,
`bandit` and `mypy` — the same tools and settings as above. Since this repo holds multiple
projects, the hooks are scoped with `files: ^module01/tools/`, so from the repo root you need:

```bash
pre-commit run --config module01/tools/.pre-commit-config.yaml --all-files
```

The three `*_demo/` folders are excluded from every hook and from the plain `ruff check .` /
`mypy` / `bandit -r .` runs above — they're broken on purpose, and fixing or flagging them would
erase the thing they're there to demonstrate.
