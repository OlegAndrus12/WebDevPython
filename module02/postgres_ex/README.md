# postgres_ex — Compose without a build

The only example in the module with **no `Dockerfile` at all**. Both services are stock
images configured purely through environment variables, which is the common case for
infrastructure: you do not build Postgres, you run it.

| Service | Image | URL | Credentials |
| --- | --- | --- | --- |
| `db` | `postgres:15` | `localhost:5432` | `admin` / `admin`, database `users` |
| `pgadmin` | `dpage/pgadmin4` | <http://localhost:5050> | `admin@gmail.com` / `admin` |

The walkthrough is **Part 5** of [../README.md](../README.md).

## Run it

```bash
cd module02/postgres_ex

docker compose up -d
docker compose ps
```

There is no `--build` because there is nothing to build — Compose pulls both images and
starts them. Give Postgres a few seconds on first run: it initialises the data directory
before it accepts connections.

## Without Compose — the same thing by hand

```bash
docker network create pg-net
docker volume create postgres_data

docker run -d --name postrgres_server --network pg-net -p 5432:5432 \
  -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=users \
  -v postgres_data:/var/lib/postgresql/data postgres:15

docker run -d --name pgadmin_ui --network pg-net -p 5050:80 \
  -e PGADMIN_DEFAULT_EMAIL=admin@gmail.com -e PGADMIN_DEFAULT_PASSWORD=admin \
  dpage/pgadmin4
```

Note there is no `docker build` in either version — that is the whole point of this
example. Tear it down:

```bash
docker rm -f postrgres_server pgadmin_ui
docker network rm pg-net
docker volume rm postgres_data          # deletes the data
```

## Connect from the host

```bash
docker compose exec db psql -U admin -d users -c '\l'

# or with a local client
psql postgresql://admin:admin@localhost:5432/users
```

## Some SQL to try

Open an interactive session against the `users` database:

```bash
docker compose exec db psql -U admin -d users
```

Create a table:

```sql
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

Add a user:

```sql
INSERT INTO users (name, email) VALUES ('Ada Lovelace', 'ada@example.com');
```

Get all users:

```sql
SELECT * FROM users;
```

```text
 id |     name     |      email      |          created_at
----+--------------+-----------------+-------------------------------
  1 | Ada Lovelace | ada@example.com | 2024-01-01 12:00:00.000000+00
(1 row)
```

Quit with `\q`. A few other useful psql commands: `\l` lists databases, `\dt` lists tables,
`\d users` describes the table.

The same statements as one-liners, no interactive session needed:

```bash
docker compose exec db psql -U admin -d users -c \
  "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, created_at TIMESTAMPTZ NOT NULL DEFAULT now());"

docker compose exec db psql -U admin -d users -c \
  "INSERT INTO users (name, email) VALUES ('Ada Lovelace', 'ada@example.com');"

docker compose exec db psql -U admin -d users -c "SELECT * FROM users;"
```

Because `/var/lib/postgresql/data` is a named volume, this table is still there after
`docker compose down && docker compose up -d` — see [Persistence](#persistence) below.

## Connect from pgAdmin — the network lesson, one more time

Open <http://localhost:5050>, log in with `admin@gmail.com` / `admin`, then
*Add New Server*:

| Field | Value |
| --- | --- |
| Host | **`db`** — not `localhost` |
| Port | **`5432`** — the container port, not the published one |
| Username / Password | `admin` / `admin` |

`localhost` would be the pgAdmin container itself. pgAdmin sits inside the compose network,
so it addresses Postgres by service name — identical to `DB_HOST=mongo` in
[../flask-node/](../flask-node/).

Note `container_name: postrgres_server` (typo in the original, kept as-is): that name is
what `docker ps` shows, but `db` is the DNS name other services use.

## Persistence

`postgres_data:/var/lib/postgresql/data` is a named volume, so tables survive restarts:

```bash
docker compose down       # data kept
docker compose down -v    # data destroyed
```

pgAdmin has *no* volume here, so its server registrations are lost on `down`. Adding one is
a good exercise.

## If port 5432 is taken

Something else already owns it (a local Postgres, usually). Change the **left** side only:

```yaml
ports:
  - "5433:5432"
```

The container port is fixed by the software; the host port is yours to choose.

> These credentials are committed deliberately — they are throwaway teaching values. Real
> projects keep them out of the repo (`.env` + `env_file:`, or a secret manager).
