# Deploying module08 to Render

Step by step, from this repo to a public URL. **No changes to module08's source
are needed** — the Dockerfile already builds a production image, and everything
Render needs is set in its dashboard.

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
| `command:` runs `alembic upgrade head` before uvicorn | a **Docker Command** override does the same |
| app listens on a fixed `8000` | must bind `0.0.0.0:$PORT` |
| `env_file: .env` | environment variables set in the dashboard |

The Dockerfile's `CMD` hardcodes `--port 8000` and does not run migrations, so
you override the command. That is the only Render-specific thing in the whole
setup.

---

## 1. Push the repo to GitHub

Render deploys from a connected repo. The whole monorepo goes up; you point the
service at one subdirectory in step 3.

```bash
git push origin main
```

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

When it finishes provisioning, open its **Info** page. You will need, from the
*internal* connection details: **hostname**, **port** (5432), **database**,
**username**, **password**. Keep the *external* connection string too — step 6
uses it.

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
step 6 seeds through the external one.

You can skip transcribing any of this by using the
[Blueprint](#optional-a-renderyaml-blueprint-instead) — `fromDatabase` fills
`DB_HOST` and the rest from the instance Render creates.

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

**Docker Command** — replaces the image's `CMD`:

```sh
/bin/sh -c "alembic upgrade head && uvicorn news:app --host 0.0.0.0 --port $PORT"
```

Three things are happening there:

- `/bin/sh -c` because it is two commands. `&&` also makes the migration a
  gate: a failed `alembic upgrade head` stops the container instead of letting
  it serve against the wrong schema.
- `--host 0.0.0.0`, because the default `127.0.0.1` is the container's own
  loopback and Render's proxy would never reach it.
- `--port $PORT`. Render sets `PORT` (default `10000`) and fails the deploy if
  it cannot detect a bound port. `sh` expands it at start time.

Running migrations in the start command is the free-tier approach. Render's
**Pre-Deploy Command** is the proper home for migrations, but it is not
available on the Free plan. On a single free instance there is nothing to race,
and `alembic upgrade head` is idempotent — it re-runs on every wake-up and does
nothing.

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
INFO  [alembic.runtime.migration] Running upgrade b773fddbe615 -> 4f0bc8afd9a6, ...
INFO:     Uvicorn running on http://0.0.0.0:10000
```

Then check it:

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

From `module08/cnn-website`, using the database's **external** connection
details:

```bash
DB_HOST=<external-hostname> DB_PORT=5432 DB_NAME=cnn \
DB_USER=admin DB_PASSWORD=<password> \
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

If you would rather not connect anything locally, `psql` works too — the
external connection string is on the database's Connect panel:

```bash
psql '<external-connection-string>' -c '\dt'
```

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
    dockerCommand: /bin/sh -c "alembic upgrade head && uvicorn news:app --host 0.0.0.0 --port $PORT"
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

## What you do not get

- **pgAdmin.** It is a dev convenience; use `psql` with the external connection
  string, or Render's own database UI.
- **`--reload`.** The Docker Command above deliberately omits it. Deploys come
  from git pushes, not from a file watcher.
- **The bind mount.** Locally, `.:/app` means a save reaches the container. On
  Render the source is baked into the image at build time, which is why a code
  change needs a push and a redeploy.

---

## Troubleshooting

**Deploy fails with "no open ports detected".** The command is not binding
`$PORT`, or not binding `0.0.0.0`. Check the Docker Command is the `/bin/sh -c`
form — without it, `$PORT` is passed to uvicorn as a literal string.

**`/healthz` returns `{"db":"unreachable"}` or the deploy hangs on migrations.**
The web service cannot reach the database. Almost always a region mismatch, or
`DB_HOST` set to the *external* hostname instead of the internal one.

**`ValidationError: news_api_key Field required` at boot.** `NEWS_API_KEY` is
not set on the service. It has no default by design.

**The front page shows an error banner but the API works.** Expected — see the
NewsAPI caveat at the top. Seed from your laptop instead (step 6).

**Everything 404s or the schema is empty.** `alembic upgrade head` did not run.
Confirm the Docker Command override actually saved; the image's own `CMD` does
not include it.

**First request after a while takes ~a minute.** Free instances spin down after
15 minutes idle. That is the plan, not a bug.

---

## Sources

- [Render — Docker on Render](https://render.com/docs/docker)
- [Render — Web Services and port binding](https://render.com/docs/web-services)
- [Render — Monorepo support](https://render.com/docs/monorepo-support)
- [Render — Connecting to Postgres](https://render.com/docs/postgresql-creating-connecting)
- [Render — Deploys and the pre-deploy command](https://render.com/docs/deploys)
- [Render — Blueprint spec](https://render.com/docs/blueprint-spec)
- [Render — Free Postgres now expires after 30 days](https://render.com/changelog/free-postgresql-instances-now-expire-after-30-days-previously-90)
- [Render — Deploy for free](https://render.com/docs/free)
- [NewsAPI — pricing and plan terms](https://newsapi.org/pricing)
