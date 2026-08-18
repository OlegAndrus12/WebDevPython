# Poetry — dependency management with a lock file

## What this project is

**`statusboard`** — the same small Flask app as in [`../pipenv_ex/`](../pipenv_ex/): the same `app.py`,
`checks.py`, `services.py`, `incidents.py`, the same templates, the same CSS. The two copies differ only
in cosmetic details; nothing about how the app works has changed.

What changed is **only how dependencies are described**.

| | pip (`pipenv_ex`) | Poetry (this folder) |
| --- | --- | --- |
| Manifest | `requirements.txt` | `pyproject.toml` |
| Lock file | none | `poetry.lock` |
| Dependency groups | none | yes (`dev`, plus any of your own) |
| Package hashes | none | yes |
| venv creation | by hand | automatic |
| Build & publish | no | `poetry build`, `poetry publish` |

If you want to understand **the app itself** — Flask, templates, the Cloudflare API — read the README in
[`../pipenv_ex/`](../pipenv_ex/README.md). This one is only about Poetry.

## What Poetry is

**Poetry** is a dependency manager and build tool for Python. Where pip installs packages one at a
time and forgets about it, Poetry maintains a complete description of your project:

- **`pyproject.toml`** — the manifest: what you asked for, as version *ranges*
- **`poetry.lock`** — the resolution: what you actually got, as exact versions plus SHA-256 hashes
- **the virtual environment** — created and managed for you, no `python -m venv` required

The split between those first two files is the whole idea. `requirements.txt` had to be either a
statement of intent or a reproducible snapshot; it could never be both. Poetry gives you one file for
each.

---

## Installing Poetry

Poetry isn't a project dependency — don't `pip install` it into your venv. It's a standalone tool:

```bash
uv tool install poetry
# or: pipx install poetry
# or: curl -sSL https://install.python-poetry.org | python3 -

poetry --version
```

---

## How to run the project

```bash
cd module01/poetry_ex

poetry install
poetry run flask --app app run --debug
```

Then open http://127.0.0.1:5000

Note what's missing: **no `python -m venv`, no activation**. Poetry created the virtual environment
and installed the packages into it. Where it lives:

```bash
poetry env info --path
```

By default that's in a cache directory (`~/Library/Caches/pypoetry/virtualenvs/` on macOS), not in the
project folder. If you'd rather have a `.venv/` next to the code, as in the previous folder:

```bash
poetry config virtualenvs.in-project true
```

### `poetry run` and activation

```bash
poetry run flask --app app run    # run one command inside the environment
poetry run python
poetry env activate               # prints the activation command (Poetry 2.x)
```

`poetry run` doesn't activate the environment — it just runs a command inside it. That covers 99% of
cases. There is no `poetry shell` in Poetry 2.x; `poetry env activate` **prints** the command for you
to `eval`, because a child process can't change your shell.

### What you'll see

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser.

On the **Status board**:
- ✅ **5 green** services (Cloudflare, AWS, Instagram, GitHub, PyPI) — reachable
- 🔴 **1 red** (`no-such-host.invalid`) — **broken on purpose**, so you can see what a failure looks like

On the **Cloudflare incidents** tab:
- The 50 most recent incidents on Cloudflare's services, roughly the last three weeks
- Fetched from a public API, no authentication required

---

## Project structure

| File | Role |
| --- | --- |
| **`pyproject.toml`** | the manifest — dependencies, groups, and the config for ruff, pytest, bandit and mypy |
| **`poetry.lock`** | the resolution — 40 packages pinned exactly, with ~520 SHA-256 hashes |
| **`pyproject.reference.toml`** | an annotated cheat sheet of nearly everything `pyproject.toml` can hold |
| **`conflict/`** | a separate mini-project with two requirements that cannot both be satisfied |
| **`app.py`** | Flask app: routes `GET /`, `GET /incidents`, `POST /services`, `POST /services/delete` |
| **`checks.py`** | standalone module: probes a URL, measures latency, returns a result dict |
| **`services.py`** | manages the watch list: reads and writes JSON, no database |
| **`services.json`** | the list itself (name → URL) |
| **`incidents.py`** | fetches incidents from Cloudflare's public API, parses ISO dates, sorts them |
| **`templates/`** | `base.html`, `index.html`, `incidents.html` |
| **`static/style.css`** | all the CSS: light and dark themes, responsive layout |

