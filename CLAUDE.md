# RakshaSetu: build rules for every Claude session

*Copy this file to the root of the event repo at H0. Every build session reads it first. The full spec is `docs/PRD.md` (copy PRD v1.1 into the repo at H0). When this file and the PRD disagree, the PRD wins. Raise it with the humans.*

**RakshaSetu** ("bridge of protection") is the district control room's rescue-request desk for the first two weeks of a disaster. Every plea from calls, voice, WhatsApp forwards, volunteer spreadsheets and partner systems becomes **one household case with one owner**, until the rescue team reports back.

Tagline: **Never lost. Never doubled. Never stale.**

## 1. Non-negotiables

2. **AI does two things only:** speech to text, and extracting facts **with quotes** into a closed schema. **Rules and people decide everything else:** priority, merges, location, assignment, closure and replies.
   - Never add an LLM call that decides, ranks, writes free text shown to users, or replies to a reporter.
   - No LangGraph, no agent frameworks, no "agentic" wording anywhere: code, comments, UI or docs. Misrepresenting AI's role is a **disqualification ground**.
3. **Zero budget.** No paid APIs, paid services or card-gated trials. Free tiers sit behind provider interfaces with fallbacks (PRD §8.4, §12.5). Development and tests use **recorded fixtures and the extraction cache**, never live provider calls.
4. **No burden on people in danger.** Victims and relatives never have to remember, type or show anything: no codes, no OTPs, no command syntax. Their confirmations are optional, and **silence never blocks, closes, escalates or lowers priority**.
5. **Every human on the team must be able to explain every module.** Prefer boring, explicit code over clever code. After finishing a module, write or update its 5-line explainer in `docs/modules/<module>.md`: what it does, the key table(s), the one tricky rule, and how to show it.
6. **Honesty.** Never present cached or recorded output as live. The demo clock is labelled "×60". The surge uses pre-structured reports. All people and phone numbers in the data are synthetic.

## 2. Architecture in one screen (PRD §12)

- **One Next.js app** (`apps/web`) with route groups `(desk)/`, `responder/`, `r/`, `s/[id]/`, and **one shared design system** in `components/ui` (owned by Session 2).
- **One FastAPI codebase** (`services/api`) run as **three processes**:
  - `api`
  - `worker` (the intake pipeline and the importer)
  - `ticker` (every 5 s: overdue deadlines → escalations)
- **Postgres + PostGIS is the only data service.**
  - The job queue uses `SELECT … FOR UPDATE SKIP LOCKED` with lanes.
  - Real-time uses `LISTEN/NOTIFY` carrying the sequence number only.
  - Timers are rows.
  - The **`events`** table is both the hash-chained audit trail and the real-time stream.
- **Caddy with two listeners:**
  - `:8080` public: reporter, status, responder, `/v1/public/*`, `/v1/ingest/*`, `/v1/partners/*`, team-lead endpoints, with request-body caps. This is the only port the Cloudflare quick tunnel points at.
  - `:80` local: everything, including the desk, `/v1/demo/*` and the "sign in as…" picker. The projector uses this one.
- **No Redis, no Kafka, no microservices, no object store, no cloud hosting.**

## 3. "Write it this way" rules (correctness that judges can trigger)

