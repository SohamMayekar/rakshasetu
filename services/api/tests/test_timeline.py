"""The drawer's Timeline & evidence (PRD F-C2, F-C11): plain lines in order, evidence with hash checks, and
evidence files only inside the caller's scope (IDOR)."""

import os
import uuid

from app.core.jobs import drain
from app.core.storage import path_for
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = [needs_db]


def _sheet_case(client, app_db):
    """Import a two-row sheet (one household twice) and return (case public id, file sha, file bytes)."""
    tag = uuid.uuid4().hex[:6]                         # unique bytes: this test may damage its own file
    data = (f"Naam,Mob,Kitne log,Gaon,Location,Remarks,Ref\n"
            f"Sita Devi,98765 64001,6,Kalu Chhapra,school ke paas,chhat par,{tag}\n"
            f"Sita Devi,98765 64001,6,Kalu Chhapra,school ke paas,dawai chahiye,{tag}\n").encode()
    imp = client.post("/v1/imports", files={"file": ("t.csv", data, "text/csv")}, data={"incident": "BR"}).json()
    client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": {**imp["proposed"], "Ref": "ignore"}})
    drain(app_db)
    pid = one(app_db, "SELECT c.public_id FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.idempotency_key = :k",
              k=f"{imp['file_sha256']}:2")
    return pid, imp["file_sha256"], data


def test_the_timeline_reads_in_order_with_folded_cases_and_sheet_evidence(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    pid, sha, data = _sheet_case(client, app_db)
    client.post(f"/v1/cases/{pid}/check", json={})
    t = client.get(f"/v1/cases/{pid}/timeline").json()
    lines = [e["line"] for e in t["events"]]
    assert [e["seq"] for e in t["events"]] == sorted(e["seq"] for e in t["events"])
    assert any(x.startswith("Merged into") or "folded into" in x for x in lines), lines   # row 3 folded into row 2
    assert sum(x.startswith("Case BR-") for x in lines) == 2                                  # both cases' history
    assert lines[-1] == "Checked by Priya Kumari"
    received = [e for e in t["events"] if e["type"] == "report.received"]
    assert len(received) == 2 and all(e["report_id"] for e in received)                    # both reports, with their cards
    assert lines[0] == "Report received (spreadsheet)"
    rows = [e for e in t["evidence"] if e["type"] == "sheet_row"]
    assert sorted(e["meta"]["row"] for e in rows) == [2, 3]
    assert all(e["sha256"] == sha and e["file_ok"] and e["chain_ok"] for e in rows)
    merge = [e for e in t["evidence"] if e["type"] == "merge"]
    assert merge and merge[0]["meta"]["line"].startswith("Merged into")

    r = client.get(f"/v1/evidence/{rows[0]['id']}/file")
    assert r.status_code == 200 and r.content == data and r.headers["X-Content-SHA256"] == sha


def test_a_swapped_file_fails_its_hash_check(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    pid, sha, _ = _sheet_case(client, app_db)
    p = path_for(sha)
    os.chmod(p, 0o644)
    p.write_bytes(b"not the original sheet")
    try:
        ev = [e for e in client.get(f"/v1/cases/{pid}/timeline").json()["evidence"] if e["type"] == "sheet_row"]
        assert ev and all(e["file_ok"] is False and e["chain_ok"] for e in ev)   # the chain still holds the true hash
    finally:
        p.unlink()


def test_evidence_and_timelines_stay_inside_the_scope(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    pid, _, _ = _sheet_case(client, app_db)
    ev_id = [e for e in client.get(f"/v1/cases/{pid}/timeline").json()["evidence"] if e["type"] == "sheet_row"][0]["id"]
    login(client, "mkumar")                                       # BR, Muzaffarpur
    assert client.get(f"/v1/evidence/{ev_id}/file").status_code == 404
    assert client.get(f"/v1/cases/{pid}/timeline").status_code == 404
    login(client, "seoc")
    assert client.get(f"/v1/evidence/{ev_id}/file").status_code == 403
