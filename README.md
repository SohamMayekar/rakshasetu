# RakshaSetu

> **Get every family in a flood to safety.**

RakshaSetu ("bridge of protection") is the district control room's rescue-request desk for the first two weeks of a disaster. Calls for help arrive as voice clips, typed calls, forwarded messages, volunteer spreadsheets and other teams' systems. Each family becomes **one case with one rescue team**, followed until the team reports them safe. Nobody is lost, nobody is counted twice, and a team that goes quiet is noticed.

Built at CodeAstra 2.0 for **Web PS 1, National-Scale Incident Command Operating Layer**: a national layer of district desks. The spec is [`docs/PRD.md`](docs/PRD.md) (v1.1). What is done, not done and blocked is in [`docs/STATUS.md`](docs/STATUS.md). The proof (the 9 required components, the tests, the golden path, the drills, the numbers) is in [`docs/VERIFICATION.md`](docs/VERIFICATION.md).

## The three innovations
1. **One household across calls, forwards and sheets, with reasons and refusals.** "Same village · same landmarks · circles overlap", merged by a person and undoable; "Rajesh ≠ Ramesh: not merged".
2. **Landmark words → a place with an honest circle**, for a caller who isn't there ("behind the Durga temple, near the bridge" → within 150 m, from real OpenStreetMap data).
3. **One owner whose silence is noticed, never auto-reassigned**, closed by the rescuers' headcount ("4 taken, someone still there" → "2 of 6 still there" → "Rescued 6 of 6").

AI does two things only: speech to text, and extracting facts **with their quotes**. Rules and people decide everything else ([`AI_USAGE.md`](AI_USAGE.md)).

**A live demo, performed by the team** ([`docs/DEMO.md`](docs/DEMO.md)): one of us asks for help from a phone as a son in Mumbai (typed, or spoken with a speech key); it lands on the desk in seconds; the officer sends a team; the team's phone accepts, reaches and records the rescue; the family's phone is asked "Is that right?". Everything runs on the real code paths; only the people, phone numbers and the 60× clock are demo values.

## Run it (one laptop, no paid service)

Needs Docker with Compose v2 and `make`. The browser checks (`make e2e`, `make drills`, `make screens`) also need Node 22 and `cd apps/web && npm ci && npx playwright install chromium`.

```bash
make env          # copies .env.example to .env: dev-only local values, no keys (change SECRET_KEY before going public)
make up           # builds and starts db, api, worker, ticker, web, caddy
make seed         # the three scenario packs (Bihar flood, Odisha cyclone, Himachal landslide), synthetic people
make test         # copy rules (never-say words + screen jargon) + ruff + the API suite (419 tests) on a separate test database
```

Open **http://localhost**. The front door has two choices: **I need help** (the phone app for people, `/r`) and **Control room dashboard**. Sign in as one of three people:

| Profile | Who | Opens | Shows |
|---|---|---|---|
| **Duty officer** | R. Das, Bihar only | the desk (`/desk/BR`), on the projector | need help now · a team on it · rescued, then Needs you now and the map; Desk · History · Demo |
| **Rescue team** | Fire & Rescue Boat 5 | the team's phone app (`/responder`) | its own cases, each with one big next action |
| **State admin** | all three incidents | All incidents (`/`) | the three disasters on a map of India, each with its numbers |

Phones use the **public listener** on :8080, through a Cloudflare quick tunnel on the day. Nine more synthetic users stay seeded for the permission tests; they are not on the sign-in screen (D22).

