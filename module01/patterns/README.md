# Design patterns

Six patterns, one folder each. Where a folder holds two files they are the same problem solved twice —
`before.py`/`after.py`, or two idioms worth comparing side by side.

| Pattern | Folder | The example | Needs |
| --- | --- | --- | --- |
| **Adapter** | [`adapter/`](adapter/) | Three carrier APIs with three payload shapes, behind one `ShippingQuote` | — |
| **Observer** | [`observer/`](observer/) | An event source fanning log lines out to a console and a file | `rich` |
| **Proxy** | [`proxy/`](proxy/) | Rate limiting, then IP blocking as Django and WSGI middleware | see below |
| **Singleton** | [`singleton/`](singleton/) | App settings loaded from `.env` exactly once | Poetry |
| **State** | [`state/`](state/) | A character moving between idle, running and jumping | — |
| **Template Method** | [`template_method/`](template_method/) | An export routine with one overridable formatting step | — |

Everything except `observer/` and `singleton/` runs on the standard library:

```bash
cd module01/patterns
python3 adapter/after.py
```

---

## Adapter

[`before.py`](adapter/before.py) branches on carrier inside `get_quote` and unpacks each payload
inline — Nova Poshta returns a string price, DHL a float nested three levels down, Ukrposhta an integer
in kopiykas. [`after.py`](adapter/after.py) gives each carrier an adapter that returns a
`ShippingQuote`, so checkout sees one shape and adding a carrier touches nothing that already works.

> The pattern is the translation layer, not the class. What makes it an Adapter is that the third-party
> API stays untouched — you adapt to it rather than asking it to change.

## Observer

[`observer.py`](observer/observer.py) — `Event` keeps a list of subscribers and calls each one on
`notify`. The two subscribers show the two shapes a listener can take: `console_logger` is a plain
function, `FileLogger` is a class with `__call__`. The publisher knows neither.

`register`/`unregister` at the bottom demonstrate subscribing and unsubscribing at runtime — the
reason for the pattern. `logs.txt` is what `FileLogger` appends to; `pubsub.png` and `rabbitmq.png`
place the idea next to message brokers, which are this pattern across a network.

## Proxy

A proxy has **the same interface** as the thing it wraps, so the caller can't tell the difference — but
it may answer itself, alter the call, or refuse to pass it on.

| File | What it shows |
| --- | --- |
| [`proxy_concept.py`](proxy/proxy_concept.py) | The bare idea: `RateLimitProxy` allows five calls, then stops forwarding |
| [`proxy_django.py`](proxy/proxy_django.py) | The same protection proxy as Django middleware (illustrative — needs Django) |
| [`proxy_statusboard/`](proxy/proxy_statusboard/) | The real thing: WSGI middleware blocking IPs in front of a Flask app |

`proxy_statusboard/` is a self-contained project with its own `pyproject.toml`, `uv.lock` and README —
run it with `uv run python run.py` from inside that folder.

## Singleton

Two answers to "load configuration once". This folder is a Poetry project — `python-dotenv` is its one
dependency:

```bash
cd singleton
poetry install
poetry run python settings.py
poetry run python settings_minimal.py
```

[`settings_minimal.py`](singleton/settings_minimal.py) is the textbook version: override `__new__`,
cache the instance on the class. Note the flaw it inherits — `__init__` still runs on **every**
`Settings()` call, re-reading `.env` each time.

[`settings.py`](singleton/settings.py) is what you'd actually write: a frozen dataclass plus
`@lru_cache(maxsize=1)` on `get_settings()`. The caching lives in one decorator, the class stays an
ordinary immutable object, and tests can build one directly instead of fighting global state. It also
validates on load — no `SECRET_KEY` with `DEBUG` off is a hard error — and its `__repr__` masks the
secret. Running it prints the cache stats, which is the difference in one line:

```
CacheInfo(hits=1, misses=1, maxsize=1, currsize=1)
```

> In Python the module system is already a singleton: import a module twice and you get the same
> object. Reach for `lru_cache` or a module-level constant long before `__new__`.

## State

The same three-state machine written twice.

[`match.py`](state/match.py) keeps every transition in one `match` over `(state, event)` — compact, and
the whole machine is readable at a glance. [`classes.py`](state/classes.py) gives each state its own
class that returns the next state, so a state's behaviour lives with it and adding one touches no
existing branch.

Pick by what changes: the table when transitions are the churn, the classes when states carry their own
behaviour and data. For three states, `match.py` wins.

## Template Method

[`template_method.py`](template_method/template_method.py) — `export()` fixes the algorithm (loop,
format each user, write JSON) and leaves `format_user` as the hook. `UsersListViewAPI` overrides only
that hook.

The file carries its own warning: `# violates LP`. The subclass changes the *shape* of what
`format_user` returns — `{name, shirt_size}` instead of `{name, experience, salary}` — so any caller
relying on the base's contract breaks. A hook may vary **how** a step is done; changing what it
produces is a Liskov violation, and the [`../solid/L/`](../solid/L/) examples cover exactly that.
