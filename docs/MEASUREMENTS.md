# Measurements

Only numbers we measured go here, each with how and where it was measured. Nothing is estimated.

## Spreadsheet import · the 300-row demo sheet (m31)

| What | Measured | Target (PRD) |
|---|---|---|
| Time to import 300 rows (job start → done, `imports.finished_at − started_at`) | **16.6 s** | ≤ 45 s |
| Rows whose outcome matches the ground truth | **300 / 300** | — |
| Automatic merges: pairwise precision | **1.000** (0 wrong merges) | never a wrong merge |
| Automatic merges: pairwise recall | **0.965** (110 of 114 same-household row pairs) | — |
| Summary line | 300 rows → 188 new cases · 90 merged · 14 to check · 0 dropped · 8 already done (closed history) · rules read 300, AI asked about 0 · 14 phone numbers damaged by Excel, not used | equals the database (tested) |

- **How:** `make sheet-eval` (`tests/scenarios/test_demo_sheet.py`): the real API and job, the test database seeded with the BR/OD/HP packs, `PROVIDER_MODE=fixture` and no keys, so **no language model was called** ("AI asked about 0"). With keys, the 19 rows the generator marks `needs_ai` (no headcount the rules can read) go to the model instead; that run has **not** been measured yet.
- **Where:** the Docker Compose stack on a cloud VM (4 vCPU Intel Xeon 2.8 GHz, 15 GB RAM), 12 Oct 2026, at commit after `607cde0` (milestone 31).
- **The 4 missed pairs** are the four households whose second row has an Excel-damaged phone: they are shown to a person as likely duplicates ("to check"), by design (T5).
- **Ground truth** is the generator's own record of which household each row is (`data/scenarios/BR/sheet/ground_truth.csv`), so this measures the importer against a synthetic sheet built to look like a real one, not against real field data.

## Live update to an open desk (m33)

| What | Measured | Target (PRD F-C10) |
|---|---|---|
| `POST /v1/ingest/desk` → the new case is on an open desk (Chromium, list count changed) | **0.84 s** (one run) | ≤ 2 s |

- **How:** a throwaway Playwright script: sign in as priya, open `/desk/BR`, wait for "Live", post a desk report, time until the case count changes. It includes the worker's processing (keyword path, no language model), the WebSocket, and the desk's 1-second render frame. A repeatable version joins the golden-path test (m55).
- **Where:** same stack and VM as above, 12 Oct 2026, milestone 33.

## The call-taker's form (m37)

| What | Measured | Target |
|---|---|---|
| Hindi demo report typed into the desk form → its case selected on the desk | **2.2 s** (one run) | ≤ 5 s with the language model off (F-C14) |
| The son's pasted forward → shown as "Likely same household as BR-199 (strong)" | **1.8 s** (one run) | — |

- **How:** a throwaway Playwright script driving the real form in Chromium (Save → the column shows the case). Keyword path (no keys), local stack, same VM, 12 Oct 2026. The golden-path test (m55) will repeat these on every run.

## The demo sheet through the desk's side sheet (m38)

| What | Measured | Target |
|---|---|---|
| Confirm mapping → the 300-row summary on screen (live worker, Chromium) | **16.2 s** (one run) | ≤ 45 s |
| "Needs you now" after the import | 40 → 55 rows (14 to check + 1 sheet row); the pill read "▲ 15 new: show" | — |

## Deadline → escalation (m41)

| What | Measured | Target (PRD F-S2) |
|---|---|---|
| A passed check-in deadline → its team escalation opened (live ticker, demo clock) | **0.21 s** (one run; by design at most one 5 s tick) | ≤ 6 s |

- **How:** a desk report on the live stack, assigned to Fire & Rescue Boat 5 (demo clock: 10 s to acknowledge), then `escalations.opened_at − assignments.next_contact_due` from the database. 12 Oct 2026, milestone 41.

## Responder app (m44)

| What | Measured | Target (PRD F-C4) |
|---|---|---|
| Officer's Assign (API) → the full-screen "New case" card on the team lead's phone (Chromium, 390×844) | **1.3 s** (one run) | ≤ 2 s on desk and responder |
| ETA chip tapped → "Sent" (includes the deliberate 10 s Undo window) | **12.8 s** after the assignment (one run) | — |

- **How:** a throwaway Playwright script with two browser contexts (officer API session + the phone). Local stack, 12 Oct 2026, milestone 44. Not yet measured on a real mid-range Android phone over mobile data (PRD F-C7 "done when"): that needs the humans and the tunnel.

## Surge: 3,000 synthetic partner reports at 50 a second (m49)

