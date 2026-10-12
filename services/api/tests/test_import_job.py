"""The import job (PRD F-D3 steps 4–8): the spreadsheet channel's integration test.
Every row ends somewhere a person can see, the summary equals the database, and re-running loses or
doubles nothing."""

from sqlalchemy import text

from app.core.jobs import drain
from app.modules.imports.job import run_import
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one, rows

pytestmark = [needs_db]

SHEET = "\n".join([
    "S.No,Naam,Mob,Kitne log,Gaon,Location,Remarks,Samay,Status",
    "1,Sita Devi,98765 61001,6,Kalu Chhapra,school ke paas,\"chhat par, dawai chahiye\",,",
    "2,Sita Devi,98765 61001,6,Kalu Chhapra,school ke paas,chhat par,,",     # the same household again
    "3,Mohan Yadav,9.19877E+11,4,Katiya,,paani ghus gaya,,",                 # phone damaged by Excel
    "4,Gita Kumari,9.19877E+11,4,Katiya,,paani ghus gaya,,",                 # same damaged phone, other family
    "5,Ram Prasad,98765 61002,3,,,help chahiye,,",                           # nowhere to put it
    "6,Kamla Devi,98765 61003,2,Bhore,,,,done",                              # already rescued
    ",,,,,,,,",                                                              # a blank row (row 8)
    "9,,,,,,,,",                                                             # only a serial number
    "10,Suresh Ram,98765 61004,5,Nautan,,chhat par,01/01/2026 10:00,",       # an old report
]).encode() + b"\n"


def _import(client, app_db, data=SHEET):
    imp = client.post("/v1/imports", files={"file": ("relief.csv", data, "text/csv")}, data={"incident": "BR"}).json()
    r = client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": imp["proposed"]})
    assert r.status_code == 200, r.text
    drain(app_db)
    return client.get(f"/v1/imports/{imp['id']}").json()


