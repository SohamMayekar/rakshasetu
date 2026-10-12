"""T8 (PRD §13.6, E10) and the rest of the rescue sheet (F-S3): the family is never asked for anything."""

import uuid

import pytest
from sqlalchemy import text

from app.modules.escalations.ticker import tick
from tests.conftest import login, needs_db, one

pytestmark = [needs_db, pytest.mark.scenario]


def _owned_case(client, db, people=6, team="Fire & Rescue Boat 5"):
    pid = one(db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                  " AND c.status IN ('reported', 'checked') AND c.geom IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assignments a"
                  " WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1")
    with db.begin() as c:
        c.execute(text("UPDATE cases SET priority = 'P1', p1_rank = 2, people_count = :n, queue_since = now() - interval"
                       " '40 minutes' WHERE public_id = :p"), {"n": people, "p": pid})
    login(client, "rdas")
    tid = one(db, "SELECT id FROM teams WHERE name = :n", n=team)
    aid = client.post("/v1/assignments", json={"case": pid, "team_id": tid}).json()["assignment_id"]
    login(client, "boat5")
    client.post(f"/v1/assignments/{aid}/acknowledge", json={"eta_minutes": 15})
    client.post(f"/v1/assignments/{aid}/reached", json={})
    return pid


def test_t8_four_taken_someone_still_there_goes_back_to_the_top_of_p1_with_its_original_time(seeded, client, app_db):
    pid = _owned_case(client, app_db, people=6)
    since = one(app_db, "SELECT queue_since FROM cases WHERE public_id = :p", p=pid)
    r = client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 4, "anyone_left": "yes"})
    assert r.status_code == 200 and r.json()["outcome"] == "partial" and r.json()["remaining"] == 2
    assert one(app_db, "SELECT queue_since FROM cases WHERE public_id = :p", p=pid) == since         # original time
    assert one(app_db, "SELECT status FROM teams WHERE name = 'Fire & Rescue Boat 5'") == "available"
    login(client, "rdas")
    rows = client.get("/v1/queue?incident=BR").json()["rows"]
    row = next(r for r in rows if r["public_id"] == pid)
    assert row["priority"] == "P1" and row["broken"] and row["chip"] == "2 of 6 still there"
    p1_broken = [r for r in rows if r["priority"] == "P1" and r["broken"]]
    assert p1_broken.index(row) <= 1                                       # at the top of P1 (rank 2, waited 40 min)
    lines = [e["line"] for e in client.get(f"/v1/cases/{pid}/timeline").json()["events"]]
    assert "Fire & Rescue Boat 5: took 4, 2 still there · back to the queue with its original time" in lines


def test_nobody_left_closes_after_the_review_window_with_no_family_input(seeded, client, app_db):
    pid = _owned_case(client, app_db, people=6)
    r = client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 6, "anyone_left": "no"})
    assert r.json()["outcome"] == "rescued" and one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "rescued"
    tick(app_db)
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "rescued"           # window not passed
    with app_db.begin() as c:
        c.execute(text("UPDATE cases SET rescued_at = now() - interval '3 hours' WHERE public_id = :p"), {"p": pid})
    assert tick(app_db)["closed"] == 1
    assert one(app_db, "SELECT resolution FROM cases WHERE public_id = :p", p=pid).startswith("Rescued 6 of 6 · Fire & Rescue Boat 5 · ")


def test_couldnt_reach_stays_open_with_why_and_other_pauses_family_messages(seeded, client, app_db):
    pid = _owned_case(client, app_db)
    assert client.post(f"/v1/cases/{pid}/rescues", json={"outcome": "couldnt_reach"}).status_code == 409   # why, always
    r = client.post(f"/v1/cases/{pid}/rescues", json={"outcome": "couldnt_reach", "reason": "road_bridge"})
    assert r.json()["status"] in ("reported", "checked")
    login(client, "rdas")
    row = next(r for r in client.get("/v1/queue?incident=BR").json()["rows"] if r["public_id"] == pid)
    assert row["chip"] == "couldn't reach" and "couldn't reach (road or bridge)" in row["line2"]

    pid2 = _owned_case(client, app_db)
    r = client.post(f"/v1/cases/{pid2}/rescues", json={"outcome": "other", "reason": "found deceased, family informed in person"})
    assert r.json()["outcome"] == "other"
    data = one(app_db, "SELECT body::jsonb->'data' FROM events WHERE action = 'rescue.other' ORDER BY seq DESC LIMIT 1")
    assert data["suppress_family_messages"] is True
    login(client, "rdas")
    assert next(r for r in client.get("/v1/queue?incident=BR").json()["rows"] if r["public_id"] == pid2)["chip"] == "tell officer"


