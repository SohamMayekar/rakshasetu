"""F-C8: verify passes after the seed, and any hand edit is caught at exactly that row."""

import pytest
from sqlalchemy import text

from tests.conftest import login, needs_db, one

pytestmark = needs_db


def verify(client):
    login(client, "admin")
    r = client.get("/v1/audit/verify")
    assert r.status_code == 200
    return r.json()


def test_verify_passes_after_the_seed(seeded, client, app_db):
    v = verify(client)
    assert v["ok"] and v["count"] == one(app_db, "SELECT count(*) FROM events")


def test_head_is_public_and_matches_the_last_event(seeded, public_client, app_db):
    h = public_client.get("/v1/audit/head").json()
    assert h["seq"] == one(app_db, "SELECT max(seq) FROM events")
    assert h["hash"] == one(app_db, "SELECT hash FROM events ORDER BY seq DESC LIMIT 1")


def test_verify_and_the_event_list_are_not_on_the_public_listener(seeded, public_client):
    assert public_client.get("/v1/audit/verify").status_code == 404
    assert public_client.get("/v1/audit").status_code == 404


@pytest.mark.parametrize("label,sql", [
    ("edit the body", "UPDATE events SET body = replace(body, '\"case.created\"', '\"case.erased\"') WHERE seq = :s"),
    ("edit a column only", "UPDATE events SET reason = 'edited quietly' WHERE seq = :s"),
    ("swap the actor", "UPDATE events SET actor_id = 'someone-else' WHERE seq = :s"),
])
def test_an_edit_breaks_the_chain_at_exactly_that_row(seeded, client, owner_db, app_db, label, sql):
    target = one(app_db, "SELECT min(seq) FROM events WHERE action = 'case.created'")
    with owner_db.begin() as c:   # the table owner stands in for a database superuser
        c.execute(text(sql), {"s": target})
    v = verify(client)
    assert not v["ok"] and v["broken_at"] == target, label


def test_deleting_a_row_breaks_the_chain_at_the_next_one(seeded, client, owner_db):
    with owner_db.begin() as c:
        c.execute(text("DELETE FROM events WHERE seq = 30"))
    v = verify(client)
    assert not v["ok"] and v["broken_at"] == 31


def test_a_forged_row_with_a_recomputed_hash_still_breaks_the_link(seeded, client, owner_db, app_db):
    """Re-hashing one row isn't enough: the next row's prev_hash no longer links."""
    from app.core.eventlog import chain_hash
    target = one(app_db, "SELECT max(seq) FROM events WHERE action = 'case.created'") - 3
    with owner_db.begin() as c:
        r = c.execute(text("SELECT body, prev_hash FROM events WHERE seq = :s"), {"s": target}).one()
        body = r.body.replace('"seq":', '"seq": ', 0) + " "      # any change to the stored text
        c.execute(text("UPDATE events SET body = :b, hash = :h WHERE seq = :s"),
                  {"b": body, "h": chain_hash(r.prev_hash, body), "s": target})
    v = verify(client)
    assert not v["ok"] and v["broken_at"] == target + 1


def test_event_list_filters_by_case(seeded, client, app_db):
    case_id = one(app_db, "SELECT min(id) FROM cases")
    login(client, "rdas")
    events = client.get("/v1/audit", params={"case_id": case_id}).json()
    assert events and all(e["case_id"] == case_id for e in events)
    assert events[0]["action"] == "case.created"
