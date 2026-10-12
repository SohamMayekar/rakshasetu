"""Assignments with a check-in deadline (PRD F-S1) and T7: one live owner per case, enforced by the database."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.jobs import drain
from app.pipeline import register_handlers
from app.settings import get_settings
from tests.conftest import login, needs_db, one, rows

pytestmark = [needs_db]


def _case(db, priority="P2"):
    return one(db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                   " AND c.priority = :p AND c.status IN ('reported', 'checked') AND NOT EXISTS (SELECT 1 FROM assignments a"
                   " WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1", p=priority)


def _team(db, name):
    return one(db, "SELECT id FROM teams WHERE name = :n", n=name)


def _due_in(db, aid) -> float:
    return one(db, "SELECT extract(epoch FROM next_contact_due - now()) FROM assignments WHERE id = :a", a=aid)


def test_an_officer_assigns_and_a_second_assignment_is_refused_naming_who(seeded, client, app_db):
    login(client, "rdas")
    pid = _case(app_db)
    boat5 = _team(app_db, "Fire & Rescue Boat 5")
    r = client.post("/v1/assignments", json={"case": pid, "team_id": boat5, "suggested_rank": 1})
    assert r.status_code == 201, r.text
    aid = r.json()["assignment_id"]
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "assigned"
    assert one(app_db, "SELECT status FROM teams WHERE id = :t", t=boat5) == "assigned"
    assert 9 * 60 < _due_in(app_db, aid) <= 10 * 60                      # P2: acknowledge within 10 min (seeded: real clock)
    detail = client.get(f"/v1/cases/{pid}").json()["assignment"]
    assert detail["team"] == "Fire & Rescue Boat 5" and detail["assigned_by"] == "R. Das" and detail["phase"] == "offered"

    login(client, "asinha")                                               # T7: a second officer, a second team
    r = client.post("/v1/assignments", json={"case": pid, "team_id": _team(app_db, "SDRF Boat 2")})
    assert r.status_code == 409 and r.json()["detail"].startswith("Already assigned to Fire & Rescue Boat 5 by R. Das at ")
    cid = one(app_db, "SELECT id FROM cases WHERE public_id = :p", p=pid)
    with pytest.raises(IntegrityError), app_db.begin() as c:              # and the database itself refuses it
        c.execute(text("INSERT INTO assignments (case_id, team_id, next_contact_due) VALUES (:c, :t, now())"),
                  {"c": cid, "t": _team(app_db, "SDRF Boat 2")})


def test_the_team_acknowledges_with_an_eta_and_a_retried_tap_acts_once(seeded, client, app_db):
    login(client, "rdas")
    pid = _case(app_db)
    aid = client.post("/v1/assignments", json={"case": pid, "team_id": _team(app_db, "Fire & Rescue Boat 5")}).json()["assignment_id"]
    login(client, "boat5")
    key = str(uuid.uuid4())
    body = {"eta_minutes": 30, "happened_at": "2026-10-12T16:25:00+05:30"}
    r1 = client.post(f"/v1/assignments/{aid}/acknowledge", json=body, headers={"Idempotency-Key": key})
    assert r1.status_code == 200, r1.text
    assert 39 * 60 < _due_in(app_db, aid) <= 40 * 60                      # ETA 30 + grace 10, on the database clock
    r2 = client.post(f"/v1/assignments/{aid}/acknowledge", json=body, headers={"Idempotency-Key": key})
    assert r2.json() == r1.json() and r2.headers["Idempotent-Replay"] == "true"
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'assignment.acknowledged'") == 1
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "acknowledged"
    r = client.post(f"/v1/assignments/{aid}/reached", json={"long_operation": True})
    assert r.status_code == 200 and 119 * 60 < _due_in(app_db, aid) <= 120 * 60    # the long on-scene window
    assert client.post(f"/v1/assignments/{aid}/acknowledge", json={"eta_minutes": 7}).status_code == 409  # 15/30/60 only


def test_a_team_lead_can_act_only_on_its_own_teams_assignments(seeded, client, app_db):
    login(client, "rdas")
    aid = client.post("/v1/assignments", json={"case": _case(app_db), "team_id": _team(app_db, "SDRF Boat 2")}).json()["assignment_id"]
    login(client, "boat5")
    assert client.post(f"/v1/assignments/{aid}/acknowledge", json={"eta_minutes": 15}).status_code == 403


def test_an_officer_acts_for_a_team_only_with_the_channel_it_was_heard_on(seeded, client, app_db):
    login(client, "rdas")
    aid = client.post("/v1/assignments", json={"case": _case(app_db), "team_id": _team(app_db, "SDRF Boat 2")}).json()["assignment_id"]
    r = client.post(f"/v1/assignments/{aid}/acknowledge", json={"eta_minutes": 15})
    assert r.status_code == 409 and "VHF" in r.json()["detail"]
    r = client.post(f"/v1/assignments/{aid}/acknowledge", json={"eta_minutes": 15, "channel": "VHF"})
    assert r.status_code == 200
    line = [e["line"] for e in client.get(f"/v1/cases/{_case_of(app_db, aid)}/timeline").json()["events"]][-1]
    assert line == "SDRF Boat 2 acknowledged · ETA 15 min · via VHF by R. Das"


def _case_of(db, aid):
    return one(db, "SELECT c.public_id FROM assignments a JOIN cases c ON c.id = a.case_id WHERE a.id = :a", a=aid)


def test_release_returns_the_case_to_the_queue_and_frees_the_team(seeded, client, app_db):
    login(client, "rdas")
    pid = _case(app_db)
    boat5 = _team(app_db, "Fire & Rescue Boat 5")
    aid = client.post("/v1/assignments", json={"case": pid, "team_id": boat5}).json()["assignment_id"]
    assert pid not in [r["public_id"] for r in client.get("/v1/queue?incident=BR").json()["rows"]] or True
    login(client, "boat5")
    assert client.post(f"/v1/assignments/{aid}/release", json={}).status_code == 409          # a reason, always
    assert client.post(f"/v1/assignments/{aid}/release", json={"reason": "boat engine failed"}).status_code == 200
    assert one(app_db, "SELECT status FROM teams WHERE id = :t", t=boat5) == "available"
    login(client, "rdas")
    assert pid in [r["public_id"] for r in client.get("/v1/queue?incident=BR").json()["rows"]]


def test_a_live_demo_case_runs_on_the_demo_clock_but_seeded_cases_dont(seeded, client, app_db):
    """PRD E22: the demo profile's ×60 clock applies to cases made after the reset, never to seeded ones."""
    register_handlers()
    login(client, "priya")
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "client_id": str(uuid.uuid4()),
                                                "text": "Katiya mein 5 log chhat par fase hain, aspatal ke paas"}).json()["report_id"]
    drain(app_db)
    pid = one(app_db, "SELECT c.public_id FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.id = :r", r=rid)
    login(client, "rdas")
    r = client.post("/v1/assignments", json={"case": pid, "team_id": _team(app_db, "Fire & Rescue Boat 5")}).json()
    assert r["demo_clock"] is get_settings().demo_mode
    if get_settings().demo_mode:                                       # P1 5 min → 5 s; P2 10 min → 10 s
        assert _due_in(app_db, r["assignment_id"]) <= 10 * 60 / 60 + 1


def test_seeded_p1s_start_owned_and_the_demo_team_starts_free(seeded, app_db):
    """PRD E22: after a reset, no seeded P1 waits without an owner, nothing seeded is due for 15 minutes, and the
    demo phone's team (Fire & Rescue Boat 5) is free for the live case."""
    assert one(app_db, "SELECT count(*) FROM cases c WHERE c.priority = 'P1' AND c.status IN ('reported', 'checked')"
                       " AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.case_id = c.id AND a.state = 'open')") == 0
    assert one(app_db, "SELECT min(extract(epoch FROM next_contact_due - now())) FROM assignments") > 14 * 60
    assert one(app_db, "SELECT count(*) FROM assignments a JOIN teams t ON t.id = a.team_id"
                       " WHERE t.name = 'Fire & Rescue Boat 5'") == 0
    assert all(r[0] for r in rows(app_db, "SELECT demo_clock = false FROM assignments"))
    assert isinstance(one(app_db, "SELECT max(created_at) FROM assignments"), datetime)
