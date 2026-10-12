"""T6 (PRD §13.6, E8/N10/N11): the deadline passes → contact overdue, ONE team escalation, the case stays with
the team, the team is greyed out of dispatch; heartbeats alone never extend a deadline. (Tests move the
deadline into the past rather than faking a clock; the ticker's tick() is called directly.)"""

import pytest
from sqlalchemy import text

from app.modules.escalations.ticker import tick
from tests.conftest import login, needs_db, one, rows

pytestmark = [needs_db, pytest.mark.scenario]


def _sql(db, sql, **p):
    with db.begin() as c:
        c.execute(text(sql), p)


def _free_cases(db, n):
    return [r[0] for r in rows(db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id"
                                   " WHERE d.name = 'Gopalganj' AND c.status IN ('reported', 'checked') AND c.geom IS NOT NULL"
                                   " AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.case_id = c.id AND a.state IN"
                                   " ('open', 'overdue')) ORDER BY c.id LIMIT :n", n=n)]


def _assign(client, db, pid, team):
    tid = one(db, "SELECT id FROM teams WHERE name = :n", n=team)
    r = client.post("/v1/assignments", json={"case": pid, "team_id": tid})
    assert r.status_code == 201, r.text
    return r.json()["assignment_id"], tid


def test_t6_overdue_is_one_team_escalation_the_case_stays_and_the_team_is_greyed(seeded, client, app_db):
    login(client, "rdas")
    (a, b) = _free_cases(app_db, 2)
    aid1, team = _assign(client, app_db, a, "Fire & Rescue Boat 5")
    aid2, _ = _assign(client, app_db, b, "Fire & Rescue Boat 5")
    _sql(app_db, "UPDATE assignments SET next_contact_due = now() - interval '1 second' WHERE id = ANY(:a)", a=[aid1, aid2])
    out = tick(app_db)
    assert out["overdue"] == 2 and out["team_escalations"] == 1

    assert one(app_db, "SELECT state FROM assignments WHERE id = :a", a=aid1) == "overdue"
    assert one(app_db, "SELECT t.name FROM assignments a JOIN teams t ON t.id = a.team_id WHERE a.id = :a",
               a=aid1) == "Fire & Rescue Boat 5"                                         # the case stays with the team
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=a) == "assigned"
    assert one(app_db, "SELECT status FROM teams WHERE id = :t", t=team) == "overdue"
    esc = client.get("/v1/escalations?incident=BR").json()
    mine = [e for e in esc if e["team_id"] == team]
    assert len(mine) == 1 and len(mine[0]["case_ids"]) == 2 and mine[0]["role"] == "duty_officer"
    assert mine[0]["line"].startswith("Fire & Rescue Boat 5 overdue · 2 cases · no contact")
    assert mine[0]["line"].endswith("Radio them, then Extend or Reassign.")
    other = _free_cases(app_db, 1)[0]
    d = client.get(f"/v1/cases/{other}/dispatch-suggestions").json()
    assert team not in [t["team_id"] for t in d["suggestions"] + d["more"]]               # greyed out of every list
    assert any(g["team_id"] == team and "overdue" in g["why"] for g in d["greyed"])
    row = next(r for r in client.get("/v1/queue?incident=BR").json()["rows"] if r["public_id"] == a)
    assert row["chip"].startswith("contact overdue") and row["action"]["kind"] == "radio"
    assert one(app_db, "SELECT actor_type FROM events WHERE action = 'assignment.overdue' LIMIT 1") == "system"
    assert tick(app_db)["team_escalations"] == 0                                          # still ONE escalation


