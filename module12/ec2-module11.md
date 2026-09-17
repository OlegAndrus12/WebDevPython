# Deploying module11 to AWS EC2

Step by step, from this repo to a public IP. Unlike
[the Render guide](render-module08.md), this one is a **lift and shift**: one
Linux box, Docker, and very nearly the same `docker compose up` you already run
on your laptop.

Written for someone with an AWS account who has used SSH before.

---

## Can it be done? Yes — one instance runs the whole stack

module11 is seven containers: Postgres, Redis, the api, a Celery worker, beat,
Mailpit and pgAdmin. There is no managed-service shopping list to assemble
first; EC2 gives you a machine, Docker runs the same compose file, and the
result behaves the way it does locally. That is the appeal, and it is real.

Five things are not the same, and all five are worth reading before you start.

**1. This is not free.** The stack needs about 700 MB of RAM at rest and more
than that to build, so the 1 GB `t3.micro` is the wrong size — the image build
tends to get OOM-killed on it. `t3.small` (2 GB) is the honest minimum, at
roughly **$15/month** on-demand in `us-east-1`, plus about $2.40 for a 30 GB
`gp3` volume and $3.60 for the public IPv4 address, which AWS has charged for
since February 2024 whether the address is attached or not. Call it **$21 a
month**, or about $0.03/hour if you stop the instance when you are not using it.

If your AWS account was created **before 15 July 2025** it has the legacy
12-month free tier: 750 hours a month of `t2.micro`/`t3.micro`. That covers the
instance hours but not the size you need. Accounts created after that date get
$100–$200 of credits instead, drawn down at normal rates.

