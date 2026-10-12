"""T7 (PRD §13.6, N12 / scenario K): two officers act on the same thing at once → the second gets a 409 that names
who acted and when; and the database itself refuses a second open assignment for one case."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.modules.escalations.ticker import tick
from tests.conftest import login, needs_db, one

pytestmark = [needs_db, pytest.mark.scenario]


def _team(db, name):
    return one(db, "SELECT id FROM teams WHERE name = :n", n=name)


def _free_case(db):
    return one(db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                   " AND c.status IN ('reported', 'checked') AND c.geom IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assignments a"
                   " WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1")


def test_t7_two_officers_on_one_escalation(seeded, client, app_db):
    login(client, "rdas")
    pid = _free_case(app_db)
    aid = client.post("/v1/assignments", json={"case": pid, "team_id": _team(app_db, "Fire & Rescue Boat 5")}).json()["assignment_id"]
    with app_db.begin() as c:
        c.execute(text("UPDATE assignments SET next_contact_due = now() - interval '1 second' WHERE id = :a"), {"a": aid})
    tick(app_db)
    (esc,) = [e for e in client.get("/v1/escalations", params={"incident": "BR"}).json() if e["team"] == "Fire & Rescue Boat 5"]

    assert client.post(f"/v1/escalations/{esc['id']}/ack").status_code == 200            # R. Das: "I'm on it"
    login(client, "asinha")                                                              # the in-charge, a moment later
    r = client.post(f"/v1/escalations/{esc['id']}/ack")
    assert r.status_code == 409 and r.json()["detail"].startswith("Already acknowledged by R. Das at ")

    login(client, "rdas")
    assert client.post(f"/v1/escalations/{esc['id']}/reassign",
                       json={"case": pid, "team_id": _team(app_db, "SDRF Boat 2")}).status_code == 200
    login(client, "asinha")
    r = client.post(f"/v1/escalations/{esc['id']}/reassign", json={"case": pid, "team_id": _team(app_db, "SDRF Boat 4")})
    assert r.status_code == 409 and r.json()["detail"].startswith("Already resolved: ") and "R. Das" in r.json()["detail"], r.text
    owners = one(app_db, "SELECT array_agg(t.name) FROM assignments a JOIN teams t ON t.id = a.team_id JOIN cases c ON"
                         " c.id = a.case_id WHERE c.public_id = :p AND a.state IN ('open', 'overdue')", p=pid)
    assert owners == ["SDRF Boat 2"]                                                     # one owner, the first decision


def test_t7_the_database_refuses_a_second_open_assignment(seeded, client, app_db):
    login(client, "rdas")
    pid = _free_case(app_db)
    client.post("/v1/assignments", json={"case": pid, "team_id": _team(app_db, "Fire & Rescue Boat 5")})
    login(client, "asinha")
    r = client.post("/v1/assignments", json={"case": pid, "team_id": _team(app_db, "SDRF Boat 2")})
    assert r.status_code == 409 and r.json()["detail"].startswith("Already assigned to Fire & Rescue Boat 5 by R. Das at ")
    cid = one(app_db, "SELECT id FROM cases WHERE public_id = :p", p=pid)
    with pytest.raises(IntegrityError), app_db.begin() as c:                             # even around the API
        c.execute(text("INSERT INTO assignments (case_id, team_id, next_contact_due) VALUES (:c, :t, now())"),
                  {"c": cid, "t": _team(app_db, "SDRF Boat 2")})
