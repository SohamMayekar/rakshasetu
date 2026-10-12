"""T3 (PRD §13.6, E4 / scenario A): the son's report from a different phone is suggested with reasons; a
merge and its undo leave both cases EXACTLY as they were (snapshot comparison), and both are audited."""

import uuid

import pytest

from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one, rows

pytestmark = [needs_db, pytest.mark.scenario]
DEMO = "Thawe gaon mein, Durga mandir ke peeche, pul ke paas, chhat pe 6 log fase hain. Paani ghus gaya hai, ek buzurg hain, dawai chahiye."
SON = "Mere mummy papa Thawe gaon mein hain, Durga mandir ke peeche, pul ke paas. 6 log chhat par fase hain, dawai chahiye."


def state(app_db, *case_ids):
    """Everything about the cases that a merge touches, as stored."""
    return {
        "cases": [one(app_db, "SELECT to_jsonb(c) FROM cases c WHERE id = :i", i=i) for i in case_ids],
        "reports": sorted(tuple(r) for r in rows(app_db, "SELECT id, case_id, status FROM reports WHERE case_id = ANY(:ids)",
                                                 ids=list(case_ids))),
        "evidence": sorted(tuple(r) for r in rows(app_db, "SELECT id, case_id, type FROM evidence WHERE case_id = ANY(:ids)",
                                                  ids=list(case_ids))),
    }


def test_t3_suggested_then_merged_then_undone_exactly(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    for text_, phone in ((DEMO, "+91 98765 60001"), (SON, "+91 98765 60002")):
        client.post("/v1/ingest/desk", json={"incident": "BR", "text": text_, "phone": phone, "client_id": str(uuid.uuid4())})
        drain(app_db)
    sug = client.get("/v1/merge-suggestions", params={"incident": "BR"}).json()
    assert len(sug) == 1 and sug[0]["strength"] == "strong"
    s = sug[0]
    assert any("same village (Thawe)" in r for r in s["reasons"]) and any("same landmarks" in r for r in s["reasons"])
    older, newer = s["candidate_case_id"], s["case_id"]
    for side in (older, newer):     # the drawer asks for one case's matches, from either side of the pair
        assert [x["id"] for x in client.get("/v1/merge-suggestions", params={"case": side}).json()] == [s["id"]]
    before = state(app_db, older, newer)

    merged = client.post(f"/v1/merge-suggestions/{s['id']}/accept", json={}).json()
    assert merged["kept"] == older
    assert one(app_db, "SELECT status FROM cases WHERE id = :i", i=newer) == "merged"
    assert one(app_db, "SELECT count(*) FROM reports WHERE case_id = :i", i=older) == 2
    assert state(app_db, older, newer) != before

    undone = client.post(f"/v1/merges/{merged['merge_id']}/undo", json={"reason": "different family after all"})
    assert undone.status_code == 200
    assert state(app_db, older, newer) == before                         # EXACTLY as before
    lo, hi = sorted((older, newer))
    assert one(app_db, "SELECT reason FROM merge_blocks WHERE case_a = :a AND case_b = :b", a=lo, b=hi) == "different family after all"

    login(client, "rdas")
    audit = client.get("/v1/audit", params={"case_id": older}).json()
    acts = [(e["action"], e["actor"]["id"], e["reason"]) for e in audit if e["action"] in ("case.merged", "case.unmerged")]
    priya = str(one(app_db, "SELECT id FROM users WHERE username = 'priya'"))
    assert acts == [("case.merged", priya, None), ("case.unmerged", priya, "different family after all")]


def test_an_undone_pair_is_never_suggested_again_and_a_second_undo_is_a_409(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    for text_, phone in ((DEMO, "+91 98765 60011"), (SON, "+91 98765 60012")):
        client.post("/v1/ingest/desk", json={"incident": "BR", "text": text_, "phone": phone, "client_id": str(uuid.uuid4())})
        drain(app_db)
    s = client.get("/v1/merge-suggestions").json()[0]
    mid = client.post(f"/v1/merge-suggestions/{s['id']}/accept", json={}).json()["merge_id"]
    client.post(f"/v1/merges/{mid}/undo", json={"reason": "not them"})
    again = client.post(f"/v1/merges/{mid}/undo", json={"reason": "again"})
    assert again.status_code == 409 and "Already undone by Priya Kumari" in again.json()["detail"]
    from app.modules.dedupe.decide import blocked
    with app_db.connect() as c:
        assert blocked(c, s["case_id"], s["candidate_case_id"])


def test_rejecting_a_suggestion_blocks_the_pair_and_clears_the_flag(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    for text_, phone in ((DEMO, "+91 98765 60021"), (SON, "+91 98765 60022")):
        client.post("/v1/ingest/desk", json={"incident": "BR", "text": text_, "phone": phone, "client_id": str(uuid.uuid4())})
        drain(app_db)
    s = client.get("/v1/merge-suggestions").json()[0]
    assert client.post(f"/v1/merge-suggestions/{s['id']}/reject", json={"reason": "different house"}).status_code == 200
    assert "possible_duplicate" not in one(app_db, "SELECT flags FROM cases WHERE id = :c", c=s["case_id"])
    assert client.get("/v1/merge-suggestions").json() == []


def test_a_refused_pair_can_be_merged_only_with_a_reason(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    for text_, phone in (("Ramesh Das, 5 log, Thawe gaon, mandir ke paas, fase hain", "+91 98765 60031"),
                         ("Rajesh Das, 5 log, Thawe gaon, mandir ke paas, fase hain", "+91 98765 60032")):
        client.post("/v1/ingest/desk", json={"incident": "BR", "text": text_, "phone": phone, "client_id": str(uuid.uuid4())})
        drain(app_db)
    s = client.get("/v1/merge-suggestions").json()[0]
    assert s["strength"] == "refused"
    assert client.post(f"/v1/merge-suggestions/{s['id']}/accept", json={}).status_code == 409
    assert client.post(f"/v1/merge-suggestions/{s['id']}/accept", json={"reason": "same man, STT misheard"}).status_code == 200
