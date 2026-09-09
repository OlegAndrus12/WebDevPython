# cnn-website

A news reader on [newsapi.org](https://newsapi.org/): Flask for the web layer,
SQLAlchemy 2.0 for the data layer, Alembic for the schema, Postgres in Compose.

```bash
cp .env.example .env                 # then put your NewsAPI key in it
docker compose up --build --wait     # -> http://localhost:8080
```

Full write-up — the topics this module covers, every endpoint, curl examples,
the configuration table, the schema and troubleshooting — is one level up in
[../README.md](../README.md). The topic list alone is in
[../AGENDA.md](../AGENDA.md).
