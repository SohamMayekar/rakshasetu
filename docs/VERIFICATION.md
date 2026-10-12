# Verification: what was checked, how, and what is left for people

*Release milestone m77 (the simplify run m63–m72 and the focus run m73–m77, on top of the m62 release), 12 Oct 2026. Every claim below names the command or test that shows it. Numbers are measured (`docs/MEASUREMENTS.md`); nothing is estimated. All people and phone numbers are synthetic. What changed for the judge (three profiles, plain words, fewer things per screen) is in §9 and `docs/SIMPLIFY_PLAN.md`.*

## 1. The stop conditions

| Condition | Result | How |
|---|---|---|
| `make up`, `make seed`, `make test` on the final code (m77) | ✓ **419 passed in 213 s** (415 at m62 + 1 realtime reconnect + 2 sign-in profiles + 1 worker reconnect); the m62 fresh-clone check: **415 passed**, on a clean checkout in its own Docker project with an empty database (one sandbox-only step: its proxy's CA certificate) | §8 |
| `make demo-reset` works | ✓ to the start in **2.4 s** (m77); every scene resets on its own (D7 drill: "The rescue" in 25.8 s) | `make e2e`, `make drills` |
| `/v1/audit/verify` ✓ after the golden path | ✓ **"1,870 events verified"** (m77) | `make e2e` ("History → Check nothing was changed") |
| `/v1/integrity` = 0 after the golden path | ✓ **0 problems** (1,870 events verified) | `make e2e` ("integrity: 0 problems") |
| main is clean and tagged | milestones m01–m77 merged with `--no-ff`; tags `m01`…`m77` exist locally. **The tags could not be pushed** (the sandbox proxy refuses tag refs: BLOCKED in `docs/STATUS.md`) | `git log --first-parent main`, `git tag` |

## 2. The 9 required components (PRD §7): where the judge sees each, and what proves it

| # | Component | In the demo (PRD §16.1) | Proved by |
|---|---|---|---|
| 1 | **Incident lifecycle** | the case panel's status line moves "Waiting for a team" → "has it: accepted" → "contact overdue" → "2 of 6 still there" → "Rescued 6 of 6"; three incidents on All incidents (the Demo admin's home) | `tests/test_incidents.py`, `tests/test_case_edits.py`, T8, T9; the golden path follows BR-199 through every state |
| 2 | **Role/permission system** | three profiles, three surfaces (desk, team app, demo controls); the team lead's **403** ("Not your team's case") on another team's case; nine more roles and districts seeded for the tests (D22) | `tests/test_permissions.py` (one test per PRD §4.2 row), `tests/test_idor.py` (one per resource), `tests/test_auth.py`; the golden path's last check (403 "Not assigned to your team") |
| 3 | **Event ingestion API** | the son's request from a phone (0:00), a pasted forward with New report (0:50), the 300-row sheet (1:15); on a judge's question, `make surge` and `make partner-demo` | `tests/test_ingest_channels.py`, `tests/test_voice.py`, `tests/test_imports.py`, `tests/test_import_job.py`, `tests/test_surge.py`, `tests/test_partners.py`, T1, T5; one code path, `intake.accept()` |
| 5 | **Task assignment** | the row's and the panel's "Send SDRF Boat 2"; "Send another team" → Fire & Rescue Boat 5; the team's phone shows the new case full screen | `tests/test_assignments.py`, `tests/test_dispatch.py`, T7; the golden path's assign, reassign and trip checks; measured 1.3 s to the phone (m44) |
| 6 | **Escalation** | the radio boat's ETA passes → **contact overdue** → one alert above the list ("Open BR-199") → greyed out → the case stays → the officer sends another team | T6 (8 tests), T7; the golden path's "Contact overdue", "still Boat 2's" and escalation checks; measured 0.21 s from the deadline (m41) |
| 7 | **Evidence references** | in Timeline & evidence (one click): the voice clip + transcript, the forward, the sheet row, the merge record, the radio log, two rescue records with the team's position, each "✓ unchanged since it was saved" | `tests/test_evidence.py`; the golden path: **7 items, each "✓ matches the audit log"** |
| 8 | **Audit trail** | History → **Check nothing was changed**: "✓ 1,870 events verified: nothing was changed"; the tamper demo breaks it at the edited entry; the panel's Audit section links the case's history | `tests/test_eventlog.py`, `tests/test_audit_tamper.py`, `tests/test_db_roles.py`; the golden path's Verify; drill D6 |
| 9 | **Real-time updates** | the judge's phone gets the case and later "Is that right?"; the desk updates on the team's taps | `tests/test_realtime.py`, `tests/test_status_page.py`; the golden path (on the desk 2.1 s after the clip; the phone asked after the rescue); drills D2, D3 |