| What | Measured | Target |
|---|---|---|
| Reports accepted | **3,000 of 3,000** (all 202), 50.0/s for 60.0 s | — |
| Time to say "received", inside the server (the surge screen, 60 s window mid-surge) | p50 **22–29 ms**, p95 **52–89 ms**, p99 **79–285 ms** (five runs on a warm stack); one run started straight after a rebuild: p95 **253–302 ms** | the screen shows ingest p95 (F-C5) |
| Same, from the generator (client side, same machine) | p50 **24.6–26.2 ms**, p95 **56.8–83.5 ms**, p99 **85.8–252.9 ms** (two runs) | — |
| Reading them: one worker, 4 threads, rules only | **~25 reports/s**; the backlog drained **58–66 s** after the last report (three runs) | — |
| Wrong automatic merges (a case holding two of the generator's households, by phone) | **0** of 299–331 merges | 0 |
| Repeat reports left as a separate case | BR: 124 households (village-only: D10 makes these strong "to check" suggestions); OD/HP: 91 (district-only: no suggestion at all, PRD F-D1 minimum evidence) | — |
| Promise bar after the backlog drained (BR) | 2,414 reports = 2,115 cases + 299 merged + 0 to check + 0 without a home ✓ · 3,503 to check · 2,328 kept apart | adds up |
| Integrity after the surge | **0 problems**, 12,652 events verified | 0 |
| Reseed with 857 jobs still waiting | **7.2 s**, integrity 0 (before the m49 fix: failed with a deadlock) | — |

- **How:** `make seed`, `make surge` (50/s, 60 s) on the local stack, `/surge` open in headless Chromium; numbers from `/v1/metrics/surge`, the generator's printout and the database. Same VM for everything, 12 Oct 2026.
- **The integrity check costs ~0.8 s of the API's CPU at 14,000 events.** Polled every 10 s during a surge, it pushed ingest p95 to **~810 ms**, so the surge screen now runs it only on request.

## The desk with 2,000+ open cases (m49)

| What | Measured | Target (PRD §15) |
|---|---|---|
| `GET /v1/queue` (2,800 open cases, 7,000 suggestions) | **3.2 s → 0.32 s** with migration 016 | — |
| Click a queue row → the case drawer in the DOM, no surge, 2,128 open cases | before m49: **1.7–2.8 s**; after: **16–70 ms** (8 + 8 clicks) | < 100 ms |
| Same, **during** a 50/s surge, 2,145 open cases | before the m49 desk fixes: **23–310 ms**; after: **19–165 ms**, 10 of 12 under 100 ms | < 100 ms |
| Main thread during a surge (8 s CPU profile) | before: busy ~7.5 s of 8 (59 long tasks); after: idle 5.6 s (9 long tasks of 130–210 ms) | — |

- **How:** throwaway Playwright scripts: clicks timed with `performance.now()` from `click()` to the drawer's `aside` changing, and a CDP CPU profile. Headless Chromium at 1366×768 with **software WebGL** (no GPU in this sandbox). Our own JavaScript is ~0.3 s of the 8 s profile; the remaining long tasks are native browser work, which looks like the map canvas being composited in software. **Not yet measured on the demo laptop with a GPU** (NOT DONE).

## Demo resets (m50)

| What | Measured | Target (PRD F-C12) |
|---|---|---|
| `make demo-reset` (the start: wipe + seed + 57 cases through the pipeline) | **3.4–3.7 s** (8 runs) | < 10 s |
| Reset to "Never doubled" / "The volunteer sheet" | **4.5 s** / **4.6 s** | each scene on its own |
| Reset to "Never stale", "The rescue", "The receipts" (each replays the 300-row sheet) | **20.5–22.7 s** (the import is 15.5–17.5 s of it) | each scene on its own |
| Same from the /demo page in Chromium (click → the result line) | **21.1–21.6 s** to "The rescue" | — |

- **How:** `make demo-reset SCENE=<id>` printing its own timings, and a throwaway Playwright script clicking "Reset here". Local stack, 12 Oct 2026.

## Evidence files on every text report (m52)

| What | Measured | Before |
|---|---|---|
| Surge at 50/s, inside the server, with each report's message stored as a hashed file | p50 **33.4 ms**, p95 **73.8 ms**, p99 **126 ms** (one run, 30 s) | p50 22–29 ms, p95 52–89 ms (m49) |
| Same, from the generator | p50 **38.9 ms**, p95 **83.9 ms**, p99 **142 ms** | p50 24.6–26.2 ms, p95 56.8–83.5 ms |

## The final code (m59–m62): English data, the redesigned screens, partner webhooks

| What | Measured | Target |
|---|---|---|
| The golden path, end to end (`make e2e`, 37 checks) | **157 s**, all passed | the 3:05 demo script, with real waits |
| Demo reset to the start | **3.8 s** | < 10 s |
| The son's clip finished → BR-199 on the desk | **2.1 s** | ≤ 2 s across screens (F-C10): just over, once; earlier runs 1.9–2.4 s |
| The 300-row sheet, English, through the desk (confirm → summary) | **19.8 s**; 300/300 rows agree with the ground truth, 0 wrong merges (test: 18.5 s) | ≤ 45 s |
| "✓ events verified" after the golden path | **1,874** events, integrity **0** | the chain verifies |
| Webhook delivery, worker → a receiver on the same machine (partner log, 8 deliveries) | **23–40 ms** each, every signature ✓ at the receiver | — |
| The API suite (`make test`, m61) | **415 passed in 272 s** | all |
| Failure drills (`make drills`, m62) | **14/14** in 151 s (numbers in `docs/DRILLS.md`) | all |

- **How:** the commands named, on the same Docker Compose stack and VM as above, 12 Oct 2026. The webhook timing is local (no network between worker and receiver), so it measures our side only.
- **Not measured:** anything on a real phone, over a real tunnel, on the demo laptop, or with a live STT/LLM call (no keys here). See `docs/VERIFICATION.md` § "For the humans".
