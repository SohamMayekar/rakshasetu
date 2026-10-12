# RakshaSetu build status

*Updated at every milestone merge. Three lists, never blurred together.*

**Current milestone:** m13 · permission + IDOR suite
**Started:** H0 = 12 Oct 2026, 16:26 IST (the first product-code commit follows the planning-only commit `246a19e`).

## DONE (verified)

| Milestone | What | The check that proved it |
|---|---|---|
| m02 | docker compose: db (PostGIS), api, worker, ticker, web; `make up/down/ps/logs` | `make up` → all 5 services healthy; /healthz reports db ok; `make test-api` passes in the container |
| m03 | Caddy :80 local / :8080 public; X-RS-Listener stamping; demo guard (listener + CF-Connecting-IP); body caps | `make smoke`: 9/9 listener checks (incl. spoofed header → 404, 3 MB public body → 413); 4 guard tests in pytest |
| m04 | Base schema (incidents, districts, teams, users, cases, reports, events); roles rakshasetu_owner / rakshasetu_app; `migrate` one-shot service; test DB | `make nuke && make up` applies 001_base; pytest: app role owns 0 tables, UPDATE/DELETE/TRUNCATE events + CREATE TABLE → InsufficientPrivilege, INSERT+SELECT events works (11 passed) |
| m05 | packages/contracts: report.v1 + extraction (closed enums, no priority, no summary) JSON schemas, ws-events.md, partner contract card, generated openapi.json; Pydantic mirrors | pytest: 26 agreement cases (schema and Pydantic accept/reject the same docs, incl. a priority field, summary_en, off-enum hazard, empty quote); openapi.json freshness test |
| m06 | Team-owned config: rakshasetu.config.yaml (PRD §9 values), roles.yaml (§4.2 matrix), flags.yaml, partners.yaml; validated loader; api fails at boot on a bad file | pytest: committed config loads; weights must sum to 1.0; heartbeat_extends_deadline and transitive_merges can't be turned on; P4 catch-all required; unknown keys refused |
| m07 | Seed loader (owner role, DEMO_MODE only): BR/OD/HP packs, 12 demo users, timestamps relative to the seed moment; deterministic BR case generator; phone protection (E.164, HMAC, Fernet, mask); scrypt passwords | `make seed` → 3 incidents, 57 cases, 15 teams, 12 users; pytest: radio-only + out-of-service BR teams, 40+ BR cases, newest < 1 h old, Low + needs-location cases present, sequential BR-151…, phones never in clear (67 passed) |
| m08 | Test harness: fixtures (seeded, owner_db, app_db, client, public_client), scenario/slow markers, tests/README.md; ruff in `make test` | `make test` → ruff clean + 67 passed in the container, against rakshasetu_test |
| m09 | append_event(): advisory lock, canonical TEXT body, sha256(prev‖body), pg_notify on commit; verify_chain(); seed writes chain.genesis + one event per seeded entity | pytest: canonical body + hash formula; rollback leaves no event; 200 concurrent appends → seqs contiguous and chain verifies; NOTIFY only after commit; a slow writer can't be overtaken (seq order = commit order) |
| m10 | GET /v1/audit/verify, /v1/audit/head (public), /v1/audit (filtered list); `make verify`, `make tamper SEQ=N` (scripts/tamper.sql as superuser) | pytest: verify ok after seed; head public = last event; verify/list 404 on public; body edit, column edit, actor swap → broken at that seq; delete → broken at next; forged row with recomputed hash → broken at next. Live: make tamper SEQ=12 → '✗ broken at #12'; reseed → ✓ 88 events |
| m11 | Real-time: one LISTEN → hub → WebSocket fan-out with ?since= back-fill and re-catch-up; GET /v1/events?since=; 25 s ping; case.updated coalesced to 1/s/case; incident filter (Scope arrives m12) | pytest: polling back-fill filtered by incident; live event on an open socket < 2 s; disconnect, 3 events, reconnect with since → exactly those 3; other incidents' events not sent; 5 case.updated → 2 sent. Live: WS works through Caddy :80 and :8080 |
| m12 | Cookie auth (signed user id, httpOnly, SameSite=Strict), role+scope reloaded per request, require(action) from roles.yaml, Scope.case_where/event_where in SQL; picker local-only; /v1/me; GET /v1/cases(+/{ref}) scoped; WS needs a session; JSON-only mutations; assignments table (one live per case) | pytest (104 passed): picker local-only, public needs password, forged cookie 401, role change applies without re-login, 415 on form posts, district-scoped case lists (Gopalganj/Muzaffarpur/admin), OD officer sees no BR case, SEOC 403 on queue, team lead 403 'Not assigned to your team', WS 4401 without session. Live through Caddy: public picker 401, public password 200, cookie HttpOnly |

## NOT DONE (engineering)

| What | Estimate |
|---|---|
| Everything from m02 onwards (PRD P0) | see the milestone plan in the build prompt |

## BLOCKED (credential or external)

| What | Variable / service | What it affects | How to verify once supplied |
|---|---|---|---|
| Overpass API unreachable from the build sandbox (the egress proxy drops the tunnel to overpass-api.de, its mirrors and Geofabrik) | `overpass-api.de` | `scripts/import_osm.py --source overpass` can't run here; the BR gazetteer is built from the openstreetmap.fr Bihar extract instead (real OSM data, ODbL; decision D6) | On a laptop with open internet: `python scripts/import_osm.py --source overpass` and compare counts with the committed extract |
| Git tags can't be pushed from this sandbox (the proxy answers 403 to tag refs; branches and main push fine) | GitHub via the session proxy | The `mNN` tags exist locally only | From a normal clone with this session's history: `git push origin --tags` |
| Speech-to-text keys | `SARVAM_API_KEY`, `GROQ_API_KEY` | Live STT. Without them the STT provider runs in fixture mode | Put the keys in `.env`, then `make provider-check` (arrives with m17) |
| LLM keys | `GROQ_API_KEY`, `GEMINI_API_KEY` | Live extraction. Without them the keyword path creates every case (chips read **Rule**) | Same |
| WhatsApp test number | `WHATSAPP_*` | P1 #5 only | — |

## For the humans to confirm

- **Demo village = Thawe, Gopalganj** (decision D5): Muzaffarpur's OSM data has no village with a mapped temple and bridge within 500 m. The pitch line changes from "[village], Muzaffarpur" to "Thawe, Gopalganj". Evidence in `data/scenarios/BR/README.md`.

## Environment notes for this build

- Docker Hub rate-limits anonymous pulls here (429), so base images come from `public.ecr.aws/docker/library/*` (the same official images, free, no account).
- Docker's daemon isn't started by default in this sandbox; it was started with `dockerd`.