## 3. The scenario tests T1–T10 and the IDOR tests
All in `make test`; the last full run (m77) **419 passed in 213 s**. Each row's file and what it asserts: `docs/TESTS.md`.

| T1 idempotency | T2 worker killed mid-surge | T3 merge + undo | T4 the Das families | T5 Excel-damaged phones |
|---|---|---|---|---|
| passed | passed (a real worker process, SIGKILLed) | passed | passed | passed |
| **T6 contact overdue** | **T7 two officers** | **T8 partial rescue** | **T9 the family's check** | **T10 language model off** |
| passed | passed | passed | passed | passed |

IDOR: case, WebSocket and polling, evidence, assignment: all passed.

## 4. The golden path, end to end (PRD §16.1, 0:00 → 3:05)

|---|---|
| `01-desk-the-case-arrives`, `01-phone-the-son` | "Thawe · 6 people · Urgent · BR-199" at the top of *Needs you now*; the son's status page in one sentence |
| `02-desk-the-sons-words-light-up` | hovering "6" lights up "6 people are stuck on the roof"; method chips; the circle's sentence |
| `03-desk-the-forward-is-suggested`, `04-desk-rajesh-is-not-ramesh` | never doubled: merged with reasons; refused with the names |
| `05-desk-the-volunteer-sheet` | "300 rows → 188 new cases · 90 merged · 14 to check · 0 dropped …" |
| `06`–`08` (desk) | accepted on radio, the clock 60× faster · contact overdue, the case stays · another team sent: Boat 5 |
| `09-phone-new-case`, `10-phone-rescue-sheet-sent`, `10-desk-2-of-6-still-there` | the team's phone; "4 taken, someone still there" → back to the top |
| `11-phone-the-family-is-asked`, `11-desk-confirmed-by-family` | "The team says 6 people were rescued. Is that right?" → Yes |
| `12-desk-timeline-and-evidence`, `13-desk-chain-verified`, `14-phone-403-not-your-team` | the receipts, History's check, "Not your team's case" |



## 5. Failure drills
`make drills`: **14 of 14 passed** on the final code (m77): worker crash mid-surge, desk cut off for 30 s, API restart, tiles down, language model off, tamper, scene reset (numbers in `docs/DRILLS.md`).

## 6. DONE / NOT DONE / BLOCKED (summary; the full lists are in `docs/STATUS.md`)
- **DONE:** milestones m01–m77 (m63–m72: the simplify run; m73–m77: the focus run; §9). All 9 components, T1–T10, the IDOR tests, the golden path, the drills; partner annotations, the partner log and signed webhooks with the contract card. P1 items #1 (a merge tightens the circle, with pin precedence), #2 (the officer's priority call with a reason), #3 (a rescue record says where the team was and how far from the pin), #7 (an installable team app with Wake Lock and an offline list), #11 (phone placeholders before the model, instruction-like words flagged) and #13 (the partner log), plus parts of #12 (the empty-queue line; 409s that name who and when). English-only screens (D17); the redesign (D18).
- **NOT DONE:** P1 items #4, #6, #8 (the capacity-gap header exists, bulk approve doesn't), #9, #10 and the rest of #12. The reporter's "not sent yet" state keeps the clip only in memory. Known dependency advisories need major upgrades (maplibre-gl 6, Next 16). The database restart is not drilled.
- **BLOCKED (needs a credential or the outside world):** live STT and LLM calls (no keys); WhatsApp, P1 #5 (no Meta test number); the Overpass API (unreachable from the sandbox, so the gazetteer came from the openstreetmap.fr extract, D6); pushing git tags (the proxy refuses them).

## 7. For the humans: before the demo
1. **Keys.** Put free-tier keys in `.env` (`SARVAM_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`; no inline comments), then `make up` and `make provider-check`, which should print one `OK` per provider. Then `make sheet-eval` should read "AI asked about 19", and `make e2e` will drive the microphone path instead of the recorded clip.
2. **Record real voices** into `data/scenarios/BR/clips/`: the son's line (README there; the shipped one is a synthetic espeak-ng voice) and the rehearsed judge inputs. With keys, no transcript file is needed. Never present a fixture as live.
3. **Record the reply clip (H-05):** "Your report is registered. You don't need to remember anything." → `apps/web/public/audio/en/registered.mp3`.
4. **Confirm the demo village:** Thawe, Gopalganj (D5). The pitch line says "Thawe, Gopalganj", not Muzaffarpur.
5. **Set `PUBLIC_URL`** to the tunnel's address on the day (the phones open it, and the webhook media links use it). Change `SECRET_KEY` and the database passwords from their dev values.
6. **Run the team app on a real mid-range Android phone over mobile data** through the tunnel (PRD F-C7 "done when"); only Chromium's phone viewport has been run.
7. **Measure the desk on the demo laptop** during `make surge` (with a GPU): click 10 rows and check < 100 ms; the sandbox only had software WebGL (19–165 ms).
8. **A partner team:** give them `packages/contracts/PARTNER_CONTRACT_CARD.md`, add their row to `config/partners.yaml` with their own secret, and set their webhook URL's env var. To rehearse without one: `make webhook-sink` + `DEMO_PARTNER_WEBHOOK_URL=http://api:9009/hook`, and `make partner-demo`.
9. **Decide the open question** in `docs/STATUS.md` (district-only repeat reports are never suggested; PRD F-D1 minimum evidence).
10. **Push the tags** from a normal clone: `git push origin --tags`.

