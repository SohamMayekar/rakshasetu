"""P1 #2 (PRD F-C3): rules propose, people decide. An officer raises or lowers a priority with a reason that is
shown on the row; the rules' own proposal stays visible; later facts never undo it; it can go back to the rules."""

from app.core.eventlog import WORKER
from app.modules.cases.service import retriage
from tests.conftest import login, needs_db, one

pytestmark = needs_db


def test_an_officer_raises_a_priority_with_a_reason_and_the_rules_keep_their_say(seeded, client, app_db):
    pid = one(app_db, "SELECT public_id FROM cases c WHERE priority = 'P2' AND status IN ('reported', 'checked') ORDER BY id LIMIT 1")
    login(client, "rdas")
    r = client.post(f"/v1/cases/{pid}/priority", json={"priority": "P1", "reason": "pregnant, said on second call"})
    assert r.status_code == 200 and r.json()["priority"] == "P1" and r.json()["rules_said"] == "P2"
    row = next(x for x in client.get("/v1/queue?incident=BR").json()["rows"] if x["public_id"] == pid)
    assert row["priority"] == "P1" and row["because"] == "raised by R. Das: “pregnant, said on second call” · the rules said P2"
    lines = [e["line"] for e in client.get(f"/v1/cases/{pid}/timeline").json()["events"]]
    assert "P1: raised from P2 by R. Das (the rules said P2)" in lines
    assert one(app_db, "SELECT reason FROM events WHERE action = 'case.priority_overridden'") == "pregnant, said on second call"

    cid = one(app_db, "SELECT id FROM cases WHERE public_id = :p", p=pid)
    with app_db.begin() as c:                                   # new facts arrive: the rules don't undo a person's call
        assert retriage(c, cid, WORKER, "a new report")["changed"] is False
    assert one(app_db, "SELECT priority FROM cases WHERE id = :c", c=cid) == "P1"

    r = client.post(f"/v1/cases/{pid}/priority", json={"priority": None, "reason": "second call was a different family"})
    assert r.status_code == 200 and r.json()["priority"] == "P2" and r.json()["override"] is None
    assert one(app_db, "SELECT priority_override IS NULL FROM cases WHERE id = :c", c=cid)


def test_a_priority_call_needs_a_reason_and_an_open_case(seeded, client, app_db):
    login(client, "rdas")
    pid = one(app_db, "SELECT public_id FROM cases WHERE status IN ('reported', 'checked') ORDER BY id LIMIT 1")
    assert client.post(f"/v1/cases/{pid}/priority", json={"priority": "P1", "reason": ""}).status_code == 422
    assert client.post(f"/v1/cases/{pid}/priority", json={"priority": "P0", "reason": "urgent"}).status_code == 422
    closed = one(app_db, "SELECT public_id FROM cases WHERE status = 'closed' LIMIT 1")
    if closed:
        assert client.post(f"/v1/cases/{closed}/priority", json={"priority": "P1", "reason": "urgent"}).status_code == 409
    login(client, "priya")                                      # a call-taker proposes nothing here: officers decide
    assert client.post(f"/v1/cases/{pid}/priority", json={"priority": "P1", "reason": "urgent"}).status_code == 403
