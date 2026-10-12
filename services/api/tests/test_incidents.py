"""Incidents as data (PRD F-C1 "done when"): a fourth incident is created through the API and receives reports
with no code change; each incident carries its own promise bar; the lifecycle only moves forward."""

import uuid

from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = [needs_db]

ASSAM = {"code": "AS", "name": "Assam floods, Oct 2026", "type": "flood", "states": ["Assam"], "center": [26.1445, 91.7362],
         "districts": [{"name": "Kamrup Metropolitan", "state": "Assam", "centroid": [26.1445, 91.7362]}]}


def test_each_incident_has_its_own_promise_bar_and_the_seoc_sees_only_its_state(seeded, client):
    login(client, "admin")
    codes = [i["code"] for i in client.get("/v1/incidents").json()]
    assert codes == ["BR", "OD", "HP", "MH"]
    login(client, "seoc")
    incs = client.get("/v1/incidents").json()
    assert [i["code"] for i in incs] == ["BR"] and incs[0]["promises"]["lost"]["adds_up"]


def test_a_fourth_incident_by_curl_receives_reports_with_no_code_change(seeded, client, app_db):
    register_handlers()
    login(client, "admin")
    r = client.post("/v1/incidents", json=ASSAM)
    assert r.status_code == 201, r.text
    assert client.post("/v1/incidents", json=ASSAM).status_code == 409
    report = {"schema_version": "1", "idempotency_key": str(uuid.uuid4()), "channel": "web_form", "incident_hint": "AS",
              "content": {"text": "Hamare ghar mein paani ghus gaya hai, 5 log chhat par hain"}}
    assert client.post("/v1/ingest/reports", json=report).status_code == 202
    drain(app_db)
    pid = one(app_db, "SELECT c.public_id FROM cases c JOIN incidents i ON i.id = c.incident_id WHERE i.code = 'AS'")
    assert pid == "AS-1"
    bar = client.get("/v1/metrics/promises?incident=AS").json()
    assert bar["lost"]["reports"] == 1 and bar["lost"]["cases"] == 1 and bar["lost"]["adds_up"]


def test_the_lifecycle_only_moves_forward(seeded, client):
    login(client, "admin")
    iid = client.post("/v1/incidents", json={**ASSAM, "code": "ASX"}).json()["incident_id"]
    assert client.patch(f"/v1/incidents/{iid}", json={"status": "closed", "reason": "too soon"}).status_code == 409
    assert client.patch(f"/v1/incidents/{iid}", json={"status": "standing_down", "reason": "water receding"}).status_code == 200
    assert client.patch(f"/v1/incidents/{iid}", json={"status": "closed", "reason": "all cases closed"}).status_code == 200
    login(client, "rdas")
    assert client.patch(f"/v1/incidents/{iid}", json={"status": "active", "reason": "x" * 5}).status_code == 403
