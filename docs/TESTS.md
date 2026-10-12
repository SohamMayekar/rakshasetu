# The scenario tests (PRD §13.6 T1–T10) and the IDOR tests (F-C9)

Every row runs in `make test`, against the real API (FastAPI TestClient) and the real SQL on a test database. A test
that needs time to pass moves the deadline, never a fake clock. Results below were first recorded at m53 and are
re-run on every milestone merge; the last full run (m61, 12 Oct 2026): **415 passed in 272 s**.

| # | What the PRD asks | Where | Result |
|---|---|---|---|
| T1 | The same report posted twice → one report; a replay returns the original id | `tests/scenarios/test_t1_idempotency.py` (5 tests, incl. keys namespaced by source, one case even if processed twice) | passed |
| T2 | Kill the worker mid-surge → integrity 0, no duplicate cases | `tests/scenarios/test_t2_worker_kill.py`: a real `python -m app.worker` (4 threads) on 300 synthetic surge reports, SIGKILLed after ≥ 75 are in cases (run: 76, with 4 jobs in its hands); its locks age past 60 s; then all 300 reports in exactly one case each, no lost or dead job, integrity 0, chain verifies | passed |
| T3 | The son's report from another phone → suggested with reasons; merge then undo restores the snapshot exactly | `tests/scenarios/test_t3_merge_undo.py` (4) | passed |
| T4 | Ramesh Das / Rajesh Das → two cases, nothing above "weak", the names shown | `tests/scenarios/test_t4_das_families.py` (2) | passed |
| T5 | 14 Excel-damaged phones → null, 0 auto-merges, counted | `tests/scenarios/test_t5_excel_damage.py`, and on the real 300-row sheet in `test_demo_sheet.py` | passed |
| T6 | Deadline passes → contact overdue, one team escalation, the case stays, the team greyed out; a radio contact restores it; heartbeats don't extend it | `tests/scenarios/test_t6_contact_overdue.py` (8) | passed |
| T7 | Two officers act on one escalation → the second gets a 409 naming who; the DB rejects a second open assignment | `tests/scenarios/test_t7_two_officers.py` (2: acknowledge and reassign by two officers; a raw INSERT of a second open assignment raises), plus two in T6 | passed |
| T8 | "4 taken, someone still there" → back at the top of P1 with 2 remaining and the original time | `tests/scenarios/test_t8_partial_rescue.py` (6, incl. two trips = "Rescued 6 of 6") | passed |
| T9 | On-site No → reopen P1; distant No → disputed, no auto-close; stranger rejected; silence closes | `tests/scenarios/test_t9_family_check.py` (4) | passed |
| T10 | Language model off / LLM error → a typed report becomes a case in ≤ 5 s; STT failure → "audio only" case | `tests/scenarios/test_t10_language_model_off.py` (4) and `tests/test_voice.py::test_stt_failing_completely_still_gives_an_audio_only_case` | passed |

| IDOR (one per resource) | Where | Result |
|---|---|---|
| Case (by public id and by numeric id; and a team lead) | `tests/test_idor.py` | passed |
| WebSocket (another district's events never arrive) and polling | `tests/test_idor.py` | passed |
| Evidence (another district's officer 404, a team lead not holding the case 404, totals-only 403) | `tests/test_idor.py::test_evidence_idor` | passed |
| Assignment (another team's lead, another district's team and officer: acknowledge, reached, release and rescue all refused; nothing changed) | `tests/test_idor.py::test_assignment_idor` | passed |

Also in the suite: one permission test per row of PRD §4.2 (`tests/test_permissions.py`), the demo spine replayed end to end (`tests/scenarios/test_demo_reset.py`), and the 300-row sheet against its ground truth (`tests/scenarios/test_demo_sheet.py`).

## The golden path, end to end (PRD §16.1, 0:00 → 3:05)

`make e2e` (`apps/web/e2e/golden.mjs`) resets the demo and drives the real screens on the running stack: the
officer's desk on `http://localhost`, the judge's phone and the team's phone on the public listener (as through
the tunnel), and the demo controls. **Last run (m62, English data, redesigned screens): 37 checks passed in 157 s**

reset to the start in 3.8 s → the son's clip becomes BR-199 (P1 · 6 people), on the desk 2.1 s later → hovering
"6" lights up "6 people are stuck on the roof" → the receipt says "recorded transcript (not a live STT call)" →
the forward is suggested, merged by the officer, the case checked → "BR-201 was not merged with BR-199: Rajesh ≠
Ramesh" → the 300-row sheet in 19.8 s → SDRF Boat 2 (the top suggestion, radio only) acknowledged on radio with
ETA 15 → 25 s of silence on the ×60 clock → "Contact overdue", the case still Boat 2's, one escalation →
reassigned to Fire & Rescue Boat 5 by the officer → the team's phone: New case, ETA 15, Reached, "4 taken, someone
still there" → "2 of 6 still there" back in the queue; Boat 2 (owes a stand-down) not suggested again → trip 2:
"2 taken, nobody left" → "Rescued 6 of 6" → the son's phone is asked "The team says 6 people were rescued. Is that
right?" → Yes → 7 evidence items, each ✓ against the audit log → "✓ 1,874 events verified" → the promise bar adds
up (343 reports = 252 cases + 91 merged + 0 to check + 0 without a home) → integrity 0 → the team lead opening
another case gets 403 "Not assigned to your team".

**Not exercised here:** the son speaking through the reporter page's microphone. With no speech-to-text key in this
sandbox a recorded voice can only become an "audio only" case, so the script plays the clip through the demo
control (the same voice pipeline) and says so in its output. With a key, the script feeds the clip into
Chromium's fake microphone on `/r` instead; that path has not been run (BLOCKED: no key).