def test_a_sheet_imports_row_by_row_and_the_summary_is_the_database(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    imp = _import(client, app_db)
    assert imp["status"] == "done", imp
    assert (imp["rows_total"], imp["new_cases"], imp["merged"], imp["to_check"], imp["history"], imp["dropped"]) == \
           (8, 3, 1, 2, 1, 1)
    assert (imp["rules_read"], imp["ai_asked"], imp["phones_damaged"]) == (7, 0, 2)
    assert imp["summary"] == ("8 rows → 3 new cases · 1 merged · 2 to check · 1 dropped · 1 already done (closed history)"
                              " · rules read 7, AI asked about 0 · 2 phone numbers damaged by Excel, not used")

    sha = imp["file_sha256"]
    reports = rows(app_db, "SELECT id, case_id, received_at, reporter_phone_hash FROM reports"
                           " WHERE source_ns = 'sheet' AND idempotency_key LIKE :k ORDER BY id", k=f"{sha}:%")
    assert len(reports) == 7 and all(r.case_id for r in reports)                      # never lost
    ev = rows(app_db, "SELECT sha256, (meta->>'row')::int AS row, meta->'cells'->>'Naam' AS naam FROM evidence"
                      " WHERE type = 'sheet_row' AND sha256 = :s ORDER BY 2", s=sha)
    assert [e.row for e in ev] == [2, 3, 4, 5, 6, 7, 10] and ev[0].naam == "Sita Devi"   # file hash + row + raw row
    assert one(app_db, "SELECT count(*) FROM merges m JOIN reports r ON r.case_id = m.target_case_id"
                       " WHERE m.decided_by = 'rule' AND r.idempotency_key LIKE :k", k=f"{sha}:%") >= 1
    assert one(app_db, "SELECT count(*) FROM cases WHERE 'closed_from_sheet' = ANY(flags) AND status = 'closed'") == 1
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'import.progress'") >= 1
    done = rows(app_db, "SELECT body::jsonb->'data' FROM events WHERE action = 'import.completed'")
    assert len(done) == 1 and done[0][0]["summary"] == imp["summary"]

    by_row = {r["row_number"]: r for r in client.get(f"/v1/imports/{imp['id']}/rows").json()}
    assert sorted(by_row) == [2, 3, 4, 5, 6, 7, 9, 10]                                  # row 8 was blank
    assert by_row[3]["outcome"] == "merged" and by_row[3]["reason"].startswith("Merged into BR-")
    assert by_row[4]["flags"] == ["phone damaged by Excel"]
    assert by_row[5]["outcome"] == "new" and by_row[5]["reason"].startswith("Not merged with BR-")   # Mohan ≠ Gita
    assert by_row[6]["outcome"] == "to_check" and "no location" in by_row[6]["reason"]
    assert by_row[7]["outcome"] == "history"
    assert by_row[9]["outcome"] == "dropped" and by_row[9]["reason"] == "row has nothing in its mapped columns"
    assert by_row[10]["outcome"] == "to_check" and "old report" in by_row[10]["reason"]
    # The headcount came from its column, labelled as a rule reading the sheet.
    prov = one(app_db, "SELECT c.provenance->'people_count' FROM cases c JOIN reports r ON r.case_id = c.id"
                       " WHERE r.idempotency_key = :k", k=f"{sha}:2")
    assert prov["value"] == 6 and prov["method"] == "rule" and prov["source"] == "sheet column"


def test_the_same_file_again_doubles_nothing_and_a_rerun_resumes(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    first = _import(client, app_db)
    cases = one(app_db, "SELECT count(*) FROM cases")
    again = _import(client, app_db)
    assert (again["already"], again["new_cases"], again["merged"], again["dropped"]) == (7, 0, 0, 1)
    assert "7 already imported" in again["summary"]
    assert one(app_db, "SELECT count(*) FROM cases") == cases
    # A reclaimed job re-runs the same import: finished rows are skipped, the counts don't change.
    with app_db.begin() as c:
        c.execute(text("UPDATE imports SET status = 'running' WHERE id = :i"), {"i": first["id"]})
    run_import(app_db, {"import_id": first["id"]})
    assert one(app_db, "SELECT count(*) FROM cases") == cases
    assert client.get(f"/v1/imports/{first['id']}").json()["new_cases"] == first["new_cases"]


def test_a_running_import_cannot_be_remapped(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    imp = _import(client, app_db)
    r = client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": imp["proposed"]})
    assert r.status_code == 409


def test_only_rows_the_rules_cannot_read_go_to_the_language_model(seeded, client, app_db):
    """Rules first; a row with no place goes to the model afterwards. (The model's answer here comes from the
    extraction cache, recorded for this test, so no key or network is needed.)"""
    import hashlib

    from app.contracts import Extraction, Village
    register_handlers()
    row_text = "Remarks: Thave ke uttar wale tole mein ghar doob gaya"
    ex = Extraction.empty("hi").model_copy(update={"location": Extraction.empty().location.model_copy(update={
        "village_or_locality": Village(original="Thave", latin="Thawe", quote="Thave")})})
    with app_db.begin() as c:
        c.execute(text("INSERT INTO extraction_cache (text_sha256, provider, model, result)"
                       " VALUES (:h, 'test-fixture', 'recorded', CAST(:r AS jsonb))"),
                  {"h": hashlib.sha256(row_text.encode()).hexdigest(), "r": ex.model_dump_json()})
    login(client, "priya")
    sheet = b"Mob,Kitne log,Gaon,Remarks\n98765 63001,4,Kalu Chhapra,chhat par\n98765 63002,,,Thave ke uttar wale tole mein ghar doob gaya\n"
    imp = _import(client, app_db, sheet)
    assert (imp["rules_read"], imp["ai_asked"]) == (1, 1)
    assert "rules read 1, AI asked about 1" in imp["summary"]
    by_row = {r["row_number"]: r for r in client.get(f"/v1/imports/{imp['id']}/rows").json()}
    assert by_row[2]["read_by"] == "rules" and by_row[3]["read_by"] == "ai"
    receipt = one(app_db, "SELECT receipt FROM reports WHERE idempotency_key = :k", k=f"{imp['file_sha256']}:3")
    assert receipt[0] == {"step": "extract", "by": "AI", "detail": "1 fields · cached result of test-fixture/recorded"}
    assert one(app_db, "SELECT c.location_text FROM cases c JOIN reports r ON r.case_id = c.id WHERE r.idempotency_key = :k",
               k=f"{imp['file_sha256']}:3") == "Thawe"


def test_model_batches_wait_while_live_voice_reports_are_queued(seeded, app_db):
    import time as _t

    from app.core.jobs import enqueue
    from app.modules.imports.job import wait_for_live_voice

    class FakeRun:
        ticks = 0

        def progress(self, force=False):
            FakeRun.ticks += 1

    t0 = _t.monotonic()
    wait_for_live_voice(app_db, FakeRun(), max_s=2)
    assert _t.monotonic() - t0 < 0.5                                   # nothing waiting: no delay
    with app_db.begin() as c:
        enqueue(c, "report.process", {"report_id": 0}, "live_voice")
    t0 = _t.monotonic()
    wait_for_live_voice(app_db, FakeRun(), max_s=1.5)
    assert _t.monotonic() - t0 >= 1.4 and FakeRun.ticks >= 1          # held back, lease kept fresh