| # | Rule | Why |
|---|---|---|
| R1 | **Every state change calls `append_event()` as the last statement before commit.** It takes `pg_advisory_xact_lock(1)`, builds the canonical JSON body **once**, stores it as `TEXT`, computes `hash = sha256(prev_hash ‖ body)`, inserts the row, and calls `pg_notify('ev', seq)`. Nothing else writes events, and nothing else sends WebSocket messages | Sequence order = commit order (no skipped events); no chain forks; no false "chain broken" from re-serialised jsonb |
| R2 | Keep transactions short. The importer commits **per row** (or per 20-row batch) | The R1 lock is global |
| R3 | `intake.accept()` inserts the **report and its job in one transaction**, before any AI runs | Never lost |
| R4 | Idempotency keys are **namespaced by the authenticated source** (`partner:<id>`, `wa`, `voice:<device>`), set server-side, never read from the body. `INSERT … ON CONFLICT DO NOTHING RETURNING`; a replay returns the original id with `Idempotent-Replay: true`. Every mutating responder and partner endpoint takes `Idempotency-Key` | Retries never duplicate; a partner can't pre-claim another source's key |
| R5 | Dedupe-and-create runs under `pg_advisory_xact_lock(hashtext('dedupe:'‖incident_id))` | Two reports in the same second can't both create a case |
| R6 | Assignment transitions are **single conditional UPDATEs** that include the team check (`… WHERE id=$1 AND team_id=$caller_team AND state='open'`). Zero rows → 409. **The database's `now()` is the only clock.** A phone's `happened_at` is stored and shown, never used for deadline maths | Responsibility; no clock games |
| R7 | **One open assignment per case** (partial unique index) and **one open escalation per (case, level)** (partial unique index). The second action gets a 409 naming who acted and when | Two officers, two boats, one roof |
| R8 | **Every repository function takes a `Scope`** and puts it in the SQL `WHERE`. Role and scope are loaded from the DB on each request (the token holds only the user id). A team lead's scope = their live assignments. WebSocket subscriptions and every event are scope-checked. Write an IDOR test per resource | No post-check leaks |
| R9 | The app's DB role (`rakshasetu_app`) has **INSERT + SELECT only** on `events` and doesn't own any table. Migrations run as `rakshasetu_owner` | Audit integrity |
| R10 | Deadlines: acknowledge-by → ETA + grace → on-scene window. **Only deliberate contact resets them** (a team app action, or the officer's team-level radio contact). The heartbeat only updates "last seen" | A PWA can't heartbeat with the screen off |
| R11 | A deadline passing **never reassigns**. It marks `contact_overdue`, sets the team to `overdue` (excluded from suggestions), and raises one escalation per team | Two boats, one roof |
| R12 | The keyword path **creates the case** whenever the LLM is off, failing, timing out (8 s) or out of quota. An STT failure creates an "audio only" case. The case never depends on AI | Never lost |
| R13 | The LLM output is validated with Pydantic against `contracts/extraction.schema.json`. It has **no priority field and no free-text summary**. Every field carries a quote, and the quote check marks misses amber | Prompt injection can't do anything a lie can't |
| R14 | All report, transcript and AI text is rendered as **text**. **Never `Popup.setHTML`** or `dangerouslySetInnerHTML` | XSS |
| R15 | Uploads: Caddy body caps; Pillow `verify()` + re-encode (strip EXIF); ffmpeg `-t 30` with a 10 s timeout; XLSX via `openpyxl(read_only=True)` + `defusedxml`; caps on rows, columns and cell size; never evaluate formulas | Poisoned inputs |
| R16 | Evidence files are content-addressed (`files/ab/<sha256>`), hashed while streaming, and the sha256 goes into the evidence's event body | Provenance |
| R17 | Phone numbers are encrypted at rest, matched by keyed HMAC, **masked in every UI and WebSocket payload**, and revealed only through an audited action with a reason | Privacy |
| R18 | `/v1/demo/*` exists only on the local listener **and** rejects any request carrying `CF-Connecting-IP` | A judge can't reset the demo |
| R19 | Partner webhooks: HMAC-SHA256 over the **raw bytes**, compared with `hmac.compare_digest`, a ±300 s window, a per-partner rate cap, and a `flags.yaml` kill switch | Replay safety |
| R20 | Jobs are at-least-once with idempotent handlers; a job locked for more than 60 s is reclaimed. Lanes: live voice > WhatsApp/partner > import > surge | Surge and recovery |

## 4. Module ownership (avoid collisions)

| Session | Owns these folders | Must coordinate before touching |
|---|---|---|
| 1 · Platform | `infra/`, DB migrations, `app/modules/{auth,audit,realtime,intake,partners,metrics}`, `app/ticker.py` scaffold, `app/channels/` registry, `packages/contracts/`, `scripts/{seed,demo_reset,verify_chain,surge}.py`, `data/scenarios/*/seed` | Anything in another session's modules |
| 2 · Command centre | `apps/web/(desk)/`, `apps/web/components/ui/` (the design system) | API contracts (ask Session 1) |
| 3 · Intake intelligence | `app/pipeline/`, `app/modules/{location,dedupe}`, `providers/`, `dictionaries/`, `i18n/`, `apps/web/r/`, `apps/web/s/`, `scripts/import_osm.py` | `cases` schema changes (ask Session 1) |
| 4 · Ownership | `app/modules/{dispatch,assignments,escalation,rescues,triage,imports}`, the ticker's logic, `apps/web/responder/` | `cases` / `events` schema changes (ask Session 1) |

- **Contracts first:** OpenAPI, `report.v1.schema.json`, `extraction.schema.json`, the WS event list and the partner contract card live in `packages/contracts/`. Change them only with a note in the PR description.
- **Schema changes go through Session 1.** Other sessions request them, and don't hand-edit migrations.
- The shared config is `services/api/config/rakshasetu.config.yaml` (team-owned values; PRD §9). Don't hard-code a number that belongs there.

## 5. Conventions

- **Python:** 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + GeoAlchemy2, `ruff` + `pytest`. Each module has `router.py` · `service.py` · `repo.py` · `schemas.py`. No business logic in routers.
- **TypeScript:** Next.js (app router) + Tailwind + shadcn/ui; MapLibre GL JS + OpenFreeMap Positron; Noto Sans (incl. Devanagari) with tabular figures.
- **UI rules** (PRD §13.5):
  - hue = priority only, also shown as text and shape
  - "needs you" = ink inversion; stale = fade; dashed circle = Low
  - no toasts or modals for events
  - the list never re-sorts under the cursor
  - responder buttons ≥ 64 px with a 10 s undo
  - section headers use the PS's words: **Assignment · Facts · Timeline & evidence · Audit**
- **Copy:** the UI says "check-in due / contact overdue", "Checked", "Help assigned", "Reveal number (reason logged)". The UI never says "lease", "team silent", "verified", "help on the way", "agent" or "AI prioritised".
- **Names in data:** Indian units ("SDRF Boat 2", "Fire & Rescue Boat 5", "Fishermen boat · Jose (radio only)"), incidents `BR` (live), `OD`, `HP`; case IDs `BR-214`.
- **Tests:**
  - the 10 scenario tests T1–T10 (PRD §13.6) in `tests/scenarios/`, against the API with seeded data; tests move `expires_at` into the past rather than faking a clock
  - one API test per permission row + one IDOR test per resource
  - fixtures only, no live provider calls

## 6. How we work

2. Build the smallest thing that meets it. Stop and ask if it needs anything from the cut list, a new service, or a paid tier.
3. Run it, and show the human how to run it (command + what to look at).
4. The human runs it. Commit.
5. Update `docs/modules/<module>.md` (the 5-line explainer) and, if AI wrote something notable, note it for `AI_USAGE.md`.


## 7. Never say (UI, docs, commits, pitch)

"agentic" · "AI agent" · "triage agents" · "AI prioritises" · "22 languages" · "novel lease" · "tamper-proof" (say **tamper-evident**) · "national command" (say **a national layer of district desks**) · "₹0 tonight" · "dispatch NDRF" · "background heartbeat".

## 8. This repo also holds the planning folder

- **Zero budget** still applies: open source, self-hosting and free tiers only; state each choice's cost and free-tier limits (PRD §12.5).
- Verify any new factual or competitor claim before it goes into a doc, and tag it VERIFIED or UNVERIFIED.
- Don't use Ainna or other outside idea tools.
- Running notes for the build: `docs/STATUS.md` (DONE / NOT DONE / BLOCKED), `docs/DECISIONS.md`, `docs/modules/`, `docs/TEACHBACK.md`, `docs/MEASUREMENTS.md`.
