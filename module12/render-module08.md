# Deploying module08 to Render

Step by step, from this repo to a public URL. module08's Dockerfile already
builds a production image; the only thing it gains for this is a one-file start
script, because of [what Render's Docker Command can and cannot
do](#the-docker-command-is-not-a-shell).

Written for someone who has the repo on GitHub and a Render account.

---

## Can it be done? Yes — with two caveats worth reading first

**1. The free Postgres instance expires after 30 days.** Render deletes it 14
days after that unless you upgrade. It is also capped at 1 GB with no backups
and no connection pooling. Fine for a demo, not for anything you care about.

**2. NewsAPI's free plan forbids exactly this.** The Developer plan "may be used
for development and testing in a development environment only, and cannot be
used in a staging or production environment". A deployed Render service is a
production environment by that wording, and NewsAPI also rate-limits by IP —
cloud provider addresses often get refused outright.

That second one matters less than it sounds, because of how module08 is built:
**only `GET /` calls NewsAPI.** Every other route — the whole JSON API, the
article pages, readers, likes — reads Postgres. So the honest way to run this
deployment is:

- seed the database **from your laptop**, where NewsAPI's terms and its
  localhost CORS rule are both satisfied ([step 6](#6-seed-the-database)), and
- accept that `/` on the deployed service may show its error banner.

Everything else works exactly as it does locally.

Other free-tier behaviour to expect: the web service **spins down after 15
minutes of inactivity** and takes about a minute to wake on the next request.
Workspaces get 750 free instance hours a month.

---

## What Render needs that Compose was doing for you

| Locally (`docker-compose.yaml`) | On Render |
| --- | --- |
| `db` service, reachable as `db:5432` | a managed Postgres instance |
| `pgadmin` service | nothing — connect with `psql` instead |
| `command:` runs `alembic upgrade head` before uvicorn | `render-start.sh` does the same — see below |
| app listens on a fixed `8000` | must bind `0.0.0.0:$PORT` |
| `env_file: .env` | environment variables set in the dashboard |

### The Docker Command is not a shell

Render **does not run the Docker Command through a shell.** It splits the field
into arguments itself, substitutes environment variables, and execs the result
directly. So the command must be **one executable plus its arguments**. No `&&`,
no `;`, no pipes, no quotes.

That rules out the obvious `alembic upgrade head && uvicorn …` one-liner, in
both of its spellings — each fails a different way, and both are in
[troubleshooting](#troubleshooting). Render's own Docker docs suggest wrapping
multiple commands in `/bin/sh -c "…"`; for this field that does not work,
because the quotes are passed through literally.

Render's [Pre-Deploy Command](https://render.com/docs/deploys) is the usual home
for migrations, but it is not available on the Free plan. So the migration goes
where it belongs anyway: in the image, as part of starting up.

---

## 1. The start script

[`module08/cnn-website/render-start.sh`](../module08/cnn-website/render-start.sh)
is the one executable that does both things:

```sh
#!/bin/sh
set -e
alembic upgrade head
exec uvicorn news:app --host 0.0.0.0 --port "${PORT:-8000}"
```

- `set -e` makes the migration a **gate**. If `alembic upgrade head` fails the
  container exits non-zero and never serves, instead of answering requests
  against the wrong schema. Render marks the deploy failed and keeps the
  previous version live.
- `exec` replaces the shell with uvicorn, so uvicorn is PID 1 and still receives
  `SIGTERM` when Render shuts the instance down. Without it, signals stop at the
  shell and the instance is killed rather than drained.
- `${PORT:-8000}` takes Render's port and falls back to the local default, so
  the same script works in both places.

It runs on every start, including every wake from spin-down. That is fine:
`alembic upgrade head` on an up-to-date database is a no-op.

> **Why not run migrations from your laptop instead?** You can —
> `DB_HOST=<external-host> … uv run alembic upgrade head` works, and needs no
> new file. But it puts production credentials on a dev machine, makes the
> deploy depend on a human remembering a step, and lets the schema drift from
> the code that was pushed. It is a reasonable escape hatch, not a way to run
> something.

```bash
git add module08/cnn-website/render-start.sh
git commit -m "module08: start script for Render"
git push origin main
```

Render deploys from a connected repo. The whole monorepo goes up; you point the
service at one subdirectory in step 3.

---

## 2. Create the Postgres instance

Dashboard → **New** → **Postgres**.

| Field | Value |
| --- | --- |
| Name | `cnn08-db` |
| Database | `cnn` |
| User | `admin` |
| Region | pick one, and **remember it** |
| Instance Type | Free |

The region matters: a web service can only reach a database over the private
network if both are in the **same region and account**. Getting this wrong is
the most common way this deploy fails.

When it finishes provisioning, open its **Info** page. You will need both sets
of connection details — internal for the service, external for your laptop.

### Internal vs external hostname

Render gives the same instance two names, and picking the wrong one is the
other common way this deploy fails:

```
internal   dpg-d1abc2defg3h4ijk5lmn-a
external   dpg-d1abc2defg3h4ijk5lmn-a.oregon-postgres.render.com
```

The **internal** one is a short single-label name — no dots, no domain. It
resolves only on Render's private network, through their internal DNS, and only
for services in the same region and account. It is the one `DB_HOST` wants: the
traffic never leaves Render, so it is faster and not exposed.

The **external** one is that same name plus a region suffix, resolvable from
anywhere. Your laptop cannot resolve the internal name at all, which is why
step 6 uses the external one.

You can skip transcribing the internal details by using the
[Blueprint](#optional-a-renderyaml-blueprint-instead) — `fromDatabase` fills
`DB_HOST` and the rest from the instance Render creates.

### The password

Render generates it; you do not choose one. It is in the **Credentials** section
of the same Info page, and it is embedded in the connection URLs shown there:

```
postgresql://admin:THIS_PART@dpg-d1abc2defg3h4ijk5lmn-a/cnn
```

There is no "reset password" button. Render rotates by *user*: create a new one
(it becomes the default), update services, redeploy, then delete the old user —
a zero-downtime rotation. Blueprint-managed variables re-sync automatically;
hand-entered ones you update yourself.

> **Do not paste it into `module08/cnn-website/.env`.** This repo *commits* its
> `.env` files, so a live database password put there lands in git history on
> the next `git add -A`. It belongs in Render's environment variables, and — for
> step 6 — inline on the command line, which is how that step is written.

---

## 3. Create the web service

Dashboard → **New** → **Web Service** → connect the repo.

| Field | Value |
| --- | --- |
| Language | **Docker** |
| Region | **the same one as the database** |
| Root Directory | `module08/cnn-website` |
| Dockerfile Path | `Dockerfile` |
| Instance Type | Free |

**Root Directory** is what makes this work in a monorepo: Render runs commands
and resolves paths relative to it, so `Dockerfile` here means
`module08/cnn-website/Dockerfile`, and the build context is that directory —
which is what the `COPY pyproject.toml uv.lock ./` and `COPY . .` lines expect.

Then, under **Advanced**:

**Docker Command** — replaces the image's `CMD`. Two words, no quotes:

```sh
sh render-start.sh
```

`sh <file>` rather than `./render-start.sh` on purpose: it does not depend on
the executable bit surviving git and the image build. The script handles
`--host 0.0.0.0` (the default `127.0.0.1` is the container's own loopback, which
Render's proxy could never reach) and `$PORT` (Render sets it, default `10000`,
and fails the deploy if it cannot detect a bound port). The image's own `CMD`
hardcodes `8000` and runs no migration, which is why it is overridden at all.

**Health Check Path**: `/healthz`

module08's `/healthz` pings the database and returns `503` when it is
unreachable, so this checks something real rather than just "the process is up".

---

## 4. Set the environment variables

Still under **Advanced** → **Environment Variables**. `news/settings.py` builds
the connection URL from five separate parts, so map them one by one from the
database's **internal** connection details:

| Key | Value |
| --- | --- |
| `DB_HOST` | the database's internal hostname |
| `DB_PORT` | `5432` |
| `DB_NAME` | `cnn` |
| `DB_USER` | `admin` |
| `DB_PASSWORD` | the generated password |
| `NEWS_API_KEY` | your key from <https://newsapi.org/register> |

`NEWS_API_KEY` has no default and the app refuses to start without it —
`settings.py` validates at import, so a missing key is a crash at boot, not a
401 from NewsAPI ten seconds later.

Two things you do **not** need to set:

- **SSL options.** psycopg 3 defaults to `sslmode=prefer`, which negotiates TLS
  and does not verify the certificate — exactly what Render's internal
  connections (self-signed certs, no `verify-full`) accept.
- **Anything else from `.env`.** `DEFAULT_SOURCE` and `PAGE_SIZE` have working
  defaults, and `Settings` is configured `extra="ignore"`, so Render's own
  injected variables (`PORT`, `RENDER_*`) are harmless.

Click **Deploy**.

---

## 5. Watch the first deploy

The build runs `uv sync --frozen` and copies the source — a few minutes cold.
In the logs you are looking for, in order:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 759161cd8fb3, create sources and articles
INFO  [alembic.runtime.migration] Running upgrade 759161cd8fb3 -> b773fddbe615, removing fetched at
INFO  [alembic.runtime.migration] Running upgrade b773fddbe615 -> 4f0bc8afd9a6, users and liked_articles
INFO:     Uvicorn running on http://0.0.0.0:10000
```

Those three lines appear once, on the first deploy against an empty database.
Later deploys print `Context impl PostgresqlImpl` and nothing else, which is
what an up-to-date schema looks like. Then check it:

```bash
B=https://<your-service>.onrender.com

curl -s $B/healthz
# {"status":"ok","db":"ok"}     <- "db":"ok" means the private network works

curl -s $B/api/articles
# {"articles":[],"total":0,...}  <- empty, correctly: nothing has seeded it yet
```

`/docs` gives you the whole API in a browser.

---

## 6. Seed the database

The deployed service has an empty database and should not be the thing calling
NewsAPI. Instead, point your **local** app at the Render database and load the
front page once — the NewsAPI request then comes from your laptop, which is what
its free plan allows.

From `module08/cnn-website`, using the database's **external** hostname:

```bash
DB_HOST=<external-hostname> DB_PORT=5432 DB_NAME=cnn \
DB_USER=admin DB_PASSWORD=<password> NEWS_API_KEY=<your-real-key> \
  uv run uvicorn news:app --port 8000
```

Open <http://localhost:8000> once. That fetches from NewsAPI and upserts every
story into the Render database. Stop it, then confirm from the deployed service:

```bash
curl -s $B/api/stats
# {"sources":[{"slug":"cnn","name":"CNN","articles":10}],...}
```

Now the deployed app is fully usable: browse `/article/{id}`, create readers,
like things, read `/liked`. Repeat this whenever you want fresher stories.

---

## Getting into the database

There is **no SQL editor in the Render dashboard** — it shows connection details
and metrics, not a query console. You connect from outside instead, and all
three of these work on the free instance type:

```bash
# 1. psql, with the external connection string from the Info page
psql '<external-connection-string>'
psql '<external-connection-string>' -c '\dt'

# 2. the Render CLI -- the same session, less copy-paste
render psql cnn08-db
render psql cnn08-db -c 'select count(*) from articles;'
```

**3. Any GUI** — pgAdmin, DBeaver, TablePlus — using the external hostname,
port `5432`, database `cnn`, user `admin` and the generated password. TLS is
required; Render rejects `sslmode=disable` on external connections.

You do not have to give up the pgAdmin you already have. module08's Compose file
ships one, so bring up that service alone and register the Render database in it:

```bash
docker compose up -d pgadmin      # from module08/cnn-website
```

Then <http://localhost:5108> → **Register → Server…**, with the *external*
hostname. The preloaded `db` entry points at the local Compose Postgres; the
Render one is a second entry beside it.

Remember that the external host is reachable from anywhere with the password, so
a free database with no backups is not the place for anything you would mind
losing — it expires after 30 days regardless.

---

## Optional: a render.yaml Blueprint instead

Everything above in one file, committed at the **repo root** so Render can find
it (Dashboard → **New** → **Blueprint**):

```yaml
services:
  - type: web
    name: cnn08
    runtime: docker
    region: oregon
    plan: free
    rootDir: module08/cnn-website
    dockerfilePath: ./Dockerfile
    dockerCommand: sh render-start.sh
    healthCheckPath: /healthz
    envVars:
      - key: NEWS_API_KEY
        sync: false          # prompts you for it instead of storing it in git
      - key: DB_HOST
        fromDatabase: { name: cnn08-db, property: host }
      - key: DB_PORT
        fromDatabase: { name: cnn08-db, property: port }
      - key: DB_NAME
        fromDatabase: { name: cnn08-db, property: database }
      - key: DB_USER
        fromDatabase: { name: cnn08-db, property: user }
      - key: DB_PASSWORD
        fromDatabase: { name: cnn08-db, property: password }

databases:
  - name: cnn08-db
    databaseName: cnn
    user: admin
    region: oregon
    plan: free
```

`fromDatabase` is the part worth having: Render fills those five variables from
the instance it creates, so no password is ever typed or committed. `sync: false`
on the API key makes Render ask for the value at deploy time.

One caveat: Render's monorepo docs say `dockerfilePath` resolves relative to
`rootDir`, while the Blueprint spec describes it as relative to the repo root.
If the build cannot find the Dockerfile, try `module08/cnn-website/Dockerfile`.
The dashboard route in steps 3–4 has no such ambiguity.

---

## Appendix: deploying without the start script

If you would rather leave `module08/` untouched, drop `render-start.sh`, set the
Docker Command to the bare server:

```sh
uvicorn news:app --host 0.0.0.0 --port $PORT
```

...and run migrations yourself before each deploy that needs one, from
`module08/cnn-website`, against the **external** hostname:

```bash
DB_HOST=<external-hostname> DB_PORT=5432 DB_NAME=cnn \
DB_USER=admin DB_PASSWORD=<password> NEWS_API_KEY=unused \
  uv run alembic upgrade head
```

`NEWS_API_KEY=unused` is not optional even though alembic never uses it:
`migrations/env.py` imports `settings`, and `Settings` validates every field at
import, so without a value there it exits with `news_api_key Field required`
before reaching the database.

The trade is the one in [step 1](#1-the-start-script): no new file, but
production credentials on your laptop and a manual step between a push and a
working deploy.

## What you do not get

- **pgAdmin as a service.** Nothing stops you pointing your *local* one at the
  deployed database — see [getting into the database](#getting-into-the-database).
- **A shell on the instance.** `render ssh` and the dashboard's Shell tab are
  both excluded from free web services, so there is no free-tier equivalent of
  `docker compose exec api sh`. That is a large part of why `render-start.sh`
  exists: it is the only way a command runs inside that container.
- **`--reload`.** Deploys come from git pushes, not from a file watcher.
- **The bind mount.** Locally, `.:/app` means a save reaches the container. On
  Render the source is baked into the image at build time, which is why a code
  change needs a push and a redeploy.
- **A Pre-Deploy Command.** Free plan. `render-start.sh` covers it, with the
  caveat that it runs on every instance start rather than once per deploy —
  fine at one instance, something to revisit at several.

---

## Troubleshooting

**`Exited with status 127`, and the log shows the whole command as "not found":**

```
/bin/sh: 1: alembic upgrade head && uvicorn news:app --host 0.0.0.0 --port 10000: not found
```

The Docker Command was wrapped in `/bin/sh -c "…"`. Render passes the quotes
through literally, so the shell receives the entire quoted string as a single
word and tries to exec a file by that name.

**`Exited with status 2`, and alembic prints its usage:**

```
alembic: error: unrecognized arguments: && uvicorn news:app --host 0.0.0.0 --port 10000
```

The other half of the same problem: without quotes, Render execs `alembic`
directly and hands it `&&` and everything after as arguments. There is no shell
to interpret them. Use `sh render-start.sh` from step 3.

**Deploy fails with "no open ports detected".** The Docker Command was left at
the image's own `CMD`, which binds a fixed `8000` and runs no migration.

**`/healthz` returns `{"db":"unreachable"}`.** The web service cannot reach the
database. Almost always a region mismatch, or `DB_HOST` set to the *external*
hostname instead of the internal one.

**`ValidationError: news_api_key Field required`.** `NEWS_API_KEY` is not set on
the service. It has no default by design — and alembic hits the same error,
because `migrations/env.py` imports `settings`.

**`relation "articles" does not exist` on `/api/articles`.** The migration did
not run. Check the deploy log for the `Running upgrade` lines, and that the
Docker Command is `sh render-start.sh` and not the bare `uvicorn ...`.

**The front page shows an error banner but the API works.** Expected — see the
NewsAPI caveat at the top. Seed from your laptop instead (step 6).

**First request after a while takes ~a minute.** Free instances spin down after
15 minutes idle. That is the plan, not a bug.

---

## Sources

- [Render — Docker on Render](https://render.com/docs/docker)
- [Render — Web Services and port binding](https://render.com/docs/web-services)
- [Render — Monorepo support](https://render.com/docs/monorepo-support)
- [Render — Connecting to Postgres](https://render.com/docs/postgresql-creating-connecting)
- [Render — Postgres credentials](https://render.com/docs/postgresql-credentials)
- [Render — Deploys and the pre-deploy command](https://render.com/docs/deploys)
- [Render — Blueprint spec](https://render.com/docs/blueprint-spec)
- [Render — Free Postgres now expires after 30 days](https://render.com/changelog/free-postgresql-instances-now-expire-after-30-days-previously-90)
- [Render — Deploy for free](https://render.com/docs/free)
- [NewsAPI — pricing and plan terms](https://newsapi.org/pricing)
