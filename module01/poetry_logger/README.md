# poetry_logger

The same `statusboard` as in [`../poetry_ex/`](../poetry_ex/), plus logging: for everything worth
knowing about Poetry itself, see that folder — this one only covers running the app and the
logger.

## Running

```bash
cd module01/poetry_logger

poetry install
poetry run flask --app app run --debug
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## How the logger works

All configuration lives in one file, [`logging_setup.py`](logging_setup.py). Its `configure()`
function attaches two handlers to the root logger:

- **`StreamHandler`** — writes to the console (stderr);
- **`FileHandler`** — writes to `statusboard.log` next to the code.

Both use the same format: `time level module: message`.

`configure()` is called once, from [`app.py`](app.py), at module import time. The other files
(`checks.py`, `services.py`, `incidents.py`) configure nothing themselves — they just grab
`logging.getLogger(__name__)` and log through it. That lets them still be used standalone (e.g.
from a cron script) without dragging file handlers along when they aren't needed.

If the root logger already has handlers, `configure()` does nothing — otherwise Flask's debug
reloader, which re-imports `app.py`, would attach a second pair of handlers and every line would
print twice.

### Where messages get logged

| Module         | What, and at what level                                                          |
| -------------- | ---------------------------------------------------------------------------------- |
| `app.py`       | `INFO` when a service is added/removed; `ERROR` (with traceback) when the Cloudflare API is unreachable |
| `checks.py`    | `WARNING` when a URL check fails or returns a code ≥400; `DEBUG` on success        |
| `services.py`  | `DEBUG` when reading a missing `services.json` and on every write                  |
| `incidents.py` | `DEBUG` before the Cloudflare request; `INFO` with how many incidents came back    |

### See it in action

```bash
poetry run flask --app app run --debug
tail -f statusboard.log     # in another terminal
```

Add a service with a broken URL through the form — a `WARNING` from `checks.py` shows up
immediately, both in the console and in `statusboard.log`.

`statusboard.log` is not committed (see the root [`.gitignore`](../../.gitignore), `*.log`) — it's
a runtime artifact of the local run.
