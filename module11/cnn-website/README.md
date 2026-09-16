# cnn-website

[module10](../../module10/)'s news reader — email verification, a Redis cache,
a rate-limit middleware, Celery worker and beat — with three test suites around
it: pytest in-process, Selenium in a real browser, and Locust under load.

```bash
cp .env.example .env                 # then set NEWS_API_KEY and SECRET_KEY
docker compose up --build --wait     # -> http://localhost:8011/docs

uv run pytest                        # the in-process suite -- needs none of the above
```

Full write-up — every feature, every endpoint, all three suites and the
commands to run them — is one level up in [../README.md](../README.md). The
tests have their own reference in [tests/README.md](tests/README.md), the four
levels are explained in [../testing-levels.html](../testing-levels.html), and
the topic list is in [../AGENDA.md](../AGENDA.md).