> The test suite and the deliberately-broken demo folders for ruff, bandit and mypy live in
> [`../tools/`](../tools/), which is where those tools are actually exercised. The **configuration**
> for all four stays here, in `pyproject.toml`, to show what a single manifest can hold.

---

## Key concepts

### 1. `pyproject.toml`

```toml
[project]
name = "statusboard"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "flask (>=3.1.0,<4.0.0)",
    "requests (>=2.32.3,<3.0.0)",
]

[tool.poetry]
package-mode = false

[tool.poetry.group.dev.dependencies]
ruff = "^0.14.0"
```

Three things worth unpacking.

**`[project]` is a standard, not a Poetry invention.** It's PEP 621. The same block is read by uv, pip,
hatch and setuptools. Poetry used to have its own format (`[tool.poetry.dependencies]`), and you'll
still see it in older projects — but with Poetry 2.x this is the correct form.

**`package-mode = false`.** `statusboard` is an application, not a library: nobody will ever run
`pip install statusboard`. This line tells Poetry "just manage the environment, there's nothing to
build". Without it, Poetry would look for a `statusboard/` package and demand a `src/` layout and a
build backend.

> If you're **writing a library** it's the other way around: drop `package-mode`, add a
> `[build-system]` section, and `poetry build` produces the `.whl` and `.tar.gz` you can push to PyPI
> with `poetry publish`. That's the headline difference from pip — Poetry can **package**, not just
> install.

**Dependency groups.** `ruff` is needed for development and **must not reach production**:

```bash
poetry install --only main      # without dev — this is how you deploy
poetry install --with dev       # with dev (installed by default anyway)
poetry install --only dev
```

There is no way to express this in `requirements.txt`. There you'd maintain a second file by hand and
watch forever that the two don't drift apart.

You can define your own groups:

```toml
[tool.poetry.group.docs]
optional = true

[tool.poetry.group.docs.dependencies]
mkdocs = "^1.6"
```

### 2. Adding a package to a specific group

```bash
poetry add requests                  # into [project] dependencies — a runtime dependency
poetry add --group dev pytest        # into the dev group
poetry add --group docs mkdocs       # into the docs group (created if missing)
poetry add --group typing mypy

poetry remove --group docs mkdocs    # remove from that specific group
```

The `--group` flag (short form `-G`) is the whole answer. Without it the package lands in the runtime
dependencies and ships to production.

> **Behaviour changed in Poetry 2.x.** A **new** group is now created in the standard
> `[dependency-groups]` section (PEP 735), not in Poetry's own `[tool.poetry.group.*]`. Verified on
> Poetry 2.4.1: `poetry add --group docs mkdocs` in an empty project produced
>
> ```toml
> [dependency-groups]
> docs = [
>     "mkdocs (>=1.6.1,<2.0.0)"
> ]
> ```
>


Installing and excluding groups:

```bash
poetry install                # main + every non-optional group
poetry install --with docs    # add an optional group
poetry install --without dev  # everything except dev
poetry install --only main    # runtime dependencies only — this is how you deploy
poetry install --only docs    # a single group
```

### 3. The extended example

This folder also contains [`pyproject.reference.toml`](pyproject.reference.toml) — a reference file
collecting nearly everything `pyproject.toml` can express, with commentary: `classifiers`, extras,
environment markers, private indexes, entry points, console scripts, multiple dependency groups,
build-backend choices, plus `[tool.ruff]`, `[tool.pytest.ini_options]`, `[tool.mypy]` and
`[tool.coverage]` sections and their uv equivalents.

It's a cheat sheet, not a template: a real manifest rarely contains a quarter of it. The file is valid
and can be checked:

```bash
mkdir -p /tmp/ref && cp pyproject.reference.toml /tmp/ref/pyproject.toml
cd /tmp/ref && touch README.md && poetry check
```

### 4. Creating a `pyproject.toml` from scratch

**Option 1: `poetry new` — a new project including the folder layout**

```bash
poetry new statusboard
```

Creates everything at once:

```
statusboard/
├── README.md
├── pyproject.toml
├── src/statusboard/__init__.py
└── tests/__init__.py
```

> In Poetry 2.x, `--src` is **already the default** and the flag itself is deprecated:
> `The --src option is now the default and will be removed in a future version.`
> To get the old flat layout without `src/`, use `--flat`.

The generated file:

