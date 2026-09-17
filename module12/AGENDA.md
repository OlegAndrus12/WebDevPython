# Module 12 — Agenda

### Render — module08 ([guide](render-module08.md))
- A Dockerfile-based web service from one subdirectory of a monorepo (`rootDir`)
- Binding `0.0.0.0:$PORT`, and why the image's own `CMD` is not enough
- Migrations as a start-command gate, since pre-deploy is not on the free plan
- Managed Postgres: internal vs external hostnames, region pinning, `sslmode=prefer`
- Config as five env vars, wired with `fromDatabase` in a Blueprint
- `/healthz` as a health check that actually touches the database
- What the free tier costs you: 30-day Postgres expiry, spin-down, no pre-deploy
- An upstream API whose licence forbids production use, and seeding around it
