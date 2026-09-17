# Module 12 — Agenda

### Render — module08 ([guide](render-module08.md))
- A Dockerfile-based web service from one subdirectory of a monorepo (`rootDir`)
- Binding `0.0.0.0:$PORT`, and why the image's own `CMD` is not enough
- The Docker Command is not a shell: no `&&`, no quotes, one executable only
- A start script as the place migrations belong, with `set -e` as the gate and
  `exec` so the server keeps PID 1 and still receives SIGTERM
- Managed Postgres: internal vs external hostnames, region pinning, `sslmode=prefer`
- Config as five env vars, wired with `fromDatabase` in a Blueprint
- `/healthz` as a health check that actually touches the database
- Reaching the database from outside: `psql`, `render psql`, or a local pgAdmin
  pointed at the external host — and no shell on a free instance
- What the free tier costs you: 30-day Postgres expiry, spin-down, no pre-deploy
- An upstream API whose licence forbids production use, and seeding around it
