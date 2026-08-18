# flask-node — why a network is needed

Three containers that have to talk to each other:

```
  browser ──:5001──► flask (portal)  ──http://???:3000──► node-api  ──mongodb://???:27017──► mongo
             host           Python                          Node.js                          Mongo
```

| Service | Directory | Stack | Container port |
| --- | --- | --- | --- |
| `flask` | [grade-submission-portal/](grade-submission-portal/) | Python / Flask UI | 5001 |
| `node-api` | [grade-submission-api/](grade-submission-api/) | Node / Express REST API | 3000 |
| `mongo` | — | official `mongo` image | 27017 |

**Neither app hardcodes a hostname.** The portal calls
`http://${GRADE_SERVICE_HOST}:3000/grades`; the API connects to
`mongodb://${DB_HOST}:${DB_PORT}/${DB_NAME}`. Reading the address of your collaborators
from the environment is the one change an application needs to become container-friendly.

The walkthrough is **Parts 2 and 3** of [../README.md](../README.md), which deliberately
breaks this stack before fixing it. This is the short version.

---

## The short way — Docker Compose

[docker-compose.yaml](docker-compose.yaml) declares all three containers, the network and
the volume:

```bash
cd module02/flask-node

docker compose up --build      # build + create network + start, logs in the foreground
# or:
docker compose up -d --build   # detached
```

Open <http://localhost:5001>, submit a grade, then open the Grades tab.

```bash
docker compose ps              # service status
docker network ls              # note flask-node_default — created automatically
docker volume ls               # flask-node_mongo-data
docker compose logs -f node-api
docker compose exec node-api sh
docker compose down            # stop + remove containers and the network
docker compose down -v         # ...and delete the volume (grades are gone)
```

Three things Compose did that are worth naming:

- **It created the network.** Every service joins `<project>_default` and is resolvable by
  its **service name**. That is why `GRADE_SERVICE_HOST=node-api` and `DB_HOST=mongo` work.
- **It kept `mongo` unpublished.** No `ports:` entry, so Mongo is unreachable from your Mac
  but perfectly reachable at `mongo:27017` from `node-api`. Publishing and networking are
  separate concerns.
- **It persisted the data.** `mongo-data` is a named volume, so grades survive
  `docker compose down` — but not `down -v`.

> **`depends_on` does not mean "wait until ready".** It orders *container start*, not
> *application readiness*. Mongo accepts connections a second or two after its container
> starts, and `node-api` may connect first — Mongoose retries, so it recovers. Real
> readiness needs a `healthcheck:` plus
> `depends_on: { mongo: { condition: service_healthy } }`.

---

## The long way — and why it fails first

Do this once before using Compose; it is the entire point of the directory.

### 1. Build the two images

```bash
docker build -t node-api ./grade-submission-api
docker build -t flask-portal ./grade-submission-portal
```

### 2. Run them naively, and watch it fail

```bash
docker run -d --name mongo -e MONGO_INITDB_DATABASE=grade_db mongo
docker run -d --name node-api -p 3000:3000 \
  -e DB_HOST=localhost -e DB_PORT=27017 -e DB_NAME=grade_db node-api
docker run -d --name flask -p 5001:5001 \
  -e GRADE_SERVICE_HOST=localhost flask-portal

curl -s localhost:3000/grades   # hangs, then errors
docker logs node-api            # ECONNREFUSED 127.0.0.1:27017
docker logs flask               # ConnectionRefusedError ... localhost:3000
```

All three containers start; none of them can reach the others. **Each container has its
own network namespace, so `localhost` inside a container means *that container*** — not
your Mac, and not the container next door. `-p 3000:3000` does not help: port publishing
opens a path from the *host* to a container, never between two containers.

```bash
docker rm -f mongo node-api flask
```

### 3. The default bridge is not enough

Containers with no `--network` join the built-in `bridge`, where they can reach each other
**by IP only** — there is no DNS:

```bash
docker run -d --name mongo -e MONGO_INITDB_DATABASE=grade_db mongo
docker inspect -f '{{.NetworkSettings.IPAddress}}' mongo   # e.g. 172.17.0.2

docker run --rm busybox nslookup mongo        # can't resolve 'mongo'  ← no DNS
docker run --rm busybox ping -c1 172.17.0.2   # works                  ← but unusable

docker rm -f mongo
```

That IP is assigned at start time and changes on every restart, so it cannot go in a config
file. (`busybox` is used only because it is a tiny image that ships `ping` and `nslookup`.)

### 4. A user-defined network, which has DNS

```bash
docker network create my-network

docker run -d --name mongo    --network my-network \
  -e MONGO_INITDB_DATABASE=grade_db mongo
docker run -d --name node-api --network my-network -p 3000:3000 \
  -e DB_HOST=mongo -e DB_PORT=27017 -e DB_NAME=grade_db node-api
docker run -d --name flask    --network my-network -p 5001:5001 \
  -e GRADE_SERVICE_HOST=node-api flask-portal

docker exec flask python -c "import socket; print(socket.gethostbyname('node-api'))"
curl -s localhost:3000/grades   # []
```

Open <http://localhost:5001>. It works.

### 5. Feel the pain, then use Compose

To restart this after a code change: stop three containers, remove three containers,
rebuild two images, re-run three long `docker run` lines **in the right order**, and
remember the network. That is what Compose exists to remove.

```bash
docker rm -f mongo node-api flask
docker network rm my-network
```

---

## The three rules to take away

1. `localhost` inside a container is that container. Always.
2. Container-to-container traffic uses the **container port** (`node-api:3000`), never the
   published host port. Publishing is only host→container.
3. On a user-defined network (or in Compose), the **container/service name is the
   hostname**. Configuration should be a name injected as an env var — never an IP, never
   `localhost`.

Next: [../microservices/](../microservices/) — the same ideas with seven services.
