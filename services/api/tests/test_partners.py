"""PRD §11.4: partner annotations, each kind's effect decided by our rules; and the partner log (P1 #13)."""

import json
import time
import uuid

import pytest
from sqlalchemy import text

from app.channels.partner import sign
from tests.conftest import login, needs_db, one

pytestmark = needs_db
SECRET = "test-partner-secret"


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("PARTNER_DEMO_SECRET", SECRET)


def _post(client, body: dict, *, ts=None, secret=SECRET, key=None):
    raw = json.dumps(body).encode()
    ts = str(ts if ts is not None else int(time.time()))
    return client.post("/v1/partners/annotations", content=raw, headers={
        "Content-Type": "application/json", "X-RakshaSetu-Partner": "demo-partner", "X-RakshaSetu-Timestamp": ts,
        "X-RakshaSetu-Signature": sign(secret, ts, raw), "Idempotency-Key": key or body["idempotency_key"]})


def _open_case(db):
    return one(db, "SELECT public_id FROM cases c JOIN incidents i ON i.id = c.incident_id WHERE i.code = 'BR'"
                   " AND c.status IN ('reported', 'checked') AND c.priority = 'P2' ORDER BY c.id LIMIT 1")


def test_a_priority_suggestion_is_the_officers_to_accept(seeded, client, public_client, app_db):
    pid = _open_case(app_db)
    body = {"idempotency_key": f"ann-{uuid.uuid4()}", "kind": "priority", "target": {"case": pid}, "value": "P1",
            "confidence": 0.78, "explanation": "river overflow: gauge G-03 rising, 3 reports within 1 km (simulated)"}
    r = _post(public_client, body)
    assert r.status_code == 201 and r.json()["effect"] == "a suggestion an officer accepts or ignores"
    again = _post(public_client, body)                                      # a replay: the first answer, nothing new
    assert again.status_code == 200 and again.headers["Idempotent-Replay"] == "true"
    assert again.json()["annotation_id"] == r.json()["annotation_id"]
    assert one(app_db, "SELECT priority FROM cases WHERE public_id = :p", p=pid) == "P2"   # a suggestion changes nothing
    login(client, "rdas")
    (a,) = client.get(f"/v1/cases/{pid}/annotations").json()
    assert (a["team"], a["value"], a["confidence"], a["decision"]) == ("Demo partner (simulated by RakshaSetu)", "P1", 0.78, None)
    assert client.post(f"/v1/partner-annotations/{a['id']}/accept").status_code == 200
    o = one(app_db, "SELECT priority_override FROM cases WHERE public_id = :p", p=pid)
    assert o["level"] == "P1" and o["by"] == "R. Das" and "accepted Demo partner (simulated by RakshaSetu)'s suggestion (0.780)" in o["reason"]
    assert client.post(f"/v1/partner-annotations/{a['id']}/ignore").status_code == 409   # decided once
    login(client, "priya")
    assert client.post(f"/v1/partner-annotations/{a['id']}/accept").status_code == 403   # officers decide


def test_a_credibility_note_marks_that_evidence_item_and_nothing_else(seeded, client, public_client, app_db):
    from app.core.jobs import drain
    from app.pipeline import register_handlers
    register_handlers()
    login(client, "rdas")
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "text": "Mirganj mein 4 log chhat par fase hain, bachche hain",
                                               "client_id": str(uuid.uuid4())}).json()["report_id"]
    drain(app_db)
    sha, eid, pid, prio = one(app_db, "SELECT array[e.sha256, e.id::text, c.public_id, c.priority] FROM evidence e"
                                      " JOIN cases c ON c.id = e.case_id WHERE e.report_id = :r", r=rid)
    r = _post(public_client, {"idempotency_key": f"ann-{uuid.uuid4()}", "kind": "credibility", "target": {"evidence_sha256": sha},
                              "value": "likely recycled", "confidence": 0.87, "explanation": "seen online in 2019"})
    assert r.status_code == 201
    (a,) = client.get(f"/v1/cases/{pid}/annotations").json()
    assert a["evidence_id"] == int(eid) and a["kind"] == "credibility"
    assert one(app_db, "SELECT priority FROM cases WHERE public_id = :p", p=pid) == prio  # never lowers a priority
    kinds = [e["type"] for e in client.get(f"/v1/cases/{pid}/timeline").json()["evidence"]]
    assert "partner_annotation" in kinds                                    # the note itself is hashed evidence


def test_an_anchor_receipt_is_checked_against_our_chain(seeded, client, public_client, app_db, owner_db):
    head = public_client.get("/v1/audit/head").json()
    r = _post(public_client, {"idempotency_key": f"ann-{uuid.uuid4()}", "kind": "anchor_receipt",
                              "target": {"seq": head["seq"], "head_hash": head["hash"]}, "value": "ledger tx 0xab12"})
    assert r.status_code == 201
    login(client, "rdas")
    (a,) = client.get("/v1/partners/log").json()["anchors"]
    assert a["seq"] == head["seq"] and a["matches"] is True
    with owner_db.begin() as c:                                            # someone re-hashes history to hide an edit
        c.execute(text("UPDATE events SET hash = repeat('0', 64) WHERE seq = :s"), {"s": head["seq"]})
    (a,) = client.get("/v1/partners/log").json()["anchors"]
    assert a["matches"] is False


def test_refusals_are_in_the_partner_log(seeded, client, public_client, app_db):
    pid = _open_case(app_db)
    body = {"idempotency_key": f"ann-{uuid.uuid4()}", "kind": "priority", "target": {"case": pid}, "value": "P1"}
    assert _post(public_client, body, ts=int(time.time()) - 900).status_code == 401              # a captured request, replayed
    assert _post(public_client, body, secret="not-the-secret").status_code == 401
    assert _post(public_client, body, ts="soon").status_code == 401                              # never got as far as the signature
    assert _post(public_client, {**body, "kind": "identity", "idempotency_key": f"ann-{uuid.uuid4()}"}).status_code == 422
    assert public_client.post("/v1/partners/annotations", json=body).status_code == 401           # unsigned
    login(client, "priya")
    assert client.get("/v1/partners/log").status_code == 403
    login(client, "rdas")
    calls = client.get("/v1/partners/log").json()["calls"]
    notes = [(c["status"], c["signature_ok"], c["note"]) for c in calls]
    assert (401, True, "401 · Stale timestamp: replay rejected") in notes                  # signed right, but too long ago
    assert (401, False, "401 · Bad signature") in notes
    assert (401, None, "401 · Missing or malformed timestamp") in notes
    assert any(s == 422 and ok is True for s, ok, _ in notes)
    assert all(c["body_sha256"] and c["latency_ms"] is not None and c["direction"] == "in" for c in calls)
