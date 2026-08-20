# Module 02 — Agenda

Nine folders that build up from *"run one script in a container"* to *"orchestrate seven polyglot
services with one command"*, each introducing exactly one new idea. The first four are single
containers and the Dockerfile itself; `flask-node/` is the turning point, where two containers
cannot reach each other and the fix is a network rather than a port; from there Compose replaces
the `docker run` lines, first for three services and then for seven. The module closes by
dockerizing the same `statusboard` app module 01 packaged twice, so the only variable left is the
packaging tool. Command reference and troubleshooting live in [README.md](README.md).

## Topics

### Images and the Dockerfile
- **Running someone else's image** (`welcome-to-docker/`) — pull vs. build, `-d`, `--name`, and
  `-p host:container`: an image is a shippable filesystem plus a default command
- **The minimal Dockerfile** (`python-script/`) — `FROM`, `WORKDIR`, `COPY`, `CMD`; build context;
  image vs. container; why a container exits when its process does
- **The same shape, another language** (`ruby-script/`) — written as an exercise; running code with
  no build at all via a bind mount, and why that is not how you ship
- **Shipping a pre-built artifact** (`java/`) — runtime image vs. build image, `COPY . .` copying
  too much, `.dockerignore`, layer caching and instruction order, and a base image that vanished

### Container networking
- **Why a network is needed** (`flask-node/`) — Flask + Express + Mongo, deliberately broken first:
  `localhost` inside a container is that container; port publishing is host→container only; the
  default bridge has no DNS; a user-defined network resolves container names; configuration belongs
  in environment variables, never IPs

### Docker Compose
- **Compose as declared `docker run`** (`flask-node/`) — services, `build:`, `ports:`,
  `environment:`, `depends_on:` and why it does not mean "wait until ready"; the project network and
  named volumes Compose creates for you
- **Compose at scale** (`microservices/`) — seven services in five languages; service-to-service
  calls by name, why a browser cannot resolve them and the UI container proxies instead; per-service
  `.dockerignore`; the same stack written out as plain `docker` commands for contrast
- **Compose with no build at all** (`postgres_ex/`) — Postgres + pgAdmin from stock images,
  configured entirely through environment variables; named volumes and data that survives `down`
  but not `down -v`

### Packaging a real project
- **uv in an image** (`statusboard-uv/`) — module 01's Flask app unchanged: a `pyproject.toml` and a
  lock file instead of a loose `pip install`, `uv sync --frozen --no-dev` for a reproducible
  runtime without the dev dependencies, and what a five-instruction image still leaves out
- **The same app, packaged with Poetry** (`statusboard-poetry/`) — byte-identical code makes the
  pair a controlled experiment: every difference is attributable to the tool. Six instructions
  instead of five, 332 MB instead of 268 MB, and the widely-repeated
  `POETRY_VIRTUALENVS_CREATE=false` advice that quietly breaks the lock file
