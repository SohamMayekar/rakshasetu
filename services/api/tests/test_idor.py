"""One IDOR test per resource (PRD F-C9): case, WebSocket, and (as they land) evidence and assignment.
Guessing another district's or another team's id must never return its data."""

import pytest

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


@pytest.mark.skip(reason="evidence endpoints arrive in m35/m52")
def test_evidence_idor():
    pass


@pytest.mark.skip(reason="assignment endpoints arrive in m40")
def test_assignment_idor():
    pass
