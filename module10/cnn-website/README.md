# cnn-website

An async FastAPI news reader on [newsapi.org](https://newsapi.org), with email
verification, a Redis cache, a rate-limit middleware, and a Celery worker and
beat sending a daily newsletter and an admin stats report.

```bash
cp .env.example .env                 # then set NEWS_API_KEY and SECRET_KEY
docker compose up --build --wait     # -> http://localhost:8010/docs
```

Full write-up — every feature, every endpoint, the commands to drive each one,
curl walkthroughs and the configuration table — is one level up in
[../README.md](../README.md). The topic list alone is in
[../AGENDA.md](../AGENDA.md).