```toml
[project]
name = "statusboard"
version = "0.1.0"
description = ""
authors = [{name = "Oleh Andrus", email = "..."}]
readme = "README.md"
requires-python = ">=3.12"
dependencies = []

[tool.poetry]
packages = [{include = "statusboard", from = "src"}]

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
```

Poetry takes the name and email from `git config user.name` and `user.email`.

**Option 2: `poetry init` — inside an existing folder**

This is what you want when the code already exists (our case):

```bash
cd module01/poetry_ex
poetry init
```

You get a prompt sequence: name, version, description, author, license, Python version, then two
questions about dependencies — runtime and dev. Any of them can be answered with an empty line and
filled in later with `poetry add`.

**Non-interactively** (for scripts and CI) — the `-n` flag plus parameters:

```bash
poetry init -n \
  --name statusboard \
  --description "Uptime board for public sites" \
  --author "Oleh <oleh@example.com>" \
  --python ">=3.12" \
  --dependency flask \
  --dependency requests \
  --dev-dependency ruff
```

Poetry looks up current versions and fills in the ranges itself:

```
Using version ^3.1.3 for flask
Using version ^2.34.2 for requests
```

Note that `poetry init` creates **neither** `src/`, `tests/`, nor a lock file. It writes only
`pyproject.toml`; the next `poetry install` installs the dependencies.

### 5. Migrating from `requirements.txt`

There is **no `poetry import` command** — unlike uv, where it's built in. It takes two steps:

```bash
# 1. create the manifest
poetry init -n --name statusboard --python ">=3.12"

# 2. feed it the whole list
poetry add $(cat requirements.txt)
```

If the file has comments — and it almost always does — you need `grep`:

```bash
poetry add $(grep -v '^#' requirements.txt)
```

**Why that's enough.** An unquoted `$(...)` substitution splits its output on spaces **and newlines**,
so `tr '\n' ' '` isn't needed. Blank lines produce no argument at all, so they need no separate
filtering. To see exactly what would be passed:

```bash
printf '  [%s]\n' $(grep -v '^#' requirements.txt)
```

```
  [Flask==3.1.0]
  [requests==2.32.3]
```

Without the `grep`, that same line yields `[#]`, `[web]`, `[framework]`, `[Flask==3.1.0]`… — every word
of the comment becomes its own "package name" and `poetry add` fails.

The `xargs` form does the same thing and reads more clearly to some people:

```bash
grep -v '^#' requirements.txt | xargs poetry add
```

> Neither form handles a **trailing** comment (`Flask==3.1.0  # web`). If you have those, the filter
> gets more involved: `sed 's/#.*//' requirements.txt`.

Verified on our file — this input:

```
Flask==3.1.0
requests==2.32.3
```

produces:

```toml
dependencies = [
    "flask (==3.1.0)",
    "requests (==2.32.3)"
]
```

plus an immediately generated `poetry.lock` with all 13 packages.

**The main migration trap.** Exact `==` pins **carry over as-is**. That was right for
`requirements.txt`; in `pyproject.toml` it almost never is. The division of labour in Poetry is
different:

| File | What it holds |
| --- | --- |
| `pyproject.toml` | **ranges** — the bounds within which you agree to be upgraded |
| `poetry.lock` | **exact versions** — what is actually installed |

Leave `==` in the manifest and you get double pinning: `poetry update` can't even pick up a security
patch, because the manifest forbids it. So after migrating, relax the ranges:

```bash
poetry add "flask@^3.1.0" "requests@^2.32.3"
```

The exact versions don't go anywhere — they stay in `poetry.lock`, which is where they belong.

**If you have a `requirements-dev.txt`,** it becomes a group:

```bash
poetry add --group dev $(grep -v '^#' requirements-dev.txt)
```

**Going back the other way.** Sometimes you need to hand a `requirements.txt` to somewhere Poetry
doesn't exist — AWS Lambda, old buildpacks, corporate build systems:

```bash
poetry self add poetry-plugin-export      # a separate plugin in Poetry 2.x
poetry export -f requirements.txt -o requirements.txt --without-hashes
poetry export -f requirements.txt -o requirements-dev.txt --only dev
```

Without `--without-hashes` the hashes from the lock file are included — which is actually better, since
`pip install --require-hashes` will then verify every archive.

### 6. Version syntax

| Spec | Means |
| --- | --- |
| `^1.2.3` | `>=1.2.3, <2.0.0` — caret, "don't break the major" |
| `^0.2.3` | `>=0.2.3, <0.3.0` — for `0.x`, the second digit counts as the major |
| `~1.2.3` | `>=1.2.3, <1.3.0` — tilde, patches only |
| `>=3.1.0,<4.0.0` | the same thing spelled out, PEP 508 |
| `*` | anything |

