# RakshaSetu build status

*Updated at every milestone merge. Three lists, never blurred together.*

**Current milestone:** m06 · config loading
**Started:** H0 = 12 Oct 2026, 16:26 IST (the first product-code commit follows the planning-only commit `246a19e`).

## DONE (verified)

| Milestone | What | The check that proved it |
|---|---|---|
| m02 | docker compose: db (PostGIS), api, worker, ticker, web; `make up/down/ps/logs` | `make up` → all 5 services healthy; /healthz reports db ok; `make test-api` passes in the container |
| m03 | Caddy :80 local / :8080 public; X-RS-Listener stamping; demo guard (listener + CF-Connecting-IP); body caps | `make smoke`: 9/9 listener checks (incl. spoofed header → 404, 3 MB public body → 413); 4 guard tests in pytest |
| m04 | Base schema (incidents, districts, teams, users, cases, reports, events); roles rakshasetu_owner / rakshasetu_app; `migrate` one-shot service; test DB | `make nuke && make up` applies 001_base; pytest: app role owns 0 tables, UPDATE/DELETE/TRUNCATE events + CREATE TABLE → InsufficientPrivilege, INSERT+SELECT events works (11 passed) |
| m05 | packages/contracts: report.v1 + extraction (closed enums, no priority, no summary) JSON schemas, ws-events.md, partner contract card, generated openapi.json; Pydantic mirrors | pytest: 26 agreement cases (schema and Pydantic accept/reject the same docs, incl. a priority field, summary_en, off-enum hazard, empty quote); openapi.json freshness test |

## NOT DONE (engineering)

| What | Estimate |
|---|---|
| Everything from m02 onwards (PRD P0) | see the milestone plan in the build prompt |

## BLOCKED (credential or external)

| What | Variable / service | What it affects | How to verify once supplied |
|---|---|---|---|
| Overpass API unreachable from the build sandbox (the egress proxy drops the tunnel to overpass-api.de and mirrors) | `overpass-api.de` | `scripts/import_osm.py --source overpass` can't run here; the BR gazetteer is built instead from the openstreetmap.fr Bihar extract (real OSM data, same ODbL licence) | On a laptop with open internet: `python scripts/import_osm.py --source overpass` and compare counts with the committed extract |
| Speech-to-text keys | `SARVAM_API_KEY`, `GROQ_API_KEY` | Live STT. Without them the STT provider runs in fixture mode | Put the keys in `.env`, then `make provider-check` (arrives with m17) |
| LLM keys | `GROQ_API_KEY`, `GEMINI_API_KEY` | Live extraction. Without them the keyword path creates every case (chips read **Rule**) | Same |
| WhatsApp test number | `WHATSAPP_*` | P1 #5 only | — |

## Environment notes for this build

- Docker Hub rate-limits anonymous pulls here (429), so base images come from `public.ecr.aws/docker/library/*` (the same official images, free, no account).
- Docker's daemon isn't started by default in this sandbox; it was started with `dockerd`.
