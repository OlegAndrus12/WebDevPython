# Load tests

One file, [locustfile.py](locustfile.py), pointing fifty simulated readers at
`GET /api/articles` and reporting what that does to its latency.

Locust is an open-source load-testing tool whose scenarios are plain Python:
subclass `HttpUser`, decorate a method with `@task`, and Locust runs many
copies of that class concurrently -- on gevent greenlets, not threads, so fifty
users cost one process -- timing every request. It ships a web UI with live
charts and a headless mode for scripts.

## The commands

`-u` is the peak user count (a ceiling, not a rate), `-r` how many are spawned
per second until it is reached, `-t` the total run time including that ramp.

```bash
# setup
uv sync --group load                        # locust itself
DEBUG=false docker compose up -d --wait     # `up -d`, NOT `restart`
export LOAD_EMAIL=you@example.com LOAD_PASSWORD=...   # a confirmed user, already in the db

L="uv run locust -f tests/load/locustfile.py"

# run
$L --headless -u 50 -r 10 -t 30s                   # scripted: run, print, exit
$L -u 50 -r 10 -t 30s                              # web UI on :8089, flags prefill the form
$L --autostart --autoquit 10 -u 50 -r 10 -t 30s    # run now, keep the UI, quit after
$L --headless -u 50 -r 10 -t 30s --html load.html  # ... and write a standalone report
$L --headless -u 50 -r 10 -t 30s --only-summary    # no periodic table mid-run
$L --headless -u 50 -r 10 -t 30s -P 9000           # web UI on another port
$L -l                                              # list the User classes and exit
locust --help                                      # everything else

# after
docker compose up -d api --wait             # back to the development settings
```

`DEBUG=false` goes on `docker compose`, never on `uv run locust`: it is the api
container's setting. With the toolbar on, or with `RATE_LIMIT_WINDOW_SECONDS`
above zero, the numbers are a lie.
