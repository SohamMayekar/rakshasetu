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
