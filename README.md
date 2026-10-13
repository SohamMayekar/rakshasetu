# RakshaSetu

> **One command layer for every emergency.**

RakshaSetu ("bridge of protection") is a **national incident command platform**. Reports arrive from anywhere (voice, typed calls, forwarded messages, volunteer spreadsheets, partner systems, and sensors) and each family or incident becomes **one case with one accountable team**, followed with its evidence and a minute-by-minute timeline until the people are **confirmed safe**. One national desk shows every disaster at once; a duty officer sees only their own districts; a responding team sees only its own cases on a phone. Nothing about it is tied to one city, one kind of disaster or one kind of team.

Built at CodeAstra 2.0 for **Web PS 1, National-Scale Incident Command Operating Layer**. The point-by-point answer to the brief is [`docs/BRIEF.md`](docs/BRIEF.md); the original spec is [`docs/PRD.md`](docs/PRD.md); what is done, not done and blocked is in [`docs/STATUS.md`](docs/STATUS.md); how to present it is [`docs/PITCH.md`](docs/PITCH.md).

## What it offers
| | |
|---|---|
| **Any disaster** | Floods, cyclones, landslides, fires, gas, building collapses, earthquakes, road accidents. Each is an *incident* started from a form, with its own districts and case numbers. |
| **Any team** | 20 agencies and 24 capabilities (boats, divers, rope, heavy lift, collapse search, fire, hazmat, ambulance, evacuation, shelter, food and water, road clearance, drones…). Teams are added in the app, with their lead's sign-in. |
| **Any way in** | Voice and typed reports from a no-login help page, forwards, volunteer sheets, a signed partner interface, signed sensor readings. A WhatsApp number is designed ([`docs/WHATSAPP.md`](docs/WHATSAPP.md)). |
| **Any signal** | A request is saved on the phone and sent by itself when signal returns; a phone-to-phone relay is designed and demonstrated as a labelled simulation (`/mesh`). |
| **One national desk** | One queue and one map across every incident, role-scoped in the database, live over one WebSocket, with an audit trail you can check. |
| **Honest AI** | AI turns speech into text and pulls out facts **with their exact quotes**. Rules rank; people decide. With no AI keys at all, every case is still created. |

## The three ideas
1. **One household across calls, forwards and sheets, with reasons and refusals.** "Same village · same landmarks · circles overlap", merged by a person and undoable; "Rajesh ≠ Ramesh: not merged".
2. **Landmark words → a place with an honest circle**, for a caller who isn't there ("behind the primary school, near the bridge" → within 150 m, from real OpenStreetMap data).
3. **One owner whose silence is noticed, never auto-reassigned**, closed by the rescuers' headcount ("4 taken, someone still there" → "Rescued 6 of 6") and the family's own confirmation.

AI does two things only: speech to text, and extracting facts **with their quotes**. Rules and people decide everything else ([`AI_USAGE.md`](AI_USAGE.md)). Languages: [`docs/LANGUAGES.md`](docs/LANGUAGES.md).

**A live demo, performed by the team** ([`docs/DEMO.md`](docs/DEMO.md)): you start an incident and add a team on the empty platform, someone asks for help from a phone, it lands on the national desk in seconds, the officer sends a team, the team's phone accepts and records the rescue, and the family's phone is asked "Is that right?". Everything runs on the real code paths; only the people, phone numbers and the 60× clock are demo values.

## Run it (one laptop, no paid service)

Needs Docker with Compose v2 and `make`. The browser checks (`make e2e`, `make drills`, `make screens`) also need Node 22 and `cd apps/web && npm ci && npx playwright install chromium`.

```bash
make env          # copies .env.example to .env: dev-only local values, no keys (change SECRET_KEY before going public)
make up           # builds and starts db, api, worker, ticker, web, caddy
make seed         # an EMPTY platform with one admin (admin / rakshasetu): no city, no district, nothing assumed.
                  # Sign in, start your own incident (Incidents), add your teams (Teams), and it is yours.
make seed-demo    # optional: the four sample scenario packs (Mumbai, Bihar, Odisha, Himachal), synthetic people
make test         # copy rules (never-say words + screen jargon) + ruff + the API suite (419 tests) on a separate test database
```

Open **http://localhost**: the landing page. From there, **I need help** is the phone page for people (`/r`, no sign-in), **Team app** is the rescue team's phone app (`/responder`), and **Control room** signs in the demo's national admin in one tap and opens the national desk (`/desk`). Sign in as:

| Profile | Who | Opens | Shows |
|---|---|---|---|
| **National admin** | `admin` | the national desk (`/desk`) | every incident in one queue and one map; Cases · Teams (add teams) · Alerts · Sheets · Sensors · Incidents (start, stand down, close) · History |
| **Duty officer** (sample packs) | a district's officer | the same desk, scoped to their own districts | need help now · a team on it · rescued, then Needs you now and the map |
| **Rescue team** | a team's lead | the team's phone app (`/responder`) | its own cases, each with one big next action, saved on the phone when there is no signal |

Phones use the **public listener** on :8080, through a Cloudflare quick tunnel on the day. The sample packs also seed more synthetic users for the permission tests; they are not on the sign-in screen (D22).

| Command | What it does |
|---|---|
| `make demo-reset SCENE=son` | Reset to a step of the demo (`son`, `merge`, `sheet`, `stale`, `rescue`, `receipts`); the script is [`docs/DEMO.md`](docs/DEMO.md) |
| `make drills` | Failure drills on the running stack: worker crash mid-surge, desk cut off, API restart, tiles down, language model off, tamper, scene reset |
| `make surge RATE=50 DURATION=60` | 3,000 synthetic, pre-structured partner reports; watch the desk's numbers |
| `make telemetry-demo` | **Simulated** sensors (river, rain, wind) rise through their warning lines, signed; watch **Sensors** on the desk and the changes on History |
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
- On a clean start there is **no demo data at all**. The sample packs (`make seed-demo`) use **synthetic** people and phone numbers; their places are real OpenStreetMap data (ODbL).
- The demo clock runs **60× faster** and says so on every ring and on the desk's header. The surge uses pre-structured reports (no model is called). The demo partner is our own script, "simulated by RakshaSetu".
- The son's clip is a **synthetic voice** (espeak-ng) until the team records one. Without keys, its transcript is a recorded fixture, and the receipt says "not a live STT call". **No live AI call has been made in this build environment.**
- The audit trail is **tamper-evident**, not tamper-proof (a superuser could re-hash, which partner anchoring catches).
- Screens are English only for now (D17). Voice is transcribed by Sarvam in many Indian languages; the word rules read Hindi, Hinglish, Marathi and English, and other languages are read when the AI keys are set ([`docs/LANGUAGES.md`](docs/LANGUAGES.md)).
- **Sensors are simulated** by our script until a partner connects real instruments. The **Bluetooth relay and the WhatsApp number are designed, not built**; the site and docs say so.

## Documentation
| | |
|---|---|
| [`docs/PITCH.md`](docs/PITCH.md) | How to present it: the 3-minute and 5-minute script, the demo order, the answers, what not to claim |
| [`docs/BRIEF.md`](docs/BRIEF.md) | The problem statement, point by point: what is built, where to see it, what is not there |
| [`docs/LANGUAGES.md`](docs/LANGUAGES.md) · [`docs/WHATSAPP.md`](docs/WHATSAPP.md) · [`docs/HERO_IMAGE.md`](docs/HERO_IMAGE.md) | Languages, the WhatsApp option, the landing picture's brief |
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
