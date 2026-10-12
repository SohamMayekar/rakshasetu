"""PRD F-C11 / rule R16: every evidence item is a stored file whose sha256 is in the audit chain: the message as
received, the transcript, the rescue record (with where the team was), the radio log, the merge record."""

import hashlib
import json
import uuid

from sqlalchemy import text

from app.core.jobs import drain
from app.core.storage import store_bytes
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = needs_db


def _items(client, pid, kind):
    return [e for e in client.get(f"/v1/cases/{pid}/timeline").json()["evidence"] if e["type"] == kind]


def _opens(client, e) -> bytes:
    r = client.get(f"/v1/evidence/{e['id']}/file")
    assert r.status_code == 200 and r.headers["x-content-type-options"] == "nosniff"
    assert hashlib.sha256(r.content).hexdigest() == e["sha256"] and e["file_ok"] and e["chain_ok"]
    return r.content


def test_a_pasted_message_is_kept_exactly_as_received(seeded, client, app_db):
    register_handlers()
    login(client, "rdas")
    words = "Fwd: Mirganj mein 4 log chhat par, ek bachcha hai. 🙏"
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "text": words, "phone": "+91 98765 71001",
                                               "client_id": str(uuid.uuid4()), "pasted_forward": True}).json()["report_id"]
    drain(app_db)
    pid = one(app_db, "SELECT c.public_id FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.id = :r", r=rid)
    (msg,) = _items(client, pid, "message")
    assert _opens(client, msg).decode() == words and msg["report_id"] == rid and msg["meta"]["forwarded"] is True
    lines = [e["line"] for e in client.get(f"/v1/cases/{pid}/timeline").json()["events"]]
    assert any(x.startswith("Evidence kept: the message as received · sha256 ") for x in lines)


def _assigned(client, app_db, team="Fire & Rescue Boat 5"):
    pid = one(app_db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                      " AND c.status IN ('reported', 'checked') AND c.geom IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assignments a"
                      " WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1")
    tid = one(app_db, "SELECT id FROM teams WHERE name = :n", n=team)
    login(client, "rdas")
    aid = client.post("/v1/assignments", json={"case": pid, "team_id": tid}).json()["assignment_id"]
    return pid, tid, aid


def test_the_rescue_record_says_where_the_team_was(seeded, client, app_db):
    pid, _, aid = _assigned(client, app_db)
    login(client, "boat5")
    client.post(f"/v1/assignments/{aid}/acknowledge", json={"eta_minutes": 15})
    client.post(f"/v1/assignments/{aid}/reached", json={})
    lat, lng = one(app_db, "SELECT array[ST_Y(geom::geometry), ST_X(geom::geometry)] FROM cases WHERE public_id = :p", p=pid)
    client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 2, "anyone_left": "no", "lat": lat + 0.001, "lng": lng})
    login(client, "rdas")
    (rec,) = _items(client, pid, "rescue")
    body = json.loads(_opens(client, rec))
    assert body["team"] == "Fire & Rescue Boat 5" and body["people_taken"] == 2 and body["outcome"] == "rescued"
    assert body["team_position"]["from"] == "the phone, with this record" and 100 < body["metres_from_pin"] < 125   # ~111 m north
    # the officer's radio record of the same trip: corroboration
    client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 2, "anyone_left": "no", "channel": "VHF"})
    second = [e for e in _items(client, pid, "rescue") if e["id"] != rec["id"]][0]
    body = json.loads(_opens(client, second))
    assert body["outcome"] == "corroboration" and body["team_position"]["from"] == "the team's last known position"


def test_a_radio_log_is_kept_on_every_case_it_covers(seeded, client, app_db):
    pid, tid, _ = _assigned(client, app_db)
    client.post(f"/v1/teams/{tid}/contact", json={"kind": "radio", "channel": "VHF", "new_eta": 30, "note": "on the way"})
    cases = [r for r in one(app_db, "SELECT array_agg(c.public_id) FROM assignments a JOIN cases c ON c.id = a.case_id"
                                    " WHERE a.team_id = :t AND a.state IN ('open', 'overdue')", t=tid)]
    assert pid in cases
    for p in cases:
        (log,) = _items(client, p, "radio")
        body = json.loads(_opens(client, log))
        assert (body["team"], body["channel"], body["new_eta"], body["logged_by"]) == ("Fire & Rescue Boat 5", "VHF", 30, "R. Das")


def test_an_edited_evidence_row_no_longer_matches_the_chain(seeded, client, app_db, owner_db):
    pid, tid, _ = _assigned(client, app_db)
    client.post(f"/v1/teams/{tid}/contact", json={"kind": "radio", "channel": "VHF"})
    (log,) = _items(client, pid, "radio")
    other, _ = store_bytes(f"another file {uuid.uuid4()}".encode(), 1000)
    with owner_db.begin() as c:                            # point the row at another stored file, as an insider might
        c.execute(text("UPDATE evidence SET sha256 = :s, uri = 'files/' || left(:s, 2) || '/' || :s WHERE id = :i"),
                  {"s": other, "i": log["id"]})
    (log,) = _items(client, pid, "radio")
    assert log["file_ok"] is True and log["chain_ok"] is False   # the file is intact; the chain recorded another hash
