# cnn-website

A news reader on [newsapi.org](https://newsapi.org/) with a full REST surface: a
readers resource with `POST`/`PATCH`/`DELETE` and a likes join table, on async
FastAPI over Postgres. Nothing authenticates — the reader is named in the URL.

```bash
cp .env.example .env                 # then put your NewsAPI key in it
docker compose up --build --wait     # -> http://localhost:8080
```

Full write-up — the topics this module covers, every endpoint, curl examples,
the configuration table, the schema and troubleshooting — is one level up in
[../README.md](../README.md). The topic list alone is in
[../AGENDA.md](../AGENDA.md).
