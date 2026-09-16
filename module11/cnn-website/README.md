# cnn-website

[module10](../../module10/)'s news reader — email verification, a Redis cache,
a rate-limit middleware, Celery worker and beat — with three test suites around
it: pytest in-process, Selenium in a real browser, and Locust under load.

```bash
cp .env.example .env                 # then set NEWS_API_KEY and SECRET_KEY
docker compose up --build --wait     # -> http://localhost:8011/docs

uv run pytest                        # the in-process suite -- needs none of the above
```

The three suites and the commands to run them are one level up in
[../README.md](../README.md); [tests/README.md](tests/README.md) is the full test
reference, and [../testing-levels.html](../testing-levels.html) explains the four
levels. The application itself is identical to module10 and documented in
[../../module10/README.md](../../module10/README.md) — only the ports differ.
Topic list: [../AGENDA.md](../AGENDA.md).
