"""P1 #1 (PRD F-D2): a merge tightens the circle when the merged report adds landmarks inside it; a pin a person
set is never replaced by a derived one; a merged report from outside the circle is only a proposed move."""

import uuid

from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = needs_db


def _report(client, app_db, text, phone):
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "text": text, "phone": phone,
                                               "client_id": str(uuid.uuid4())}).json()["report_id"]
    drain(app_db)
    return one(app_db, "SELECT c.public_id FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.id = :r", r=rid)


def _loc(app_db, pid):
    return one(app_db, "SELECT to_jsonb(x) FROM (SELECT radius_m, location_confidence, location_method, location_source"
                       " FROM cases WHERE public_id = :p) x", p=pid)


def test_a_temple_report_and_a_bridge_report_merge_into_a_tighter_circle(seeded, client, app_db):
    register_handlers()
    login(client, "rdas")
    a = _report(client, app_db, "Thawe gaon mein, Durga mandir ke peeche, 6 log chhat par fase hain", "+91 98765 74001")
    b = _report(client, app_db, "Thawe gaon mein, pul ke paas, 6 log chhat par fase hain, paani bahut hai", "+91 98765 74002")
    before = _loc(app_db, a)
    assert before["radius_m"] > 150 and "temple" in before["location_method"].lower()
    r = client.post("/v1/merges", json={"cases": [a, b], "reason": "same family, the son and the neighbour"})
    assert r.status_code == 200, r.text
    after = _loc(app_db, r.json()["kept"])
    assert after["radius_m"] < before["radius_m"], (before, after)                       # never wider, here tighter
    assert after["location_method"].endswith("· both reports' landmarks") and "bridge" in after["location_method"]
    lines = [e["line"] for e in client.get(f"/v1/cases/{r.json()['kept']}/timeline").json()["events"]]
    assert any(x.startswith(f"The circle tightened with {r.json()['absorbed']}'s report: {before['radius_m']} m → ") for x in lines)
    undo = client.post(f"/v1/merges/{one(app_db, 'SELECT max(id) FROM merges')}/undo", json={"reason": "check the undo"})
    assert undo.status_code == 200 and _loc(app_db, a) == before                          # undo restores the old circle


def test_a_pin_a_person_set_is_never_replaced_by_a_derived_one(seeded, client, app_db):
    register_handlers()
    login(client, "rdas")
    a = _report(client, app_db, "Thawe gaon mein, Durga mandir ke peeche, 6 log chhat par fase hain", "+91 98765 74011")
    lat, lng = one(app_db, "SELECT array[ST_Y(geom::geometry), ST_X(geom::geometry)] FROM cases WHERE public_id = :p", p=a)
    assert client.patch(f"/v1/cases/{a}/location", json={"lat": lat + 0.0003, "lng": lng, "reason": "caller confirmed on phone"}).status_code == 200
    b = _report(client, app_db, "Thawe gaon mein, pul ke paas, 6 log chhat par fase hain", "+91 98765 74012")
    pinned = _loc(app_db, a)
    client.post("/v1/merges", json={"cases": [a, b], "reason": "same family"})
    assert _loc(app_db, a) == pinned and pinned["location_source"] == "human"


def test_a_merged_report_from_outside_the_circle_is_only_a_proposed_move(seeded, client, app_db):
    register_handlers()
    login(client, "rdas")
    a = _report(client, app_db, "Thawe gaon mein, Durga mandir ke peeche, 6 log chhat par fase hain", "+91 98765 74021")
    b = _report(client, app_db, "Mirganj mein, station ke paas, 6 log chhat par fase hain", "+91 98765 74022")
    before = _loc(app_db, a)
    r = client.post("/v1/merges", json={"cases": [a, b], "reason": "the family moved to the station roof"})
    assert r.status_code == 200 and _loc(app_db, r.json()["kept"]) == before            # the pin doesn't move by itself
    move = one(app_db, "SELECT attributes->'proposed_move' FROM cases WHERE public_id = :p", p=r.json()["kept"])
    assert move["from"] == r.json()["absorbed"] and move["metres_away"] > before["radius_m"]
    lines = [e["line"] for e in client.get(f"/v1/cases/{r.json()['kept']}/timeline").json()["events"]]
    assert any("outside the circle: a proposed move, for a person to accept (the pin stays)" in x for x in lines)
