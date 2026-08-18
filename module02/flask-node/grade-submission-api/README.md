# grade-submission-api

The Express REST API behind [../grade-submission-portal/](../grade-submission-portal/).
It stores and returns grades, and it is the middle box of the three-container chain in
[../README.md](../README.md):

```
flask (5001) ──► node-api (3000) ──► mongo (27017)
```

| Route | Method | Does |
| --- | --- | --- |
| `/grades` | GET | Return every stored grade as JSON |
| `/grades` | POST | Store one `{ name, subject, score }` |

Mongo is reached at `mongodb://${DB_HOST}:${DB_PORT}/${DB_NAME}` — **read from the
environment, not hardcoded.** That is what makes the same image work on a laptop
(`DB_HOST=localhost`) and inside a network (`DB_HOST=mongo`).

## Run it — with the rest of the stack

Normally you never start this alone. From the parent directory:

```bash
cd module02/flask-node
docker compose up --build
```

## Run it alone

```bash
cd module02/flask-node/grade-submission-api
docker build -t node-api .

# it still needs a Mongo to talk to, on a shared user-defined network
docker network create my-network
docker run -d --name mongo --network my-network -e MONGO_INITDB_DATABASE=grade_db mongo
docker run -d --name node-api --network my-network -p 3000:3000 \
  -e DB_HOST=mongo -e DB_PORT=27017 -e DB_NAME=grade_db node-api

curl -s localhost:3000/grades
curl -s -X POST localhost:3000/grades \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ada","subject":"Maths","score":95}'
```

`DB_HOST=localhost` here would fail with `ECONNREFUSED 127.0.0.1:27017` — inside the
container, `localhost` is the container itself. See Part 2 of [../../README.md](../../README.md).

```bash
docker rm -f node-api mongo && docker network rm my-network
```

## The Dockerfile

```dockerfile
FROM node:14
WORKDIR /app
COPY package*.json ./     # changes rarely
RUN npm install           # ← expensive, stays cached
COPY . .                  # changes constantly
EXPOSE 3000
CMD ["node", "app.js"]
```

The manifest is copied *before* the source so that editing `app.js` does not reinstall
`node_modules`. Flip those two blocks and every edit pays for a full `npm install`.

`EXPOSE` is documentation only — it publishes nothing. Only `-p` / `ports:` does that.

> `node:14` is long out of support and only publishes `amd64`. On Apple Silicon it runs
> under emulation; if the build fails with `no matching manifest`, add
> `--platform linux/amd64`. Upgrading the tag is a good exercise.
