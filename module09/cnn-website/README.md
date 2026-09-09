# cnn-website

A news reader on [newsapi.org](https://newsapi.org/) with accounts: bcrypt
hashing, HS256 bearer tokens, and per-user likes, on async FastAPI over
Postgres. Every JSON endpoint needs a token.

```bash
cp .env.example .env                 # then put your NewsAPI key in it
docker compose up --build --wait     # -> http://localhost:8080
```

Full write-up — the topics this module covers, every endpoint, curl examples,
the configuration table, the schema and troubleshooting — is one level up in
[../README.md](../README.md). The topic list alone is in
[../AGENDA.md](../AGENDA.md).