**On stage, say** (the script is `docs/DEMO.md`): the people and phone numbers are synthetic and the places are real; the demo clock runs 60× faster; the surge is pre-structured reports; the demo partner is simulated by us; a recorded clip is a recording.

## 8. Fresh-clone check
A clean `git clone` of the release branch (commit `7df4cb9`, the content merged as m62) into an empty folder, run as its **own Docker Compose project** (`COMPOSE_PROJECT_NAME=rsfresh`: new images, an empty database volume) with the main stack stopped, 12 Oct 2026:

| Step | Result |
|---|---|
| `make up` (`make env` copies `.env.example`; builds and starts db, migrate, api, worker, ticker, web, caddy) | ✓ healthy in **1 min 49 s** |
| `make seed` | ✓ in **6.1 s**: 3 incidents, 57 cases, 24 teams, 12 users, 32 P1 cases with owners |
| `make test` (copy rules, ruff, the API suite) | ✓ **415 passed in 279 s** |
| `make demo-reset SCENE=son`, then `make verify` | ✓ reset in **5.0 s**; **"✓ 223 events verified"** |

**One environment step was needed in this sandbox, and only here:** its network intercepts TLS, so the fresh clone's Docker build couldn't reach PyPI until the sandbox's CA certificate was copied into `infra/certs/` (`*.crt` there is git-ignored by design; `infra/certs/README.md`). The first attempt without it failed at `pip install` with "self-signed certificate in certificate chain". On a laptop with normal internet that folder stays empty and nothing else is needed.

## 9. The simplify run (m63–m72): what a judge sees now
Three people on the sign-in screen (Duty officer, Rescue team, Demo admin); a front door with two choices (I need help · Control room dashboard); plain words on every screen (`apps/web/lib/words.ts`; `make copy-check` refuses the jargon); the desk with three promises as sentences, Needs you now and the map; the case panel with a summary and one next step over the PS's four sections; three places in the sidebar (Desk · History · Demo); one thing to do on each phone screen; `/demo` as a numbered walk with Next scene. Nothing was deleted: every capability is still one or two clicks away, and every test still runs.


| Screen | 1366×768 | phone 390×844 |
|---|---|---|
| `/` signed out (front door) | 3 → 8 (two big choices + the team link) | 3 → 5 |
| `/login` | 12 → **6** (3 profiles) | 13 → **6** |
| `/` signed in | Incidents 36 → the duty officer goes straight to the desk; the Demo admin's All incidents 58 | 29 → desk; 43 |
| `/desk/BR` | 71 → **62** | 59 → **45** |
| case panel (`?case=BR-199`) | 105 → **76** | 109 → **59** |
| `/audit` → History | 123 → **76** | 62 → **48** |
| `/partners` (inside Demo) | 22 → 20 | 12 → 11 |
| `/surge` (inside Demo) | 54 → **36** | 43 → **30** |
| `/demo` (Demo admin) | 51 → **37** | 33 → **22** |
| `/r` | 8 → 10 (the text box and Send are on screen, not behind "Type instead") | 8 → 10 |
| `/s/BR-199` | 12 → 14 (one sentence, the steps folded) | 12 → 14 |
| `/responder` (a new case on screen) | 16 → 18 (each card has its next action) | 16 → 18 |
| `/responder/case/58` | 14 → 14 | 15 → 14 |

### The focus run (m73–m77)

| Screen | m72 → m77 at 1366×768 | phone |
|---|---|---|
| `/desk/BR` | 62 → 62 (the promise sums became three numbers) | 45 → 49 |
| All incidents | 58 → **39** | 43 → **32** |
| case panel | 76 → 76 | 59 → 63 |
| History | 76 → 82 (a one-line header lets more entries into view) | 48 → 50 |
| Show it under load | 36 → **32** | 30 → **26** |
| `/demo` | 37 → 36 | 22 → 22 |

Bug found by the m73 gate and fixed: a worker thread died when Postgres was still starting up after a restart and never retried, so new reports would have sat unread (`tests/test_worker_reconnect.py`).