**2. Two secrets are committed to this repo.** `module11/cnn-website/.env` is
checked in — it contains a real `NEWS_API_KEY` and a real `SECRET_KEY`. That is
fine for a sandbox on your laptop and *not* fine on a public address, because
`SECRET_KEY` signs every JWT: anyone with the repo can mint an admin token for
your deployment. [Step 7](#7-write-the-servers-env) generates fresh ones. Do not
skip it.

**3. Beat is configured to send the newsletter every minute.**
`news/celery_app.py` ships with `crontab(minute="*")` and a comment explaining
why — it is there so the task can be watched running in development. Deployed as
is, that is 1440 NewsAPI calls a day against a 100/day quota, and a newsletter
every sixty seconds to every subscriber. [Step 6](#6-the-one-source-change) is a
one-line fix.

**4. NewsAPI's free plan forbids exactly this deployment.** The Developer plan
"may be used for development and testing in a development environment only". It
also rate-limits by IP, and cloud provider addresses are often refused outright.
As in module08, this matters less than it sounds: **only `GET /` and the
newsletter task call NewsAPI.** Everything else — the JSON API, article pages,
auth, likes — reads Postgres. So seed the database from your laptop
([step 11](#11-seed-the-database)) and accept that `/` may show its error banner.

**5. Mail goes nowhere.** Mailpit is a sink: it accepts every message and
delivers none. That is the safe default and the guide keeps it, reachable over
an SSH tunnel so you can still click a verification link. Real delivery needs
SES or an external SMTP provider — see [the mail section](#optional-real-email).
Note that EC2 throttles outbound port 25 by default, so use 587 or 2525.

---

## What EC2 needs that your laptop was doing for you

| Locally (`docker-compose.yaml`) | On EC2 |
| --- | --- |
| every port published to `0.0.0.0` | only `80`; the rest bound to `127.0.0.1` or not published at all |
| `.:/app` bind mount + `--reload` | source baked into the image; a redeploy is a rebuild |
| `uv sync --frozen` on every container start | done once at build time |
| `DEBUG=true`, rate limiter off | `DEBUG=false`, limiter on |
| pgAdmin on `:5111`, Flower on `:5511` | neither — `psql` over an SSH tunnel instead |
| you run `docker compose up` by hand | `restart: unless-stopped` brings it back after a reboot |
| secrets from a committed `.env` | a `.env` written on the server, never in git |

That is the whole delta, and it lives in one new file
(`docker-compose.prod.yaml`, [step 8](#8-write-the-production-compose-file))
plus one edited line of Python.

---

# Part 1 — the instance

## 1. Create the security group

EC2 Console → **Network & Security** → **Security Groups** → **Create security
group**. Name it `cnn11-sg`.

Inbound rules — three, and no more:

| Type | Port | Source | Why |
| --- | --- | --- | --- |
| SSH | 22 | **My IP** | your shell. Not `0.0.0.0/0`. |
| HTTP | 80 | `0.0.0.0/0` | the app |
| HTTPS | 443 | `0.0.0.0/0` | only if you do [the Caddy section](#optional-https-with-a-domain) |

Leave outbound as the default (all traffic).

**Do not open 5411, 6311, 5111, 8211 or 5511.** Those are Postgres with
`admin`/`admin`, an unauthenticated Redis, a pgAdmin with `admin`/`admin`, an
open mail UI and a Flower running `FLOWER_UNAUTHENTICATED_API=1`. An exposed
Redis on a public IP is typically found and abused within minutes. The compose
file in step 8 does not publish them at all; the security group is the second
lock on the same door.

One trap worth knowing even though this guide avoids it: **Docker writes its own
iptables rules and bypasses UFW.** A `ports:` entry of `"6311:6379"` is reachable
from the internet even with `ufw deny 6311` in place. The protections that work
are the security group and binding to `127.0.0.1`, which is what step 8 does.

## 2. Launch the instance

EC2 Console → **Launch instance**.

| Field | Value |
| --- | --- |
| Name | `cnn11` |
| AMI | **Ubuntu Server 24.04 LTS**, 64-bit (x86) |
| Instance type | **t3.small** (2 GB) |
| Key pair | create one, download the `.pem`, `chmod 400` it |
| Network → Security group | **select existing** → `cnn11-sg` |
| Storage | **30 GB gp3** |

30 GB is not overkill. The base image is ~1 GB, and Postgres, the uv cache, and
Docker's build cache and logs all grow.

**Cheaper, with one caveat:** `t4g.small` is a Graviton (arm64) instance at
about 20% less. Every image this stack uses — `ghcr.io/astral-sh/uv`,
`postgres:15`, `redis:7-alpine`, `axllent/mailpit` — publishes arm64, so it
works; pick the **arm64** Ubuntu AMI if you go that way.

**If you insist on t3.micro**, add swap before building or the `uv sync` layer
will be killed:

```bash
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

It will run. It will also be slow, and the worker's two prefork children are the
first thing to get squeezed.

## 3. Give it a stable address (recommended)

An instance's public IP changes every time you stop and start it, which breaks
`PUBLIC_BASE_URL` and every link in an already-sent email. **Elastic IPs** →
**Allocate** → **Associate** with the instance.

You are charged for the address either way, so there is no saving in skipping
this — only the risk of the address moving.

## 4. Install Docker

```bash
ssh -i ~/path/to/cnn11.pem ubuntu@<your-ip>
```

Then, on the instance — Docker's official apt repository, not the distro
package, which is old enough to lack the `compose` plugin:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker ubuntu
```

**Log out and back in** — group membership is read at login, so without this
every `docker` command says "permission denied while trying to connect to the
Docker daemon socket".

```bash
exit
ssh -i ~/path/to/cnn11.pem ubuntu@<your-ip>
docker compose version     # Docker Compose version v2.x.x
```

While you are here, cap the logs. Docker's default `json-file` driver grows
without limit, and three chatty containers on a 30 GB disk will eventually fill
it:

```bash
sudo tee /etc/docker/daemon.json > /dev/null <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
sudo systemctl restart docker
```

---

# Part 2 — the code

## 5. Get the source onto the instance

From your **laptop**, at the repo root. `rsync` works whether or not the repo is
public, and skips everything the image does not need:

```bash
rsync -av --delete \
  --exclude '.venv' --exclude '.git' --exclude '__pycache__' \
  --exclude '.pytest_cache' --exclude '.coverage' --exclude 'htmlcov' \
  --exclude '.env' \
  -e "ssh -i ~/path/to/cnn11.pem" \
  module11/cnn-website/ ubuntu@<your-ip>:~/cnn11/
```

The trailing slash on `module11/cnn-website/` is load-bearing: without it rsync
creates `~/cnn11/cnn-website/` instead.

`--exclude '.env'` is deliberate. The committed one has the wrong secrets, the
wrong `DEBUG`, and a disabled rate limiter; step 7 writes a new one in place.

If the repo is on GitHub you can `git clone` on the instance instead — but then
the committed `.env` arrives with it, and you must overwrite it in step 7 rather
than create it.

## 6. The one source change

On the **laptop**, in `module11/cnn-website/news/celery_app.py`, the newsletter
entry in `beat_schedule`:

```python
        "newsletter": {
            "task": "news.tasks.send_newsletter",
-           "schedule": crontab(minute="*"),
+           "schedule": crontab(hour=settings.newsletter_hour, minute=settings.newsletter_minute),
        },
```

The file's own comment says to do this; every-minute is a development
convenience that is safe only because Mailpit swallows the output. With the
change, `NEWSLETTER_HOUR` and `NEWSLETTER_MINUTE` from `.env` take effect —
08:00 UTC by default, one NewsAPI call a day.

Re-run the `rsync` from step 5 after editing.

If you would rather change nothing, the alternative is to **not run beat at all**:
delete the `beat` service from the compose file in step 8. The scheduled
newsletter and the stats report then never fire; everything else works. Tasks
can still be triggered by hand with `docker compose exec worker celery -A
news.celery_app call news.tasks.send_newsletter`.

## 7. Write the server's `.env`

On the **instance**, in `~/cnn11`. Generate the two secrets first:

```bash
cd ~/cnn11
openssl rand -hex 32        # -> SECRET_KEY
```

Then write the file. Replace `<your-ip>`, the two secrets and the NewsAPI key:

```bash
cat > ~/cnn11/.env <<'EOF'
# --- secrets: generated on this box, never committed -----------------------
NEWS_API_KEY=<a fresh key from https://newsapi.org/register>
SECRET_KEY=<the openssl rand -hex 32 output>

# --- database --------------------------------------------------------------
# Not reachable from outside the instance, but the password is still what
# stands between a compromised container and the data. Generate it too.
DB_USER=admin
DB_PASSWORD=<another openssl rand -hex 16>
DB_NAME=cnn
# Overridden to db:5432 inside compose; these are only for host-side tools.
DB_HOST=localhost
DB_PORT=5411

# --- the two development defaults that must flip ---------------------------
# The toolbar exposes SQL with bound parameters, every request header and the
# whole route table, and wraps each request in a sampling profiler.
DEBUG=false
# 0 disables the limiter -- it is 0 in the committed .env for the browser and
# load suites. On a public address it goes back on.
RATE_LIMIT_WINDOW_SECONDS=1

# --- public identity -------------------------------------------------------
# What the newsletter builds its links from. A worker has no request to infer
# it from. Trailing slash required.
PUBLIC_BASE_URL=http://<your-ip>/

# --- cache -----------------------------------------------------------------
REDIS_HOST=localhost
REDIS_PORT=6311
ARTICLE_CACHE_TTL_SECONDS=300

# --- mail: the Mailpit sink, overridden to mailpit:1025 inside compose ------
MAIL_SERVER=localhost
MAIL_PORT=1011
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_STARTTLS=false
MAIL_SSL_TLS=false
MAIL_USE_CREDENTIALS=false
MAIL_VALIDATE_CERTS=false
MAIL_FROM=noreply@cnnreader.example
MAIL_FROM_NAME=CNN Reader
VERIFICATION_TOKEN_EXPIRE_MINUTES=60

# --- worker ----------------------------------------------------------------
CELERY_BROKER_DB=1
CELERY_RESULT_DB=2
CELERY_RESULT_EXPIRES_SECONDS=3600

# --- schedules (UTC) -------------------------------------------------------
NEWSLETTER_HOUR=8
NEWSLETTER_MINUTE=0
NEWSLETTER_MAX_ARTICLES=10
STATS_REPORT_HOUR=7
STATS_REPORT_MINUTE=0
EOF

chmod 600 ~/cnn11/.env
```

`NEWS_API_KEY` and `SECRET_KEY` have no defaults — `news/settings.py` validates
at import, so a missing one is a crash at boot rather than a failure later.

## 8. Write the production compose file

On the **instance**, `~/cnn11/docker-compose.prod.yaml`. This is a **standalone
file, not a `-f` override**: Compose merges `volumes:` by mount path, so an
override cannot *remove* the `.:/app` bind mount that the development file
needs and this one must not have. A separate file is clearer than fighting the
merge rules.

```bash
cat > ~/cnn11/docker-compose.prod.yaml <<'EOF'
# module11 on a single EC2 instance. Differences from docker-compose.yaml:
#
#   - only the api publishes to the world, on :80
#   - db and mailpit bind to 127.0.0.1 (SSH tunnel only); redis not published
#   - no pgadmin, no flower
#   - no bind mount, no --reload, no `uv sync` on start: the image is the app
#   - restart: unless-stopped everywhere, so a reboot brings the stack back
name: cnn11

services:
  db:
    image: postgres:15
    container_name: cnn11_postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - cnn11_postgres_data:/var/lib/postgresql/data
    # 127.0.0.1 is the whole point: reachable through `ssh -L`, not from the
    # internet. Without the prefix Docker publishes on 0.0.0.0 and punches
    # through any host firewall to do it.
    ports:
      - "127.0.0.1:5411:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER} -d ${DB_NAME}"]
      interval: 2s
      timeout: 3s
      retries: 15
      start_period: 5s

  redis:
    image: redis:7-alpine
    container_name: cnn11_redis
    restart: unless-stopped
    # No ports at all. Nothing outside the compose network needs it, and an
    # unauthenticated Redis is the single most abused open port on the internet.
    command: redis-server --save "" --appendonly no
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 2s
      timeout: 3s
      retries: 15

  mailpit:
    image: axllent/mailpit
    container_name: cnn11_mailpit
    restart: unless-stopped
    # Web UI on the loopback only -- it is an open inbox with no login.
    # Reach it with: ssh -L 8211:localhost:8211 ubuntu@<your-ip>
    ports:
      - "127.0.0.1:8211:8025"

  api:
    build: .
    container_name: cnn11_api
    restart: unless-stopped
    env_file: .env
    environment:
      DB_HOST: db
      DB_PORT: 5432
      MAIL_SERVER: mailpit
      MAIL_PORT: 1025
      REDIS_HOST: redis
      REDIS_PORT: 6379
      # Belt and braces: `environment:` outranks `env_file:`, so even a stale
      # DEBUG=true in .env cannot turn the toolbar on here.
      DEBUG: "false"
    ports:
      - "80:8000"
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
      mailpit:
        condition: service_started
    # The image's CMD does not migrate. `&&` makes the migration a gate: a
    # failed upgrade stops the container rather than serving the wrong schema.
    # No --reload, and no `uv sync` -- the image already has the dependencies
    # and there is no bind mount for a watcher to watch.
    command: >
      sh -c "alembic upgrade head &&
      uvicorn news:app --host 0.0.0.0 --port 8000"
    healthcheck:
      test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')\""]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  worker:
    build: .
    container_name: cnn11_worker
    restart: unless-stopped
    env_file: .env
    environment:
      DB_HOST: db
      DB_PORT: 5432
      MAIL_SERVER: mailpit
      MAIL_PORT: 1025
      REDIS_HOST: redis
      REDIS_PORT: 6379
    depends_on:
      # On api, not db: only one container may run `alembic upgrade head`, and
      # waiting for a healthy api is waiting for the migration it already ran.
      api:
        condition: service_healthy
      redis:
        condition: service_started
    command: celery -A news.celery_app worker --loglevel=info --concurrency=2

  beat:
    build: .
    container_name: cnn11_beat
    restart: unless-stopped
    env_file: .env
    environment:
      DB_HOST: db
      DB_PORT: 5432
      REDIS_HOST: redis
      REDIS_PORT: 6379
    volumes:
      # The last-fired-at file. Outside /app deliberately.
      - cnn11_beat_data:/var/lib/celery
    depends_on:
      api:
        condition: service_healthy
      redis:
        condition: service_started
    # Exactly one replica, always. Two beats both fire the schedule.
    command: >
      celery -A news.celery_app beat --loglevel=info
      --schedule=/var/lib/celery/beat-schedule

volumes:
  cnn11_postgres_data:
  cnn11_beat_data:
EOF
```

So you do not have to type `-f docker-compose.prod.yaml` on every command:

```bash
echo 'export COMPOSE_FILE=~/cnn11/docker-compose.prod.yaml' >> ~/.bashrc
source ~/.bashrc
```

Every `docker compose` command below assumes that, and assumes you are in
`~/cnn11`.

---

# Part 3 — run it

## 9. Build and start

```bash
cd ~/cnn11
docker compose up -d --build --wait
```

The first build is a few minutes: `uv sync --frozen` resolves and installs the
whole dependency set. `--wait` blocks until the healthchecks pass, so if it
returns cleanly the api is already serving and the migrations are done.

```bash
docker compose ps
```

Five services, `api` and `db` reading `(healthy)`.

## 10. Verify

```bash
docker compose logs api | grep -i alembic
```

You want the migration chain, in order:

```
INFO  [alembic.runtime.migration] Running upgrade  -> 759161cd8fb3, create sources and articles
INFO  [alembic.runtime.migration] Running upgrade 759161cd8fb3 -> b773fddbe615, removing fetched at
...
INFO:     Uvicorn running on http://0.0.0.0:8000
```

Then from your **laptop**:

```bash
B=http://<your-ip>

curl -s $B/healthz
# {"status":"ok","db":"ok"}      <- "db":"ok" means the app reached Postgres

curl -s $B/api/articles
# {"articles":[],"total":0,...}  <- correctly empty: nothing has seeded it
```

`$B/docs` is the whole API in a browser.

## 11. Seed the database

The deployed app has an empty database and should not be the thing calling
NewsAPI ([caveat 4](#can-it-be-done-yes--one-instance-runs-the-whole-stack)). So
point your **local** app at the EC2 database through an SSH tunnel and load the
front page once — the NewsAPI request then comes from your laptop.

Postgres is bound to the instance's loopback, so open the tunnel first. In one
terminal:

```bash
ssh -i ~/path/to/cnn11.pem -L 5411:localhost:5411 ubuntu@<your-ip>
```

Leave it open. If module11's own stack is running locally it already holds 5411
— stop it (`docker compose down`) or forward to a different local port
(`-L 15411:localhost:5411`) and adjust below.

In another terminal, from `module11/cnn-website` on your laptop:

```bash
DB_HOST=localhost DB_PORT=5411 DB_NAME=cnn \
DB_USER=admin DB_PASSWORD='<the DB_PASSWORD from the server .env>' \
  uv run uvicorn news:app --port 8000
```

Environment variables outrank `.env` in pydantic-settings, so those five win
over the committed file. Open <http://localhost:8000> once — that fetches from
NewsAPI and upserts every story into the EC2 database. Stop it, then confirm
from outside:

```bash
curl -s http://<your-ip>/api/stats
# {"sources":[{"slug":"cnn","name":"CNN","articles":10}],...}
```

The deployment is now fully usable: browse `/article/{id}`, register, like
things, read `/liked`. Repeat whenever you want fresher stories.

`psql` through the same tunnel works too:

```bash
psql "postgresql://admin:<password>@localhost:5411/cnn" -c '\dt'
```

## 12. Read the mail

Registration sends a verification link, and Mailpit holds it. Tunnel to the UI:

```bash
ssh -i ~/path/to/cnn11.pem -L 8211:localhost:8211 ubuntu@<your-ip>
```

Then <http://localhost:8211> on your laptop. The link in the message points at
`PUBLIC_BASE_URL`, so it is clickable from anywhere.

To promote yourself to admin (there is no endpoint that does it — the stats
report goes to confirmed users whose `role` is `admin`):

```bash
docker compose exec db psql -U admin -d cnn \
  -c "UPDATE users SET role = 'admin' WHERE email = 'you@example.com';"
```

---

## Operating it

```bash
docker compose logs -f api worker beat     # follow
docker compose ps                          # what is up, and healthy
docker compose restart worker              # after a tasks.py change
docker compose down                        # stop; data survives
docker compose down -v                     # stop and DELETE the database
docker stats                               # is 2 GB actually enough
```

**Redeploy after a code change.** `rsync` again from the laptop, then rebuild:

```bash
docker compose up -d --build
```

Only changed layers rebuild, so this is fast unless `pyproject.toml` or
`uv.lock` moved. Compose recreates the containers whose image changed and leaves
the rest alone. `alembic upgrade head` runs again on the api's start command and
is a no-op when there is nothing new.

**After a reboot.** Nothing to do. `restart: unless-stopped` plus Docker's own
enabled systemd unit brings the whole stack back. Verify once with
`sudo reboot`, wait a minute, then `curl http://<your-ip>/healthz`.

**Back up the database.** Nothing else on the instance holds state worth keeping.

```bash
docker compose exec -T db pg_dump -U admin cnn | gzip > ~/cnn-$(date +%F).sql.gz
```

Copy it off the box — an EBS volume deleted with the instance takes the backup
with it. EBS snapshots of the whole volume are the AWS-native alternative.

**Running the test suite on the server.** The image installs the `dev`
dependency group, so pytest is there:

```bash
docker compose exec api pytest -q
```

It uses SQLite in memory and touches nothing in the running stack. The `e2e` and
`load` suites are a different matter — both need `RATE_LIMIT_WINDOW_SECONDS=0`
and a browser, and neither belongs on a public instance.

---

## Optional: HTTPS with a domain

Serving over plain HTTP means every JWT crosses the network in clear text. If
you have a domain, point an A record at the Elastic IP and put Caddy in front —
it obtains and renews a Let's Encrypt certificate on its own.

Change the api's `ports:` so it is no longer public, and add the proxy flags:

```yaml
  api:
    # ports: removed -- only caddy talks to it now, over the compose network
    expose:
      - "8000"
    command: >
      sh -c "alembic upgrade head &&
      uvicorn news:app --host 0.0.0.0 --port 8000
      --proxy-headers --forwarded-allow-ips='*'"
```

Then add:

```yaml
  caddy:
    image: caddy:2-alpine
    container_name: cnn11_caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - cnn11_caddy_data:/data
      - cnn11_caddy_config:/config
    depends_on:
      api:
        condition: service_healthy
```

with `~/cnn11/Caddyfile`:

```
news.example.com {
    reverse_proxy api:8000
}
```

and `cnn11_caddy_data`, `cnn11_caddy_config` added under `volumes:`. Open 443 in
the security group, and set `PUBLIC_BASE_URL=https://news.example.com/` in
`.env`.

**`--proxy-headers` is not optional here, and the reason is specific to this
app.** The rate limiter in `news/middleware.py` keys on `request.client.host`.
Behind a proxy that is Caddy's own container IP for every request, so all
visitors share one bucket and a `RATE_LIMIT_WINDOW_SECONDS` of 1 throttles the
entire site to one `/api` call per second. Uvicorn's proxy-headers middleware
rewrites `request.client` from `X-Forwarded-For`, which restores per-visitor
limiting. `--forwarded-allow-ips='*'` is safe *only* because the api no longer
publishes a port — nothing but Caddy can reach it to forge the header.

## Optional: real email

Mailpit delivers nothing. To send real mail, set these in `.env` and remove the
`MAIL_SERVER`/`MAIL_PORT` overrides from the `api` and `worker` services in the
compose file, so `.env` wins:

```ini
MAIL_SERVER=email-smtp.us-east-1.amazonaws.com   # or smtp.mailtrap.io, etc.
MAIL_PORT=587
MAIL_USERNAME=<smtp username>
MAIL_PASSWORD=<smtp password>
MAIL_STARTTLS=true
MAIL_USE_CREDENTIALS=true
MAIL_VALIDATE_CERTS=true
MAIL_FROM=you@your-verified-domain.com
```

Two AWS specifics: **port 25 is throttled on EC2 by default** (use 587), and
**SES starts in sandbox mode**, where it will only send to addresses you have
verified. Getting out of the sandbox is a support request. `MAIL_FROM` must be a
verified identity — the default `noreply@cnnreader.example` will be rejected.

With real mail configured, check `NEWSLETTER_HOUR` and the
[step 6](#6-the-one-source-change) edit again before starting the stack.

---

## Beyond one box

This guide puts everything on one instance because that is what module11's
compose file describes and it is the honest starting point. What you would
change as it grows, roughly in the order the pain arrives:

| Pressure | Move |
| --- | --- |
| database is the thing you cannot lose | **RDS for PostgreSQL** — backups, snapshots, restore |
| a reboot means downtime | **ALB** + two instances, or ECS/Fargate |
| Redis restarts lose queued tasks | **ElastiCache** |
| `docker build` on the server is slow | build in CI, push to **ECR**, pull on deploy |
| secrets live in a file on disk | **Secrets Manager** or SSM Parameter Store |

Each one is real money and real configuration. None of them is needed to see
module11 working on a public URL.

---

## Troubleshooting

**`docker: permission denied while trying to connect to the Docker daemon
socket`.** You have not logged out since `usermod -aG docker`. Exit the SSH
session and reconnect.

**The build dies with `Killed` or exit code 137.** Out of memory during
`uv sync`. You are on a `t3.micro`; add swap or resize the instance.

**`curl http://<ip>/healthz` hangs or times out.** Port 80 is not open in the
security group, or the stack is not up. `docker compose ps` on the instance, and
check the inbound rules. A *connection refused* (rather than a hang) means the
security group is fine and the api is not listening.

**`{"db":"unreachable"}`.** The api cannot reach Postgres. `docker compose logs
db` — most often the db container is restarting because `DB_PASSWORD` in `.env`
changed after the volume was created. Postgres only reads those variables when
it initialises an empty data directory. Either restore the old password or
`docker compose down -v` and start fresh.

**`ValidationError: secret_key Field required` at boot.** `.env` is missing,
in the wrong directory, or was excluded by the rsync and never recreated. It
must be at `~/cnn11/.env`, beside the compose file.

**`/` shows an error banner but `/api/articles` works.** Expected — NewsAPI
refusing the cloud IP, or the free-plan quota spent. Seed from your laptop
([step 11](#11-seed-the-database)).

**Everything returns 429.** `RATE_LIMIT_WINDOW_SECONDS` is doing its job but the
limiter sees one client. Either you are behind a proxy without `--proxy-headers`
(see [the HTTPS section](#optional-https-with-a-domain)), or the window is too
large for a front end that fires two or three `/api` calls per page load. `1` is
the right order of magnitude.

**A newsletter every minute.** The [step 6](#6-the-one-source-change) edit did
not make it to the server. `docker compose exec beat grep -n 'crontab' \
news/celery_app.py` to confirm, then rsync and `docker compose up -d --build beat`.

**The debug toolbar is visible on a page.** `DEBUG` is true somewhere. The
compose file pins `DEBUG: "false"` in the api's `environment:`, which outranks
`env_file:` — if you see the toolbar, you are running the development compose
file. Check `echo $COMPOSE_FILE`.

**Disk full.** `docker system df`, then `docker system prune -a --volumes` —
read what it lists before agreeing, `--volumes` includes the database.

---

## Teardown

Stopping the instance still costs you the EBS volume and the Elastic IP (about
$6/month). To pay nothing:

1. Back up first if you care: `pg_dump` as above, and copy the file off.
2. EC2 Console → **Instance state** → **Terminate**. The root volume goes with
   it if **Delete on termination** was left at its default.
3. **Elastic IPs** → select → **Release**. An allocated-but-unassociated address
   is still billed.
4. **Volumes** → check nothing was left behind, and **Snapshots** if you took
   any.
5. Delete the `cnn11-sg` security group and the key pair if you are done.

---

## Sources

- [AWS — Get started with Amazon EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/EC2_GetStarted.html)
- [AWS — Security group rules](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/security-group-rules.html)
- [AWS — Elastic IP addresses](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/elastic-ip-addresses-eip.html)
- [AWS — EC2 On-Demand pricing](https://aws.amazon.com/ec2/pricing/on-demand/)
- [AWS — New public IPv4 address charge (Feb 2024)](https://aws.amazon.com/blogs/aws/new-aws-public-ipv4-address-charge-public-ip-insights/)
- [AWS — Free Tier](https://aws.amazon.com/free/)
- [AWS — Port 25 restriction on EC2](https://repost.aws/knowledge-center/ec2-port-25-throttle)
- [Amazon SES — Moving out of the sandbox](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html)
- [Docker — Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Docker — Packet filtering and firewalls (Docker and ufw)](https://docs.docker.com/engine/network/packet-filtering-firewalls/)
- [Compose — Merge and override rules](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
- [Uvicorn — Deployment and proxy headers](https://www.uvicorn.org/deployment/)
- [Caddy — Automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [NewsAPI — pricing and plan terms](https://newsapi.org/pricing)
