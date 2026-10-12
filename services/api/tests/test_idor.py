"""One IDOR test per resource (PRD F-C9): case, WebSocket (and polling), evidence, assignment.
Guessing another district's or another team's id must never return its data."""


from app.core.eventlog import SYSTEM, append_event
from tests.conftest import login, needs_db, one

pytestmark = needs_db


def _muzaffarpur_case(app_db):
    return one(app_db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id"
                       " WHERE d.name = 'Muzaffarpur' ORDER BY c.id LIMIT 1")


def test_case_idor_by_public_id_and_numeric_id(seeded, client, app_db):
    pid = _muzaffarpur_case(app_db)
    num = one(app_db, "SELECT id FROM cases WHERE public_id = :p", p=pid)
    login(client, "rdas")                                 # Gopalganj duty officer
    assert client.get(f"/v1/cases/{pid}").status_code == 404
    assert client.get(f"/v1/cases/{num}").status_code == 404
    login(client, "mkumar")                               # Muzaffarpur duty officer: their own case
    assert client.get(f"/v1/cases/{pid}").status_code == 200


def test_case_idor_for_a_team_lead(seeded, client, app_db):
    login(client, "boat5")
    assert client.get("/v1/cases/BR-151").status_code == 403


def test_websocket_idor_other_districts_events_never_arrive(seeded, client, app_db):
    gop = one(app_db, "SELECT id FROM districts WHERE name = 'Gopalganj'")
    muz = one(app_db, "SELECT id FROM districts WHERE name = 'Muzaffarpur'")
    br = one(app_db, "SELECT id FROM incidents WHERE code = 'BR'")
    head = one(app_db, "SELECT max(seq) FROM events")
    login(client, "mkumar")
    with client.websocket_connect(f"/v1/ws?since={head}") as ws:
        assert ws.receive_json()["type"] == "hello"
        with app_db.begin() as c:
            append_event(c, actor=SYSTEM, action="case.updated", entity_type="case", entity_id=1,
                         incident_id=br, district_id=gop, case_id=1)
        with app_db.begin() as c:
            mine = append_event(c, actor=SYSTEM, action="case.updated", entity_type="case", entity_id=2,
                                incident_id=br, district_id=muz, case_id=2)
        m = ws.receive_json()
        while m["type"] in ("ping", "hello"):
            m = ws.receive_json()
        assert m["seq"] == mine                           # the Gopalganj event was skipped


def test_polling_events_idor(seeded, client, app_db):
    login(client, "mkumar")
    gop = one(app_db, "SELECT id FROM districts WHERE name = 'Gopalganj'")
    events = client.get("/v1/events", params={"since": 0}).json()
    assert events and gop not in {e["district_id"] for e in events}


def test_evidence_idor(seeded, client, app_db):
    """A Gopalganj case's evidence file, guessed by id from outside its scope, never comes back."""
    from app.core.jobs import drain
    from app.pipeline import register_handlers
    register_handlers()
    login(client, "rdas")
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "text": "Mirganj mein 4 log fase hain",
                                               "phone": "+91 98765 72001", "client_id": "idor-ev-0001"}).json()["report_id"]
    drain(app_db)
    eid = one(app_db, "SELECT id FROM evidence WHERE report_id = :r AND type = 'message'", r=rid)
    assert client.get(f"/v1/evidence/{eid}/file").status_code == 200
    login(client, "mkumar")                               # Muzaffarpur duty officer
    assert client.get(f"/v1/evidence/{eid}/file").status_code == 404
    login(client, "boat5")                                # a team lead: only the cases its team holds
    assert client.get(f"/v1/evidence/{eid}/file").status_code == 404
    login(client, "seoc")                                 # totals only
    assert client.get(f"/v1/evidence/{eid}/file").status_code == 403


def test_assignment_idor(seeded, client, app_db):
    """Another team's lead, or another district's officer, can't act on an assignment by guessing its id."""
    pid = one(app_db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                      " AND c.status IN ('reported', 'checked') AND c.geom IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assignments a"
                      " WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1")
    login(client, "rdas")
    aid = client.post("/v1/assignments", json={"case": pid, "team_id": one(app_db, "SELECT id FROM teams WHERE name ="
                                                                                    " 'Fire & Rescue Boat 5'")}).json()["assignment_id"]
    for user in ("ndrf03", "boat1", "mkumar"):            # another Gopalganj team, a Muzaffarpur team, a Muzaffarpur officer
        login(client, user)
        for step, body in (("acknowledge", {"eta_minutes": 15, "channel": "VHF"}), ("reached", {"channel": "VHF"}),
                           ("release", {"reason": "not ours", "channel": "VHF"})):
            r = client.post(f"/v1/assignments/{aid}/{step}", json=body)
            assert r.status_code in (403, 404), (user, step, r.status_code, r.text)
        r = client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 1, "anyone_left": "no", "channel": "VHF"})
        assert r.status_code in (403, 404), (user, "rescue", r.status_code)
    assert one(app_db, "SELECT phase || '/' || state FROM assignments WHERE id = :a", a=aid) == "offered/open"
    assert one(app_db, "SELECT count(*) FROM rescues") == 0