`^` is Poetry's default choice. It assumes everyone follows semantic versioning; in practice they
don't, which is exactly why the lock file exists.

### 7. `poetry.lock` — the heart of the lesson

`pyproject.toml` describes **what you asked for**. `poetry.lock` records **what you got**:

```bash
head -30 poetry.lock
grep -c '^\[\[package\]\]' poetry.lock   # 40 packages: 13 runtime + the dev toolchain
grep -c sha256 poetry.lock               # ~520 in this project
```

It contains:

- **the exact version of every package** — not just your two, but all thirteen including transitive
  ones (plus everything `ruff`, `pytest`, `bandit`, `pre-commit` and `mypy` pull into the `dev` group);
- **the SHA-256 of every file** that will be downloaded;
- `content-hash` — a fingerprint of `pyproject.toml` itself.

The hashes are the whole point of a lock file. On install, every downloaded archive is checked against
its hash. If PyPI were compromised, a mirror swapped a wheel, or a maintainer overwrote a release, the
install **fails** rather than quietly running someone else's code.

`content-hash` is what lets Poetry notice that `pyproject.toml` changed and `poetry.lock` didn't.

> **Commit the lock file to git. Always.**

**`install` vs `lock` vs `sync` vs `update`**

| Command | Reads | What it does |
| --- | --- | --- |
| `poetry install` | the lock (or the manifest, if there's no lock) | installs exactly what's in the lock |
| `poetry lock` | `pyproject.toml` | re-resolves and rewrites the lock, installing nothing |
| `poetry sync` | the lock | installs what's in the lock **and removes everything else** |
| `poetry update` | `pyproject.toml` | `lock` + `install`: pulls newer versions within your constraints |

`poetry sync` is the thing pip fundamentally lacks: it brings the environment **exactly** to the state
of the lock file, removing packages you once installed by hand and forgot about.

**Exercise: break the lock on purpose**

```bash
# 1. In pyproject.toml, change flask to (>=3.0.0,<4.0.0)
poetry check --lock
```

```
Error: pyproject.toml changed significantly since poetry.lock was last generated.
Run `poetry lock` to fix the lock file.
```

This is exactly the check to put in CI, so nobody deploys versions no one reviewed. Undo it with:

```bash
git checkout -- pyproject.toml poetry.lock
```

### 8. Dependency conflicts

You only see the resolver when it can't solve the problem. The [`conflict/`](conflict/) folder holds a
**separate mini-project** for exactly that — separate so that `statusboard`'s own `pyproject.toml` and
`poetry.lock` stay untouched. Inside:

```toml
dependencies = [
    "flask (==3.1.0)",
    "werkzeug (==2.3.0)",
]
```

Flask 3.1.0 declares `Werkzeug>=3.1` in its metadata while we demand exactly `2.3.0` alongside it. No
such set of versions exists.

Poetry is aimed at another project with `-C` (also spelled `--directory`), so you don't have to change
directory:

```bash
poetry -C conflict lock
```

```
Skipping virtualenv creation, as specified in config file.
Updating dependencies
Resolving dependencies...

Because conflict-demo depends on flask (3.1.0) which depends on Werkzeug (>=3.1), werkzeug is required.
So, because conflict-demo depends on werkzeug (2.3.0), version solving failed.
```

Exit code **1**, no `conflict/poetry.lock` is written, and your real lock file is unchanged — you can
confirm immediately: `poetry check --lock` in this folder still says `All set!`.

Read that error text carefully. It isn't "something went wrong", it's a **proof**, built from your
project down to the contradiction:

1. `conflict-demo` depends on `flask (3.1.0)`;
2. which depends on `Werkzeug (>=3.1)`;
3. therefore `werkzeug>=3.1` is required;
4. but `conflict-demo` requires `werkzeug (2.3.0)` → no solution.

Poetry (like uv) uses the **PubGrub** algorithm, and this ability to name the colliding pair of
constraints — rather than just saying "conflict" — is a direct consequence.

**The same file, but solvable.** Drop the version from Flask in `conflict/pyproject.toml`, leaving just
the name (that means "any version"; Poetry rejects `flask (*)` with `The requirement is invalid`):

```toml
dependencies = [
    "flask",
    "werkzeug (==2.3.0)",
]
```

```bash
poetry -C conflict lock
```

Now `poetry lock` succeeds and writes `conflict/poetry.lock`, containing `Flask 2.3.1`:

```bash
grep -A1 'name = "flask"' conflict/poetry.lock
# name = "flask"
# version = "2.3.1"
```

Poetry **backtracked** to the newest Flask that still accepts Werkzeug 2.3.0. That's resolution: not
"install the newest", but "find versions where every constraint holds at once". pip in
[`../pipenv_ex/`](../pipenv_ex/) and uv arrive at the same `Flask 2.3.1` from the same input.

Clean up:

```bash
rm -f conflict/poetry.lock && git checkout -- conflict/pyproject.toml
```

**How this differs from pip.** The important difference isn't the error text, it's **what cannot happen
here**. In pip, a sequential `pip install flask==3.1.0` followed by `pip install werkzeug==2.3.0`
leaves a broken environment and exits 0 (details in
[`../pipenv_ex/README.md`](../pipenv_ex/README.md)). Poetry has no such path: `poetry add` re-resolves
the **entire** graph first, and if there's no solution it changes neither the environment nor
`pyproject.toml`.

Try it on the solvable variant from the previous step (`flask` unpinned + `werkzeug (==2.3.0)`) —
attempt to add a conflicting pin:

```bash
poetry -C conflict add "flask==3.1.0"
```

```
Because flask (3.1.0) depends on Werkzeug (>=3.1)
 and conflict-demo depends on werkzeug (2.3.0), flask is forbidden.
So, because conflict-demo depends on flask (3.1.0), version solving failed.
```

Exit code 1 — and `conflict/pyproject.toml` is **unchanged**: no `flask==3.1.0` line appeared. Compare
that with pip, which in the same situation installs the package and reports the problem afterwards.

| | pip | Poetry |
| --- | --- | --- |
| Detect a conflict up front | `--dry-run` | yes, `poetry lock` |
| Name the exact pair of constraints | yes, briefly | yes, as a proof |
| Backtrack to an older version | yes | yes |
| Can break a working environment | **yes, and returns 0** | no |
| Find an already-broken environment | `pip check` | not needed — the lock file describes the state |

---

## Development tooling

The dev group holds five tools:

```toml
[tool.poetry.group.dev.dependencies]
ruff = "^0.14.0"
pytest = "^9.1.1"
bandit = "^1.9.4"
pre-commit = "^4.6.1"
mypy = "^1.18.0"
types-requests = "^2.33.0.20260712"
```

All of them are configured in the **same** `pyproject.toml` — `[tool.pytest.ini_options]`,
`[tool.bandit]`, `[tool.mypy]`, `[tool.ruff]`. In [`../pipenv_ex/`](../pipenv_ex/) that took three
separate files in three different formats (`pytest.ini`, `requirements-dev.txt`, `bandit.yaml`). This
is exactly why `setup.cfg`, `.flake8`, `mypy.ini` and the rest of the zoo are disappearing.


### pre-commit — running the checks automatically

`pre-commit` attaches checks to a git hook: they fire on `git commit`, and **only for the files you
staged**.

```bash
poetry run pre-commit install          # write the hook into .git/hooks (once)
poetry run pre-commit run --all-files  # run it now, across everything
poetry run pre-commit autoupdate       # bump the versions in rev:
poetry run pre-commit run ruff-check   # a single hook
```

Four hooks: `ruff-check` (finds problems and fixes them), `ruff-format` (formats), `bandit` (security),
`mypy` (types).


## Recreating the environment

With pip, the venv sits where you created it: `.venv/` in the project folder, and removing it is
`rm -rf`. With Poetry the venv is **a managed object, not a file in your project**, and its path
depends on configuration. So the first question is always: which environment am I actually using?

```bash
poetry env info          # full information about the current environment
poetry env info -p       # the path only (same as --path)
poetry env list          # every environment Poetry keeps for this project
```

> **A trap that can cost you half an hour.** `poetry env info` doesn't just report the path — it
> **creates** the environment if it doesn't exist. So does `poetry env activate`. Which means that
> after `poetry env remove --all`, simply asking `poetry env info --path` brings one back (empty, with
> just `pip` in it). Verified on Poetry 2.4.1. If you're wondering where an environment came from, it
> may well have been created by your own diagnostic command.

By default (`virtualenvs.in-project` unset) Poetry keeps environments **outside the project**, in its
own directory, named something like `statusboard-8SkKN7Wn-py3.12`:

```
~/Library/Caches/pypoetry/virtualenvs/     # macOS
~/.cache/pypoetry/virtualenvs/             # Linux
```

The hash in the name comes from the project's absolute path. Practical consequence: **move the project
folder and you get a new environment**, with the old one left hanging in the cache.

**The actual recreation:**

```bash
poetry env remove --all     # delete every environment for this project
poetry install              # build a new one from poetry.lock
```

`--all` matters here: if a project has accumulated several environments (different Python versions, a
moved path), `poetry install` may repair one you aren't looking at. To delete a specific one, use the
name from `poetry env list`:

```bash
poetry env remove statusboard-8SkKN7Wn-py3.12
```


## Command reference

| Command | What it does |
| --- | --- |
| `poetry new myproj` | create a new project |
| `poetry init` | create a `pyproject.toml` in an existing folder |
| `poetry install` | create the venv (if needed) and install dependencies |
| `poetry install --only main` | without dev groups — for production |
| `poetry sync` | bring the environment exactly to the lock, removing extras |
| `poetry add requests` | add a dependency and update the lock |
| `poetry add --group dev pytest` | add a dev dependency |
| `poetry remove requests` | remove a dependency |
| `poetry lock` | re-resolve the lock without installing |
| `poetry update` | update everything within the constraints |
| `poetry update flask` | update a single package |
| `poetry show` | list what's installed |
| `poetry show --tree` | the dependency tree |
| `poetry show --why urllib3` | who pulled this package in |
| `poetry check` | validate `pyproject.toml` |
| `poetry check --lock` | check whether the lock is stale |
| `poetry run <cmd>` | run a command inside the environment |
| `poetry env info` / `--path` | where the venv lives (**creates it** if absent) |
| `poetry env list` | every environment for this project |
| `poetry env use python3.13` | switch Python version |
| `poetry env activate` | print the activation command (`eval $(...)`) |
| `poetry env remove --all` | delete the project's environments |
| `poetry lock --regenerate` | re-resolve the lock from scratch |
| `poetry cache clear --all pypi` | clear the download cache |
| `poetry export -f requirements.txt` | generate a `requirements.txt` (needs the plugin) |
| `poetry build` | build a wheel and sdist (only without `package-mode = false`) |
| `poetry publish` | upload to PyPI |

The most useful one here is `poetry show --why urllib3`. That's the command you need at two in the
morning when a security scanner complains about a package you've never heard of and you need to know
who dragged it in.

---

## Common problems and how to fix them

| Symptom | Cause | Fix |
| --- | --- | --- |
| `poetry: command not found` | Poetry installed into a project venv, or not on `$PATH` | install it as a tool: `uv tool install poetry` or `pipx install poetry` |
| `pyproject.toml changed significantly since poetry.lock was last generated` | the manifest was edited, the lock wasn't | `poetry lock` |
| A package you removed is still installed | `poetry install` never deletes | `poetry sync` |
| An environment reappears after `poetry env remove --all` | `poetry env info` / `env activate` create one | check with `poetry env list` instead |
| Moving the project folder gave you a fresh, empty venv | the venv name hashes the absolute path | `poetry install`, or set `virtualenvs.in-project true` |
| bandit reports hundreds of findings in `.venv` | the `-c pyproject.toml` flag was omitted | always pass `-c pyproject.toml` |
| The mypy pre-commit hook can't see `flask` | pre-commit builds each hook its own venv | list packages in `additional_dependencies`, or run mypy in CI |
| `The requirement is invalid` on `flask (*)` | Poetry rejects that spelling | write just `flask` for "any version" |

---

## Takeaways

**What Poetry gives you over pip:**

1. **A lock file with hashes** — reproducibility and protection against a swapped package
2. **Direct and transitive dependencies kept apart** — two lines in `pyproject.toml`, all 40 packages in `poetry.lock`
3. **Dependency groups** — dev tooling never ships to production
4. **`poetry sync`** — the environment can be brought *to* the description, not merely topped up
5. **Build and publish** — `poetry build`, `poetry publish` (for libraries)
6. **The venv creates itself**

**What Poetry doesn't give you:**

- **Speed.** `poetry lock` on this tiny project takes about **1.9 seconds** with a warm cache. On a real
  project with dozens of dependencies that's tens of seconds, sometimes minutes.
- **Python version management** — you still need `pyenv` or `uv python` for that.