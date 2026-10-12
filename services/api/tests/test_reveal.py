"""Revealing a phone number (PRD F-C7, P1 #12): a reason for desk users, automatic for the assigned team, a 403 for
any other team, and the number never written into the event log."""

from tests.conftest import login, needs_db, one

pytestmark = [needs_db]


def _case(db):
    return one(db, "SELECT c.public_id FROM cases c JOIN reports r ON r.case_id = c.id JOIN districts d ON d.id = c.district_id"
                   " WHERE d.name = 'Gopalganj' AND r.reporter_phone_enc IS NOT NULL AND NOT EXISTS (SELECT 1 FROM assignments a"
                   " WHERE a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1")


def test_a_desk_user_needs_a_reason_and_the_log_keeps_only_the_masked_number(seeded, client, app_db):
    pid = _case(app_db)
    login(client, "priya")
    assert client.post(f"/v1/cases/{pid}/reveal-contact", json={}).status_code == 409
    r = client.post(f"/v1/cases/{pid}/reveal-contact", json={"reason": "the caller asked us to ring back"})
    assert r.status_code == 200 and r.json()["phone"].startswith("+91") and "x" in r.json()["masked"]
    body = one(app_db, "SELECT body FROM events WHERE action = 'contact.revealed' ORDER BY seq DESC LIMIT 1")
    assert r.json()["phone"] not in body and r.json()["masked"] in body


def test_the_assigned_team_reveals_without_typing_and_other_teams_get_403(seeded, client, app_db):
    pid = _case(app_db)
    login(client, "rdas")
    boat5 = one(app_db, "SELECT id FROM teams WHERE name = 'Fire & Rescue Boat 5'")
    assert client.post("/v1/assignments", json={"case": pid, "team_id": boat5}).status_code == 201
    login(client, "boat5")
    r = client.post(f"/v1/cases/{pid}/reveal-contact", json={})
    assert r.status_code == 200
    assert one(app_db, "SELECT reason FROM events WHERE action = 'contact.revealed' ORDER BY seq DESC LIMIT 1") == \
        "on-site call by the assigned team"
    login(client, "ndrf03")
    assert client.post(f"/v1/cases/{pid}/reveal-contact", json={}).status_code == 403
