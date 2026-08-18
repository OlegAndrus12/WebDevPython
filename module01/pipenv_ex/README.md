# pip and requirements.txt — dependency management in Python

## What this project is

**`statusboard`** is a small Flask web app that monitors service availability. It:

- **Checks HTTP availability** of several sites (Cloudflare, GitHub, PyPI and others)
- **Measures response time** (latency) and renders a status table with colour indicators
- **Pulls Cloudflare incidents** from a public API and shows them on a second tab
- **Lets you add and remove** services through the web UI, storing them in JSON

The app is deliberately small (~150 lines of Python) so that all the attention stays on **how dependencies are organised**, not on Flask.

## What pip and requirements.txt are

**`pip`** is Python's package manager: it installs libraries from PyPI (the Python Package Index). It is the first tool most people learn, and also the one with the fewest guardrails.

**`requirements.txt`** is a plain text file where each line is one dependency:
```
Flask==3.1.0
requests==2.32.3
```

**`venv`** (virtual environment) is an isolated Python environment for a project — a folder holding an interpreter and its own packages. It's what lets two projects on the same machine depend on incompatible versions of the same library.

### Where pip falls short

   - 🔴 No lock file with hashes (a release could be swapped out under you)
   - 🔴 No distinction between dev and runtime dependencies (here that's solved by hand, with two files)
   - 🔴 `pip install -r req.txt` never removes anything (the only real cleanup is recreating the venv)
   - 🔴 Successive `pip install` calls can break the environment and still exit 0 — `pip check` is what catches it
   - 🔴 Dependency conflicts — how to spot them (`--dry-run`) and how resolution settles them


## How to run the project

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

Then open http://127.0.0.1:5000

### What you'll see

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser.

On the **Status board**:
- ✅ **5 green** services (Cloudflare, GitHub, PyPI, Instagram and others) — reachable
- 🔴 **1 red** (`no-such-host.invalid`) — **broken on purpose**, so you can see what a failure looks like

On the **Cloudflare incidents** tab:
- The 50 most recent incidents on Cloudflare's services, roughly the last three weeks
- Fetched from a public API, no authentication required

### Leaving the project

```bash
# Leave the virtual environment
deactivate

# Back to your main Python
which python              # now the system Python
```


## Project structure

| File | Role |
| --- | --- |
| **`app.py`** | Flask app: routes `GET /`, `GET /incidents`, `POST /services`, `POST /services/delete` |
| **`checks.py`** | standalone module: probes a URL, measures latency, returns a result dict. Imports `requests`, but **not** Flask |
| **`services.py`** | manages the watch list: reads and writes JSON, no database |
| **`services.json`** | the list itself (name → URL). Created on the first add |
| **`incidents.py`** | fetches incidents from Cloudflare's public API, parses ISO dates, sorts them |
| **`requirements.txt`** | the project's three direct dependencies (Flask, requests, colorama) |
| **`requirements-dev.txt`** | development dependencies (pytest, bandit, ruff) — for when you extend the project |
| **`requirements-conflict.txt`** | demo file: deliberately incompatible Flask and Werkzeug versions |
| **`templates/base.html`** | page skeleton: `<head>`, header, tabs, footer |
| **`templates/index.html`** | the status board: service table plus the add form |
| **`templates/incidents.html`** | the Cloudflare incidents page, including the error state when the API is unreachable |
| **`static/style.css`** | all the CSS: light and dark themes, responsive layout, the full palette |

## Key concepts

### 1. The virtual environment (venv)

Run this **before** and **after** activating:

```bash
which python && which pip     # Windows: where python
```

Before activation you get the system Python; after, `.venv/bin/python`. Activation isn't magic:
it prepends `.venv/bin` to `$PATH` and sets `$VIRTUAL_ENV`. That's essentially the whole mechanism.

And here's the payoff it buys you:

```bash
python -c "import sys; print(sys.prefix)"
python -c "import flask, pathlib; print(pathlib.Path(flask.__file__).parent)"
```

Flask lives in `.venv/lib/python3.x/site-packages/`, not in the system Python. That's why two projects
on one machine can depend on **incompatible versions** of the same library without interfering.

Install without a venv and `pip install flask` drops the package into the system interpreter — after which
you can't upgrade one project without breaking another. On recent macOS and Debian, pip simply refuses:

```
error: externally-managed-environment
```

That's not a bug, it's pip telling you to make a venv.

> **The key point:** a venv can be deleted and recreated at any time — nothing valuable lives there.
> That's exactly why `.venv/` is in `.gitignore` and `requirements.txt` isn't.

---

### 2. pip commands

```bash
pip list                    # what's installed
pip show flask              # version, dependencies, path
pip show -f flask           # ...plus every file the package put on disk
pip list --outdated         # what has newer versions available
pip index versions flask    # every version available on PyPI
```

Look at the `Requires:` line in `pip show flask` — `blinker`, `click`, `itsdangerous`,
`jinja2`, `markupsafe`, `werkzeug`. You asked for **one** package and got **seven**. Now look from the
other direction: `pip show werkzeug` and its `Required-by:` line.

### Reference

| Command | What it does |
| --- | --- |
| `python3 -m venv .venv` | create a virtual environment |
| `source .venv/bin/activate` | activate it (Windows: `.venv\Scripts\activate`) |
| `deactivate` | leave it |
| `pip install flask` | install a package |
| `pip install 'flask==3.1.0'` | install a specific version |
| `pip install -r requirements.txt` | install everything in the list |
| `pip install -U flask` | upgrade |
| `pip uninstall flask` | remove it (its dependencies **stay behind**) |
| `pip freeze` | print the full list of what's installed |
| `pip check` | verify that dependencies aren't broken |
| `pip cache purge` | clear the wheel cache |
| `python -m pip ...` | the safe form — it makes the target interpreter unambiguous |

That last line is worth making a habit. With several Pythons on a machine, `pip` is whichever one turned
up first in `$PATH`; `python -m pip` is unmistakably the one you just invoked.

---

### 3. Two files, two jobs — `requirements.txt` vs `pip freeze`

You asked for two packages. Look at what actually got installed:

```bash
pip list
```

About a dozen, because dependencies have dependencies of their own. Now generate the file automatically:

```bash
pip freeze
```

```
blinker==1.9.0
certifi==2026.7.22
charset-normalizer==3.4.9
click==8.4.2
Flask==3.1.0
idna==3.18
itsdangerous==2.2.0
Jinja2==3.1.6
MarkupSafe==3.0.3
requests==2.32.3
urllib3==2.7.0
Werkzeug==3.1.8
```

Your version numbers will differ — and that's precisely the point: the two lines you pinned are fixed,
while the other ten were handed to you as whatever PyPI happened to be serving on install day.

Compare that with `requirements.txt` and its **two lines**. Both files produce the same environment today.
But they are not the same thing:

- **`pip freeze` is complete, but flat.** Nothing in it shows which two packages you chose deliberately and
  which arrived as baggage. A year later, no reviewer can tell whether `urllib3` is imported by your code or
  was dragged in by `requests` — so nobody dares remove it.
- **A hand-written file expresses intent.** Two lines, two decisions. But it pins no transitive packages at
  all, so `pip install -r requirements.txt` on a different day gives you a different `urllib3`.

**Neither file can do both jobs at once.** That's not a matter of taste, it's a missing capability. It's
exactly the gap Poetry and uv close: a manifest of your direct dependencies **plus** a separate lock file
that pins all twelve, hashes included.

### Ways to pin a version

| Spec | Means | When |
| --- | --- | --- |
| `Flask==3.1.0` | exactly this version | applications — you need reproducibility |
| `Flask>=3.1` | this or newer | libraries — you don't know the consumer's constraints |
| `Flask~=3.1.0` | `>=3.1.0, <3.2.0` | you trust patch releases but not minor ones |
| `Flask` | anything | never in something you deploy |

Here it's `==`, because `statusboard` is an application.

---

### 4. What pip can't do

Every item here is the subject of a later lesson.

1. **No lock file and no hashes.** pip installs whatever PyPI hands over. If a release were swapped out,
   the install would succeed silently. `pip install --require-hashes` exists, but you maintain the hashes by hand.
2. **No distinction between direct and transitive dependencies.** Covered above — this is the big one.
3. **No dependency groups.** Add `pytest` and you either ship test tooling to production or maintain a second
   `requirements-dev.txt` by hand, forever watching that the two don't drift apart.
4. **`pip install -r` never removes anything.** Delete a line from the file, run it again — the package stays installed.
5. **It doesn't build or publish your project.** These are just files in a folder; there's nothing you could
   install with `pip install statusboard`.

Point 4 takes fifteen seconds to verify and usually surprises people:

```bash
pip install rich
pip install -r requirements.txt     # rich isn't in the file
pip list | grep -i rich             # still there
```

`poetry sync` and `uv sync` would remove it (in Poetry 2.x it's a separate command; the old
`poetry install --sync` is deprecated). pip has no equivalent — short of deleting the venv and rebuilding it,
which, honestly, is a perfectly reasonable habit.

---

### 5. Dependency conflicts — finding them and resolving them

So far we've installed packages that get along. Now let's see what happens when they don't — and why this is
most dangerous in pip specifically.

The folder contains a separate file, [`requirements-conflict.txt`](requirements-conflict.txt). **It doesn't
touch the real `requirements.txt`** — pip reads only the file you name. Two lines inside:

```
flask==3.1.0
werkzeug==2.3.0
```

Flask 3.1.0 declares `Requires-Dist: Werkzeug>=3.1` in its metadata, while we're demanding exactly `2.3.0`
alongside it. No such combination exists. You can see the constraint for yourself — it lives in the wheel's
`METADATA` (`pip show flask` prints only dependency **names**, without versions):

```bash
pip download flask==3.1.0 --no-deps -d /tmp/fl
unzip -p /tmp/fl/flask-3.1.0-*.whl '*/METADATA' | grep Requires-Dist
# Requires-Dist: Werkzeug>=3.1
```

### Step 1. Ask pip to solve it

`--dry-run` means "work it out but install nothing" — your venv stays untouched:

```bash
pip install --dry-run -r requirements-conflict.txt
```

```
INFO: pip is looking at multiple versions of flask to determine which version is compatible...
ERROR: Cannot install -r requirements-conflict.txt (line 17) and werkzeug==2.3.0 because these
       package versions have conflicting dependencies.

The conflict is caused by:
    The user requested werkzeug==2.3.0
    flask 3.1.0 depends on Werkzeug>=3.1

ERROR: ResolutionImpossible
```

The exit code is **1**. This is normal, healthy behaviour: pip did the maths and declined.

### Step 2. The same thing, but solvable

Comment out `flask==3.1.0` and uncomment the bare `flask` line — now the same file becomes solvable. The
resolver **backtracks** and installs `Flask 2.3.1`, the newest release that still accepts `Werkzeug 2.3.0`:

```bash
pip install --dry-run -r requirements-conflict.txt | grep -i "Would install"
# Would install ... Flask-2.3.1 ... Werkzeug-2.3.0 ...
```

That is dependency resolution: not "take the newest", but **find a set of versions that satisfies every
constraint simultaneously**. Poetry and uv in [`../03_poetry/`](../03_poetry/) and [`../04_uv/`](../04_uv/)
do the same thing with this file and arrive at the same `Flask 2.3.1` — they differ only in speed and in the
wording of the error.

### Step 3. The real problem: pip can break an environment that already works

This is what neither Poetry nor uv will do. pip installs packages **one at a time** and **doesn't check what's
already there**. So the conflict that was an honest error in step 1 here simply happens:

```bash
python3 -m venv /tmp/broken-venv        # a separate venv; we leave ours alone
/tmp/broken-venv/bin/pip install flask==3.1.0
/tmp/broken-venv/bin/pip install werkzeug==2.3.0
```

The second command prints `ERROR` — and **exits with code 0**:

```
ERROR: pip's dependency resolver does not currently take into account all the packages that are
installed. This behaviour is the source of the following dependency conflicts.
flask 3.1.0 requires Werkzeug>=3.1, but you have werkzeug 2.3.0 which is incompatible.
```

The word `ERROR`, a success code, a broken environment. A CI script checking `if pip install; then` treats
this step as a pass.

How broken isn't obvious right away, and that's the worst part. See for yourself with
[`conflict_demo.py`](conflict_demo.py): it builds a Flask app with a single route that touches the session
(that is, a signed cookie — the thing every login form relies on).

```bash
/tmp/broken-venv/bin/pip install -q flask==3.1.0 werkzeug==2.3.0   # skip if you already did this above
/tmp/broken-venv/bin/python conflict_demo.py
```

```
flask     3.1.0
werkzeug  2.3.0

The session route raised:
...
    self.session_interface.save_session(self, ctx.session, response)
TypeError: Response.set_cookie() got an unexpected keyword argument 'partitioned'
```

Notice **what still works** in this broken environment: `import flask` succeeds, the app starts, an ordinary
route returns 200. Only the code path that uses the newer Werkzeug API breaks. Deploy this to production and
what fails isn't the build — it's your users' logins.

The same script in a healthy environment (where pip picked `Flask 2.3.1` itself in step 2) prints
`GET /login -> 200` and exits 0.

### What to take away

| | pip |
| --- | --- |
| Detect a conflict up front | yes, `--dry-run` (exit code 1) |
| Backtrack to an older version | yes, the resolver has done this since 2020 (pip 20.3) |
| Protect what's already installed | **no** — successive `pip install` calls break the environment and return 0 |
| Find an already-broken environment | `pip check` (exit code 1) — but you have to **remember to run it** |

`pip check` is something worth adding to CI today:

```bash
/tmp/broken-venv/bin/pip check
# flask 3.1.0 has requirement Werkzeug>=3.1, but you have werkzeug 2.3.0.
```

Poetry and uv avoid this problem by construction: they don't "add a package", they **recompute the whole
environment from the lock file**, so an inconsistent state simply can't occur. You can see how that looks in
[`../03_poetry/`](../03_poetry/README.md) and [`../04_uv/`](../04_uv/README.md).

Clean up afterwards:

```bash
rm -rf /tmp/broken-venv
```

---

## Application architecture

### Routes

| Method and path | Function | Purpose |
| --- | --- | --- |
| `GET /` | `board` | the status table |
| `GET /incidents` | `incidents_page` | Cloudflare incidents |
| `POST /services` | `add_service` | add a service from the form |
| `POST /services/delete` | `delete_service` | remove a service |

Two important things are visible right here.

**Deletion is a POST, not a link.** By spec, GET must be *safe* and repeatable: browsers prefetch, crawlers
follow links, the back button replays requests. A `GET /services/delete?name=AWS` link will eventually delete
rows nobody asked to delete. Anything that changes server state goes through POST.

**Post/Redirect/Get.** Both POSTs answer with a redirect to `/` rather than HTML. Without it the address bar
would still point at a POST, and reloading the page (or the 30-second auto-refresh) would resubmit the form
and add the service twice.

### Templates and static files

Flask looks for two folders next to `app.py` — by convention, with no configuration at all:

- **`templates/`** — Jinja templates rendered on every request. Values get substituted, `{% if %}` and
  `{% for %}` work, and all data is **escaped automatically** (XSS protection).
- **`static/`** — files handed to the browser as-is. No rendering, no Python. The URL `/static/style.css`
  maps straight onto the file on disk.

Styles are linked through `url_for`, not a hard-coded path:

```html
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
```

`url_for` asks Flask to build the URL. Same story in the forms' `action` attributes: they name the **handler
function** (`url_for('add_service')`), not the path. Rename a route and everything still works.

### Template inheritance

`base.html` is the shared skeleton: `<head>`, header, tabs, footer. Both pages do
`{% extends "base.html" %}` and fill in blocks:

| Block | What it's for |
| --- | --- |
| `title` | the page `<title>` |
| `heading`, `subtitle` | heading and subheading |
| `refresh` | **empty by default** |
| `content` | the page body |
| `footer` | the footer |

`refresh` is the interesting one. Only the status board needs auto-refresh, so
`<meta http-equiv="refresh" content="30">` lives in `index.html`, not in the skeleton. Had the tag sat in
`base.html`, the incidents page would hammer someone else's API twice a minute for data that changes about
once a week.

### Auto-refresh without JavaScript

```html
<meta http-equiv="refresh" content="30">
```

This is a browser capability, not page code. The browser sets its own timer and issues a fresh `GET /` after
30 seconds, exactly as if you'd hit reload. There is **not a single line of JavaScript** on the page.

Things worth knowing before using this "for real":

- it's a **full reload**, so scroll position and keyboard focus reset (and half-typed form text disappears);
- WCAG 2.2.1 treats this as an accessibility problem when the refresh can't be paused;
- every 30 seconds means six outbound requests **per open tab**.

### Service checks run sequentially

`check_all` is an ordinary loop:

```python
return [check(name, url, timeout) for name, url in services.items()]
```

So the page takes roughly the sum of all the checks to load (~1.4 s for six services). For six that's fine,
and simplicity beats speed. Past about twenty it isn't, and that's where threads or `asyncio` come in
(module 04).

### Error handling in `checks.py`

Any network error is caught and turned into a **table row**, not an exception:

```python
except requests.RequestException as err:
    return {..., "error": type(err).__name__, "ok": False}
```

The reasoning is simple: a status page that crashes when a monitored site goes down crashes at precisely the
moment it was built for.

One more detail: `requests.get` **follows redirects by default**. That's why Instagram, which bounces
anonymous visitors to a login page, still reports 200.

> **Important:** both branches of `check()` return **the same set of keys**; on failure `status` and
> `latency_ms` are simply `None`. A dict whose shape depends on which branch produced it is a `KeyError`
> three files away.

### `services.py` — JSON instead of a database

```python
SERVICES_FILE = Path(__file__).parent / "services.json"
```

The path is anchored to **the source file**, not the working directory. `flask run` can be launched from
anywhere, and a plain `Path("services.json")` would look wherever the terminal happens to be. The bug is
insidious because it works perfectly — right up until the day someone starts the app from another folder.

Limits of this "storage" worth stating out loud:

- two concurrent writes → both read the file, both modify their own copy, and whoever writes second wins.
  The first edit vanishes with no error at all. Flask's dev server is multi-threaded, so this is a real race,
  not a theoretical one;
- the whole file is rewritten on every change;
- there's no schema — nothing stops you typing a number where a URL belongs.

For six services that's acceptable; for six thousand it isn't. Hence SQLite and SQLAlchemy in module 05.

---

## Cloudflare API integration

Cloudflare's status page runs on **Atlassian Statuspage**, which exposes a public JSON API — no key,
no authentication:

```
https://www.cloudflarestatus.com/api/v2/incidents.json
```

You can check it straight from the terminal:

```bash
curl -s https://www.cloudflarestatus.com/api/v2/incidents.json | python3 -m json.tool | head -40
```

Worth knowing:

- it returns the **50 most recent** incidents, and that's a hard limit. The `?page`, `?per_page` and
  `?limit` parameters are accepted and **silently ignored**;
