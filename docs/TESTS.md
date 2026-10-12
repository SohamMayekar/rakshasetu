# The scenario tests (PRD §13.6 T1–T10) and the IDOR tests (F-C9)

Every row runs in `make test`, against the real API (FastAPI TestClient) and the real SQL on a test database. A test
that needs time to pass moves the deadline, never a fake clock. Results below are from the m53 run (12 Oct 2026):
**all passed**.

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
