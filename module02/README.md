# Module 02 — Docker, networking and Docker Compose

Nine self-contained examples that build up, step by step, from *"run one script in a
container"* to *"orchestrate seven polyglot services with one command"*.

**Every folder has its own README with the full walkthrough** — the Dockerfile line by
line, what breaks and why, the exercises. This page is the map and the command reference:
what each example is for, the two ways to start it, and every Docker command used in the
module on one page.

Read them in order. Each one exists to introduce exactly one new idea.

| # | Folder | New idea | Stack |
| --- | --- | --- | --- |
| 0 | [welcome-to-docker/](welcome-to-docker/) | Run an image somebody else built | nginx |
| 1 | [python-script/](python-script/) | `Dockerfile`, `build`, `run` | Python |
| 2 | [ruby-script/](ruby-script/) | Write a Dockerfile yourself (exercise) | Ruby |
| 3 | [java/](java/) | Shipping a pre-built artifact, `.dockerignore` | Java |
| 4 | [flask-node/](flask-node/) | **Containers must share a network** → Compose | Python + Node + Mongo |
| 5 | [microservices/](microservices/) | Compose at scale, service-to-service calls | Python + Node + Go + Java + React |
| 6 | [postgres_ex/](postgres_ex/) | Compose with *no build at all* — images + volumes | Postgres + pgAdmin |
| 7 | [statusboard-uv/](statusboard-uv/) | A real project: lock file, dev/runtime split | Python (uv) |
| 8 | [statusboard-poetry/](statusboard-poetry/) | The same app, same lesson, different packaging tool | Python (Poetry) |