def test_t6_heartbeats_alone_never_extend_a_deadline(seeded, client, app_db):
    login(client, "rdas")
    pid = _free_cases(app_db, 1)[0]
    aid, team = _assign(client, app_db, pid, "Fire & Rescue Boat 5")
    _sql(app_db, "UPDATE assignments SET next_contact_due = now() - interval '61 minutes' WHERE id = :a", a=aid)
    login(client, "boat5")
    for _ in range(5):                                                   # the app open, phone awake, sending "last seen"
        r = client.post("/v1/teams/me/heartbeat")
        assert r.status_code == 200 and r.json()["extends_deadline"] is False
    tick(app_db)
    assert one(app_db, "SELECT state FROM assignments WHERE id = :a", a=aid) == "overdue"
    assert one(app_db, "SELECT last_seen_at IS NOT NULL AND last_contact_at IS NULL FROM teams WHERE id = :t", t=team)


def test_t7_two_officers_on_one_escalation_the_second_gets_a_409_naming_who(seeded, client, app_db):
    login(client, "rdas")
    aid, team = _assign(client, app_db, _free_cases(app_db, 1)[0], "SDRF Boat 2") if _has_room(app_db, "SDRF Boat 2") \
        else _assign(client, app_db, _free_cases(app_db, 1)[0], "Fire & Rescue Boat 5")
    _sql(app_db, "UPDATE assignments SET next_contact_due = now() - interval '1 second' WHERE id = :a", a=aid)
    tick(app_db)
    eid = next(e["id"] for e in client.get("/v1/escalations?incident=BR").json() if e["team_id"] == team)
    assert client.post(f"/v1/escalations/{eid}/ack").status_code == 200
    login(client, "asinha")
    r = client.post(f"/v1/escalations/{eid}/ack")
    assert r.status_code == 409 and r.json()["detail"].startswith("Already acknowledged by R. Das at ")


def _has_room(db, team):
    return one(db, "SELECT t.max_active > (SELECT count(*) FROM assignments a WHERE a.team_id = t.id AND a.state IN"
                   " ('open', 'overdue')) FROM teams t WHERE t.name = :n", n=team)


def test_an_unacknowledged_escalation_rises_to_the_in_charge_and_resolves_when_the_team_is_heard(seeded, client, app_db):
    login(client, "rdas")
    aid, team = _assign(client, app_db, _free_cases(app_db, 1)[0], "Fire & Rescue Boat 5")
    _sql(app_db, "UPDATE assignments SET next_contact_due = now() - interval '1 second' WHERE id = :a", a=aid)
    tick(app_db)
    _sql(app_db, "UPDATE escalations SET opened_at = now() - interval '11 minutes' WHERE team_id = :t", t=team)
    assert tick(app_db)["risen"] == 1
    e = next(e for e in client.get("/v1/escalations?incident=BR").json() if e["team_id"] == team)
    assert (e["level"], e["role"]) == (2, "incharge")
    # the team is heard from (m42 makes this the officer's one radio log; here, directly)
    _sql(app_db, "UPDATE assignments SET state = 'open', next_contact_due = now() + interval '30 minutes' WHERE id = :a", a=aid)
    tick(app_db)
    assert one(app_db, "SELECT status FROM escalations WHERE team_id = :t", t=team) == "resolved"


def test_no_free_team_means_one_capacity_gap_header_not_one_alarm_per_case(seeded, client, app_db):
    _sql(app_db, "UPDATE teams SET status = 'out_of_service' WHERE district_id = (SELECT id FROM districts WHERE name = 'Gopalganj')")
    _sql(app_db, "UPDATE cases SET priority = 'P1', queue_since = now() - interval '10 minutes' WHERE public_id = ANY(:p)",
         p=_free_cases(app_db, 3))
    out = tick(app_db)
    assert out["capacity_gaps"] == 1
    login(client, "rdas")
    gap = [e for e in client.get("/v1/escalations?incident=BR").json() if e["kind"] == "capacity_gap"]
    assert len(gap) == 1 and gap[0]["line"].startswith("P1 without owner · ") and "0 teams free" in gap[0]["line"]
    assert "ask SEOC" in gap[0]["line"]
    _sql(app_db, "UPDATE teams SET status = 'available' WHERE name = 'Fire & Rescue Boat 5'")
    tick(app_db)
    assert one(app_db, "SELECT status FROM escalations WHERE kind = 'capacity_gap'") == "resolved"
