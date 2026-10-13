# Deployment: Vercel + Render + Neon

The platform runs on three free services. Nothing here changes how the code runs locally
(`make up` still brings up the whole stack on one laptop).

```
 a phone or a laptop
        │
        ▼
 myrakshasetu.vercel.app          Vercel · Next.js (apps/web)
        │   /v1/* is proxied by app/v1/[...path]/route.ts, which stamps
        │   x-rs-listener: local (rule R18) and keeps the session cookie
        │   on one origin
        ▼
 rakshasetu-api-vmc1.onrender.com   Render · the API image (Dockerfile.render)
        │   api + worker + ticker in one container
        ▼
 Neon Postgres (PostGIS)          the only data service, in Singapore
```

## What is where

| Piece | Service | Configuration |
|---|---|---|
| Front end | Vercel, project `rakshasetu-web` | Root directory `apps/web`, production domain `myrakshasetu.vercel.app`, env `API_ORIGIN=https://rakshasetu-api-vmc1.onrender.com` |
| Back end | Render, service `rakshasetu-api` | Docker, `Dockerfile.render`, start command `services/api/render_start.sh`, health check `/healthz`, plan free, region singapore, URL `https://rakshasetu-api-vmc1.onrender.com` |
| Database | Neon (through the Vercel integration) | PostGIS + pg_trgm; roles `neondb_owner` (migrations) and `rakshasetu_app` (the API) |

Render assigned the `-vmc1` suffix because `rakshasetu-api` was already taken; the hostname is fixed for
the life of the service, which is why the front end's `API_ORIGIN` and the keepalive both name it.

`render.yaml` is the same service written down as a blueprint (`render blueprints validate render.yaml`).
It exists so the service can be recreated in one step; applying it creates a **second** service, so do it
only when the existing one is gone.

## Environment variables

Render holds the API's variables (13 of them). Production values live in `.env.production` (gitignored) —
that file is the record of what the service is running with, and the place to edit before re-pushing a
value in the Render dashboard. The provider keys are the ones from the local `.env`. `SECRET_KEY`,
`PHONE_HASH_KEY` and `PHONE_ENC_KEY` are generated once and must never be regenerated: phones are hashed
with `PHONE_HASH_KEY` and encrypted with `PHONE_ENC_KEY`, so a new value makes every stored phone unreadable.

Vercel holds one variable, `API_ORIGIN`, which points the `/v1/*` rewrite at Render.

## Database setup, from scratch

```bash
psql "$OWNER_URL" -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
psql "$OWNER_URL" -c "CREATE ROLE rakshasetu_app LOGIN PASSWORD '…'; GRANT USAGE ON SCHEMA public TO rakshasetu_app;"
cd services/api && OWNER_DATABASE_URL="$OWNER_URL" .venv/bin/python -m app.migrate
```

`grants.sql` runs at the end of every migration and leaves `rakshasetu_app` with INSERT + SELECT on
`events` only — the API role cannot rewrite history (rule R9), which is what makes `make verify` mean
something on the deployed database too.

## Deploying a change

- **Front end**: push to `main`; Vercel builds `apps/web` automatically.
- **Back end**: Render does **not** auto-deploy this service. It was created from the public repository
  URL, without Render's GitHub App, so a push is not a deploy. Either press **Deploy latest commit** in
  the dashboard or run:

  ```bash
  render deploys create srv-db6rbb8u01pc73b9pbq0 --wait
  ```

  (Installing the Render GitHub App for the repository is what turns auto-deploy on.)
  Migrations run at boot: `render_start.sh` calls `python -m app.migrate` before uvicorn.

## Seeding

The seed runs inside the Render instance, against the Neon database. From the Render dashboard open the
service's **Shell** and run:

```bash
python -m app.seed            # an empty platform with one admin (admin / rakshasetu)
python -m app.seed --demo     # the four sample packs, synthetic people
```

`DEMO_OWNER_DATABASE_URL` must be set for either (it is), and `DEMO_MODE=true`.

**Start an incident before phoning in.** A public report goes to the live incident — the newest one that
is open — and with no incident at all it is deliberately kept for review instead of being lost
(`live_incident()` in `app/modules/public/router.py`). On an empty platform a voice message is therefore
transcribed and extracted, then parked as `needs_review · unknown incident`, and the desk stays empty.
Start an incident on the desk (Incidents) first: the next report becomes its first case.

## Signing in on the deployed site

`admin` / `rakshasetu` at `/login`, typed. The one-tap picker on the front door and `/v1/demo/*` are both
refused here, because Render serves every service through Cloudflare: those endpoints refuse any request
carrying `cf-connecting-ip` (rule R18 — demo controls exist only on a local listener, never through a
tunnel). Nothing else on the desk is affected: `require_local` endpoints check only the listener header,
which the proxy sets.

## What is honest about this deployment

- **The free Render instance sleeps** after 15 minutes without traffic and takes ~30–60 s to wake.
  `.github/workflows/keepalive.yml` pings `/healthz` every 10 minutes to keep it awake; GitHub pauses
  scheduled workflows after 60 days without a commit.
- **The desk's live updates poll instead of using a WebSocket.** A socket cannot be held open through
  Vercel's serverless front end, so `apps/web/lib/live.ts` falls back to `GET /v1/events?since=` every
  2.5 s — the same scoped envelopes. Locally, the socket is still used.
- **Evidence files are ephemeral.** `/files` in the container is cleared on every deploy and restart.
  The database is not: Neon keeps everything.
- **`DEMO_MODE=true` on a public address**, but the password-less picker and `/v1/demo/*` still refuse
  requests that carry `cf-connecting-ip`, and Render's front door is Cloudflare — so the demo controls
  are not reachable from the internet even though the flag is on. Sign in by typing `admin` with the
  password. (Locally, on the tunnel-less listener, the picker works as designed.)
- **Free tiers**: Render free (512 MB, 0.1 CPU), Neon free (0.5 GB), Vercel Hobby.
