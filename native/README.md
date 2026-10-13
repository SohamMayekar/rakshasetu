# Running RakshaSetu natively (no Docker)

The whole stack runs as plain processes on this laptop. Nothing from `infra/docker-compose.yml`
is used; instead a tiny Node proxy (`native/proxy.mjs`) takes over Caddy's local-listener job.

## What runs where

| Process | Port | Role |
|---|---|---|
| Postgres 17 + PostGIS (brew services) | 5432 | the only data service (`rakshasetu` + `rakshasetu_test`) |
| API (uvicorn, `services/api/.venv`) | 8000 | HTTP + WebSocket (`/v1/ws`) |
| worker, ticker | — | pipeline/imports and 5-second escalations, same venv |
| Next.js (`apps/web`, `next start`) | 3100 | the UI (internal; not opened directly) |
| **native/proxy.mjs** | **3000** | **open this one**: `/v1/*` + `/healthz` → API with `X-RS-Listener: local`, everything else → Next |

The proxy replaces Caddy: it injects the `X-RS-Listener: local` header the API requires for the
desk endpoints, and proxies the live-updates WebSocket upgrade.

## Commands

```bash
native/start.sh        # migrations if needed, then api + worker + ticker + web + proxy
native/stop.sh         # stop everything (also frees ports 3000/3100 from orphans)
```

Logs and pid files: `var/log/{api,worker,ticker,web,proxy}.{log,pid}`

## The live demonstration (with provider keys)

`make demo-live GROQ_API_KEY=gsk_…` (or `SARVAM_API_KEY=…`, `GEMINI_API_KEY=…`; `scripts/demo_live.sh`) saves the
keys into `.env`, restarts the stack so every process sees them, runs `app.providers.check` (one tiny live call
per provider), then plays the whole demonstration (`app.modules.demo.scenes --scene receipts`: the clip through
the voice pipeline, the forward and the merge, the 300-row sheet, the silent boat, the rescue) and prints the
receipts — which reports a live provider read and which the word rules did. It re-seeds the demo database, so
the previous state is wiped. `--scene son|merge|sheet|stale|rescue` stops at a reset point; `native/stop.sh`
stops the stack afterwards.

Reseed the demo data (Bihar flood, Odisha cyclone, Himachal landslide, Mumbai floods — 105 cases,
40 teams, 17 synthetic users):

```bash
cd services/api && source ../native/env.sh && .venv/bin/python -m app.seed --demo   # the four sample packs (without --demo: an empty platform)
```

## Environment

- `.env` (repo root, from `.env.example`): secrets incl. a generated `PHONE_ENC_KEY`.
  It must be identical for every process — phone numbers are encrypted with it at rest.
- `native/env.sh`: derives all `*_DATABASE_URL`s from `.env` against `localhost:5432`
  (roles `rakshasetu_owner` / `rakshasetu_app`, passwords per `.env.example`).

## Sign in

http://localhost:3000 → Control room dashboard → pick an account (demo password: `rakshasetu`):

- **rdas** — duty officer, the Bihar desk (`/desk/BR`)
- **boat5** — rescue team phone app (`/responder`)
- **admin** — state admin, all incidents with the map

## One-time setup (already done on this machine)

1. `brew services start postgresql@17`; extensions `postgis` + `pg_trgm` available (brew postgis).
2. Roles/databases created once:
   `CREATE ROLE rakshasetu_owner LOGIN PASSWORD 'rakshasetu-owner';`
   `CREATE ROLE rakshasetu_app LOGIN PASSWORD 'rakshasetu-app';`
   `CREATE DATABASE rakshasetu OWNER rakshasetu_owner;` (and `rakshasetu_test`), then in each:
   `CREATE EXTENSION postgis; CREATE EXTENSION pg_trgm;`
3. `python3 -m venv services/api/.venv && services/api/.venv/bin/pip install -e "services/api[dev]"`
4. `cd apps/web && npm ci`
5. `cd services/api && source ../native/env.sh && .venv/bin/python -m app.migrate && .venv/bin/python -m app.seed`