Jump to the **[Docker cheat sheet](#docker-cheat-sheet)** at the bottom for the commands
themselves, grouped by task.

---

## Prerequisites

```bash
docker --version           # 20.10+ ; this doc was checked against 29.3.1
docker compose version     # v2+ ; note the space — `docker-compose` is the old v1 binary
docker info                # must not error: the daemon has to be running
```

Everything below runs **from inside the example's own directory**, never from the repo
root — the trailing `.` in `docker build -t name .` is the build context, and it has to
be the folder holding the Dockerfile.

> **Apple Silicon.** A few examples pin old base images that only publish `amd64`
> (`node:14`, `maven:3.6.3-openjdk-17-slim`). They still run, under emulation, just
> slowly. If a build dies with `no matching manifest`, add `--platform linux/amd64` to
> `docker build`, or `platform: linux/amd64` to the compose service.

---

## The examples

One folder per idea. Each README carries the full walkthrough — the Dockerfile line by
line, both ways to start it (Compose and plain `docker` commands), what breaks and why.

### 0 · [welcome-to-docker/](welcome-to-docker/) — run someone else's image

An intentionally empty folder: before building anything, run a published image and watch
Docker pull an nginx you never installed. Introduces `-d`, `-p host:container` and
`--name`. → **[README](welcome-to-docker/README.md)**

### 1 · [python-script/](python-script/) — the minimal Dockerfile

One Python file and the four instructions almost every image starts with — `FROM`,
`WORKDIR`, `COPY`, `CMD`. The container exits the moment the script does, because a
container lives exactly as long as its main process. → **[README](python-script/README.md)**

### 2 · [ruby-script/](ruby-script/) — your turn

The same shape in Ruby, with the Dockerfile as a reference solution to write yourself
first. Run it once with no build at all, by bind-mounting the source into a stock image:
the fastest way to run anything, and the wrong way to ship it.
→ **[README](ruby-script/README.md)**

### 3 · [java/](java/) — an image over a pre-built artifact

A compiled `.jar` and nothing else, so the image only supplies a JRE — the opposite choice
to `order-management`, which compiles inside the container and ships the whole JDK. Also
where `COPY . .` copying too much motivates `.dockerignore`. → **[README](java/README.md)**

### 4 · [flask-node/](flask-node/) — why a network is needed

**The core of the module.** A Flask portal, an Express API and Mongo that have to reach
each other; the README breaks the stack on purpose first — `localhost` inside a container
is that container, and the default bridge has no DNS — before fixing it with a
user-defined network and only then reaching for Compose.
→ **[README](flask-node/README.md)** ·
[api](flask-node/grade-submission-api/README.md) ·
[portal](flask-node/grade-submission-portal/README.md)

### 5 · [microservices/](microservices/) — Compose at scale

Seven services in five languages, and nothing new conceptually — only the number of moving
parts. The lesson is the call graph: the browser can only reach port 4000, so the UI
container proxies to service names that exist solely inside the network.
→ **[README](microservices/README.md)** — every service folder has its own

### 6 · [postgres_ex/](postgres_ex/) — Compose without a build

No `Dockerfile` anywhere: two stock images configured entirely through environment
variables, which is the normal case for infrastructure. pgAdmin then repeats the network
lesson by connecting to host `db`, never `localhost`. → **[README](postgres_ex/README.md)**

### 7 · [statusboard-uv/](statusboard-uv/) — a real project, packaged with uv

Everything before this was a toy; this is a Flask app with a `pyproject.toml`, a lock file
and dev dependencies, copied unchanged from [`module01/uv_ex/`](../module01/uv_ex/). Five
instructions, and `uv sync --frozen --no-dev` in place of `pip install`.
→ **[README](statusboard-uv/README.md)**

> **Known gap:** `uv.lock` was removed from this folder in the *module02 cleanup* commit,
> so `RUN uv sync --frozen` currently fails the build. Run `uv lock` there before demoing.

### 8 · [statusboard-poetry/](statusboard-poetry/) — the same app, packaged with Poetry

Byte-identical application, different packaging tool, which makes the pair a controlled
experiment: every difference between the two images is attributable to the tool. Six
instructions instead of five, 332 MB instead of 268 MB, and one widely-repeated piece of
advice that quietly breaks the lock file. → **[README](statusboard-poetry/README.md)**


---

## Docker cheat sheet

Every command used in this module, grouped by task.

### Images

```bash
docker build -t name .                   # build from ./Dockerfile; "." is the CONTEXT
docker build -t name -f path/Dockerfile .# explicit Dockerfile
docker build --no-cache -t name .        # ignore the layer cache
docker build --platform linux/amd64 -t name .
docker images                            # local images
docker images --format "table {{.Repository}}\t{{.Size}}"
docker history name                      # one row per instruction, with layer sizes
docker pull image:tag                    # fetch without running
docker rmi name                          # delete an image
docker tag name registry/user/name:1.0   # rename before pushing
```

### Containers

```bash
docker run image                         # foreground, dies with your terminal
docker run -d image                      # detached
docker run --rm image                    # delete the container when it exits
docker run -it image bash                # interactive shell instead of the CMD
docker run --name n image                # stable name instead of "nifty_bardeen"
docker run -p 8080:80 image              # publish HOST:CONTAINER
docker run -e KEY=value image            # environment variable
docker run --env-file .env image         # ...many of them
docker run -v vol:/path image            # named volume
docker run -v "$PWD":/app -w /app image  # bind-mount the current dir, and cd into it
docker run --network net image           # join a user-defined network
docker run image some other command      # override CMD

docker ps                                # running
docker ps -a                             # including stopped
docker stop n / docker start n / docker restart n
docker rm n                              # delete a stopped container
docker rm -f n                           # stop and delete in one go
```

### Looking inside

```bash
docker logs n                            # stdout/stderr of the main process
docker logs -f n                         # follow
docker exec -it n sh                     # shell in a RUNNING container (bash if present)
docker exec n env                        # one-off command
docker inspect n                         # everything docker knows, as JSON
docker inspect -f '{{.NetworkSettings.IPAddress}}' n
docker stats                             # live CPU/memory
docker cp n:/app/file.txt .              # copy out of a container
```

### Networks

```bash
docker network create my-network         # user-defined bridge → has DNS
docker network ls
docker network inspect my-network        # which containers are attached
docker network connect my-network n      # attach a running container
docker network rm my-network
```

Rules that never change:

1. `localhost` inside a container is **that container**. Always.
2. Container→container traffic uses the **container port** (`node-api:3000`), never the
   published host port. `-p` only opens host→container.
3. On a user-defined network the **container/service name is the hostname**. Configuration
   should be a name in an env var — never an IP, never `localhost`.
4. The default `bridge` network has no DNS: names do not resolve there, only IPs work.

### Volumes

```bash
docker volume create data
docker volume ls
docker volume inspect data
docker volume rm data
docker run -v data:/var/lib/postgresql/data postgres:15   # named volume — docker-managed
docker run -v "$PWD/services.json":/app/services.json img # bind mount — a host path
```

A container's filesystem dies with the container. Named volumes survive `down`; bind
mounts live in your repo; the real answer for application data is a database.

### Compose

```bash
docker compose up                        # create network + volumes, build if needed, start
docker compose up -d --build             # detached, force a rebuild
docker compose up -d --build one-service # rebuild and replace a single service
docker compose build                     # build without starting
docker compose ps                        # status of this project's services
docker compose logs -f svc               # follow one service
docker compose exec svc sh               # shell into a running service
docker compose run --rm svc cmd          # one-off container, not the long-running one
docker compose restart svc
docker compose stop                      # stop, keep containers
docker compose down                      # stop + remove containers and the network
docker compose down -v                   # ...and delete named volumes (DATA LOSS)
docker compose down --rmi local          # ...and delete images this project built
docker compose config                    # print the resolved file, with defaults filled in
```

`depends_on:` orders **container start**, not application readiness. For real readiness
add a `healthcheck:` to the dependency and
`depends_on: { db: { condition: service_healthy } }`.

### Compose ↔ plain Docker

| Task | Plain Docker | Compose |
| --- | --- | --- |
| Build | `docker build -t name .` | `build:` + `docker compose build` |
| Start | `docker run -d --name n -p 80:80 img` | `docker compose up -d` |
| Stop & remove | `docker rm -f n` | `docker compose down` |
| Logs | `docker logs -f n` | `docker compose logs -f svc` |
| Shell | `docker exec -it n sh` | `docker compose exec svc sh` |
| Network | `docker network create net` + `--network net` | automatic (`<project>_default`) |
| Hostname | `--name n` | the service key |
| Env var | `-e KEY=value` | `environment:` / `env_file:` |
| Volume | `-v vol:/path` | `volumes:` |
| Start order | run them in the right order, by hand | `depends_on:` |

### Dockerfile instructions used in this module

| Instruction | Does |
| --- | --- |
| `FROM image:tag` | Base image. Pin it; unmaintained tags disappear (see [java/](java/)) |
| `WORKDIR /app` | `cd` inside the image, creating the directory if needed |
| `COPY src dst` | Host → image. Paths are relative to the **build context** |
| `RUN cmd` | Executes at **build** time, producing a layer |
| `ENV KEY=value` | Environment variable baked into the image |
| `EXPOSE 3000` | Documentation only — publishes nothing. Only `-p`/`ports:` does |
| `CMD ["exe","arg"]` | Default command at **run** time; overridable on the command line |
| `USER app` | Drop root. Missing from every example here — an exercise |
| `HEALTHCHECK` | Lets `docker ps` say `healthy`, and lets others wait for readiness |

**Layer caching:** every instruction is a cached layer; change one and it plus everything
below it rebuilds. That is why dependency manifests are copied *before* source code
everywhere in this module:

```dockerfile
COPY requirements.txt .                 # changes rarely
RUN pip install -r requirements.txt     # ← expensive, stays cached
COPY . .                                # changes constantly
```

**`.dockerignore`** works like `.gitignore` but for the build context — matched files are
never even sent to the daemon. Ignore `node_modules/`, `target/`, `.venv/`, `.git/`, and
the `Dockerfile` itself.

### Cleanup

```bash
docker compose down -v                   # per project, from its directory
docker ps -a                             # what is still around
docker system df                         # disk used by images/containers/volumes/cache
docker system prune                      # stopped containers, unused networks, dangling images
docker system prune -a --volumes         # nuke everything unused, volumes included
```

### Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ECONNREFUSED 127.0.0.1:<port>` inside a container | Using `localhost` to reach another container | Use the service/container name |
| `getaddrinfo ENOTFOUND <name>` / `unknown host` | Not on a shared user-defined network (or on the default bridge, which has no DNS) | Same compose project, or `docker network create` + `--network` |
| `Bind for 0.0.0.0:5432 failed: port is already allocated` | Something else owns the host port | `lsof -i :5432`, or change the **left** side: `"5433:5432"` |
| Published port reaches nothing | App bound to `127.0.0.1` inside the container | Bind `0.0.0.0` (e.g. `flask run --host 0.0.0.0`) |
| Code change not reflected | Image was not rebuilt | `docker compose up -d --build` |
| `no matching manifest for linux/arm64` | amd64-only base image | `--platform linux/amd64` / `platform:` |
| Stale data after a schema or env change | Old named volume reused | `docker compose down -v` |
| Build unexpectedly slow, huge context | Missing `.dockerignore` | Ignore `node_modules/`, `target/`, `.git/` |
| Container exits immediately, no error | Its main process finished — that is normal for scripts | `docker logs`; use a long-running process for a service |