| Command | What it does |
|---|---|
| `make demo-reset SCENE=son` | Reset to a step of the demo (`son`, `merge`, `sheet`, `stale`, `rescue`, `receipts`); the script is [`docs/DEMO.md`](docs/DEMO.md) |
| `make drills` | Failure drills on the running stack: worker crash mid-surge, desk cut off, API restart, tiles down, language model off, tamper, scene reset |
| `make surge RATE=50 DURATION=60` | 3,000 synthetic, pre-structured partner reports; watch the desk's numbers |
| `make partner-demo CASE=BR-199` | A **simulated** partner's signed notes; they appear on the case |
| `make webhook-sink` | A partner's webhook receiver that checks our signature (set `DEMO_PARTNER_WEBHOOK_URL=http://api:9009/hook`) |
| `make verify` · `make tamper SEQ=12` | Verify the hash chain · edit one past event as a superuser and watch History → Check nothing was changed break at it |
| `make provider-check` | With keys in `.env`: one live call per STT/LLM provider |
| `make screens OUT=… PAGES="…"` · `make count PAGES="…"` | Screenshots at 1366×768 and phone size · how many things compete for attention in a screen's first view |

## Architecture (PRD §12)

```
 phones ── tunnel ──▶ Caddy :8080 (public: reporter, status, team app, ingest, partners)
 projector ─────────▶ Caddy :80   (local: everything, incl. the desk and the demo reset API)
                          │
            ┌─────────────┴──────────────┐
            ▼                            ▼
   Next.js app (apps/web)       FastAPI codebase (services/api), run 3 ways:
   desk · team app ·              api      HTTP + WebSocket
   reporter · status page         worker   the pipeline, imports, webhook deliveries (jobs, SKIP LOCKED)
                                  ticker   every 5 s: deadlines → escalations; events → webhooks
                          │
                          ▼
            Postgres + PostGIS: the only data service. Jobs are rows; timers are rows;
            the hash-chained `events` table is both the audit trail and the live stream (LISTEN/NOTIFY).
```

No Redis, no Kafka, no microservices, no object store, no agent framework. **Cost: ₹0.** Everything is open source and self-hosted, apart from free tiers behind provider interfaces with fallbacks: Sarvam / Groq Whisper (speech to text), Groq / Gemini (extraction), OpenFreeMap tiles, and a Cloudflare quick tunnel. With no keys at all, everything still works on the keyword rules and recorded transcripts.

## Honesty
- All people and phone numbers are **synthetic**; the places are real OpenStreetMap data (ODbL).
- The demo clock runs **60× faster** and says so on every ring and on the desk's header. The surge uses pre-structured reports (no model is called). The demo partner is our own script, "simulated by RakshaSetu".
- The son's clip is a **synthetic voice** (espeak-ng) until the team records one. Without keys, its transcript is a recorded fixture, and the receipt says "not a live STT call". **No live AI call has been made in this build environment.**
- The audit trail is **tamper-evident**, not tamper-proof (a superuser could re-hash, which partner anchoring catches).
- Screens are English only for now (D17); the rules still read Hindi and Hinglish.

## Documentation
| | |
|---|---|
| [`docs/VERIFICATION.md`](docs/VERIFICATION.md) | The 9 components → demo moment → test; T1–T10; the golden path; drills; numbers; the humans' pre-stage list |
| [`docs/STATUS.md`](docs/STATUS.md) | Every milestone and its proof; NOT DONE; BLOCKED |
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | D1–D34: where the build chose, and why |
| [`docs/SIMPLIFY_PLAN.md`](docs/SIMPLIFY_PLAN.md) | The simplify run (m63–m72): every screen before → after, the plain-word glossary, the three profiles |
| [`docs/TEACHBACK.md`](docs/TEACHBACK.md) | 20 questions every team member should be able to answer |
| [`docs/modules/`](docs/modules) | A short explainer per module |
| [`docs/TESTS.md`](docs/TESTS.md) · [`docs/DRILLS.md`](docs/DRILLS.md) · [`docs/MEASUREMENTS.md`](docs/MEASUREMENTS.md) | Tests, drills, measured numbers (measured only) |
| [`packages/contracts/`](packages/contracts) | OpenAPI, the report and extraction schemas, the partner contract card |
| [`AI_USAGE.md`](AI_USAGE.md) | The AI in the product, and the AI that built it |

**Credits:** OpenStreetMap contributors (ODbL), OpenFreeMap, MapLibre GL JS (BSD-3), Noto Sans (OFL), lucide icons (ISC), segno (BSD), FastAPI, PostGIS, Caddy, Next.js.