def test_an_officers_radio_record_and_the_apps_later_sync_are_one_rescue(seeded, client, app_db):
    pid = _owned_case(client, app_db)
    login(client, "rdas")
    assert client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 6, "anyone_left": "no"}).status_code == 409  # channel
    r1 = client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 6, "anyone_left": "no", "channel": "VHF"})
    assert r1.status_code == 200
    login(client, "boat5")
    key = str(uuid.uuid4())
    r2 = client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 6, "anyone_left": "no"}, headers={"Idempotency-Key": key})
    assert r2.json()["corroborates"] == r1.json()["rescue_id"]
    assert one(app_db, "SELECT count(*) FROM rescues WHERE case_id = (SELECT id FROM cases WHERE public_id = :p)"
                       " AND corroborates IS NULL", p=pid) == 1
    r3 = client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 6, "anyone_left": "no"}, headers={"Idempotency-Key": key})
    assert r3.json() == r2.json() and r3.headers["Idempotent-Replay"] == "true"
    login(client, "rdas")
    lines = [e["line"] for e in client.get(f"/v1/cases/{pid}/timeline").json()["events"]]
    assert "Fire & Rescue Boat 5: 6 of 6 rescued, nobody left · via VHF by R. Das" in lines


def test_a_record_far_from_the_pin_doesnt_auto_close_and_an_officer_closes_it(seeded, client, app_db):
    pid = _owned_case(client, app_db)
    r = client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 6, "anyone_left": "no", "lat": 26.0, "lng": 84.0})
    assert r.json()["away_from_pin"] is True
    with app_db.begin() as c:
        c.execute(text("UPDATE cases SET rescued_at = now() - interval '3 hours' WHERE public_id = :p"), {"p": pid})
    tick(app_db)
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "rescued"         # blocked
    login(client, "priya")
    assert client.post(f"/v1/cases/{pid}/close", json={"reason": "radio confirmed"}).status_code == 403
    login(client, "rdas")
    assert client.post(f"/v1/cases/{pid}/close", json={"reason": "radio confirmed the right house"}).status_code == 200
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "closed"
    assert client.post(f"/v1/cases/{pid}/reopen", json={"reason": "neighbour says 2 still on the roof"}).json()["status"] in ("reported", "checked")


def test_two_trips_count_as_one_rescue_of_everyone(seeded, client, app_db):
    """4 taken (2 still there), the boat sent again, 2 taken (nobody left): the case, the family's question and
    the closing line all say 6, not the last trip's 2."""
    pid = _owned_case(client, app_db, people=6)
    assert client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 4, "anyone_left": "yes"}).json()["remaining"] == 2
    login(client, "rdas")
    tid = one(app_db, "SELECT id FROM teams WHERE name = 'Fire & Rescue Boat 5'")
    aid = client.post("/v1/assignments", json={"case": pid, "team_id": tid}).json()["assignment_id"]
    login(client, "boat5")
    client.post(f"/v1/assignments/{aid}/acknowledge", json={"eta_minutes": 15})
    client.post(f"/v1/assignments/{aid}/reached", json={})
    r = client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 2, "anyone_left": "no"}).json()
    assert r["outcome"] == "rescued"
    data = one(app_db, "SELECT body::jsonb->'data' FROM events WHERE action = 'rescue.recorded' ORDER BY seq DESC LIMIT 1")
    assert data["total_taken"] == 6 and data["earlier_trips_taken"] == 4
    with app_db.begin() as c:
        c.execute(text("UPDATE cases SET rescued_at = now() - interval '3 hours' WHERE public_id = :p"), {"p": pid})
    tick(app_db)
    assert one(app_db, "SELECT resolution FROM cases WHERE public_id = :p", p=pid).startswith("Rescued 6 of 6 · Fire & Rescue Boat 5 · ")
