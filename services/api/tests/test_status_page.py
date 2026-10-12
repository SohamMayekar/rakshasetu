"""F-L3: the status page shows a step and when it changed, nothing personal, and is rate-limited."""

import re

from sqlalchemy import text

from app.core.eventlog import SYSTEM, append_event
from app.modules.public import router as public_router
from tests.conftest import needs_db, one

pytestmark = needs_db


def test_status_has_the_step_and_no_personal_data(seeded, public_client, app_db):
    r = public_client.get("/v1/public/cases/BR-151/status")
    assert r.status_code == 200
    body = r.json()
    assert set(body) - {"demo"} == {"public_id", "tracked_as", "other_reports", "step", "steps", "last_update_at"}
    assert body.get("demo") is True                       # tests run in DEMO_MODE (the demo QR's device handover)
    assert body["step"] in body["steps"] and body["steps"][1] == "help_assigned"
    raw = r.text
    assert not re.search(r"\+91|98765|xxxxxx", raw)                          # no phone, not even masked
    for word in ("priority", "P1", "lat", "lng", "eta", "escalat", "district", "name", "Gopalganj"):
        assert word not in raw, word


def test_outside_demo_mode_the_status_never_offers_a_device_handover(seeded, public_client, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    assert "demo" not in public_client.get("/v1/public/cases/BR-151/status").json()


def test_a_state_change_shows_within_one_poll(seeded, public_client, app_db, owner_db):
    case_id = one(app_db, "SELECT id FROM cases WHERE public_id = 'BR-151'")
    before = public_client.get("/v1/public/cases/BR-151/status").json()
    with owner_db.begin() as c:
        c.execute(text("UPDATE cases SET status = 'assigned' WHERE id = :c"), {"c": case_id})
        append_event(c, actor=SYSTEM, action="assignment.created", entity_type="assignment", entity_id=0, case_id=case_id)
    after = public_client.get("/v1/public/cases/BR-151/status").json()
    assert (before["step"], after["step"]) == ("registered", "help_assigned")
    assert after["last_update_at"] > before["last_update_at"]


def test_unknown_case_is_404(seeded, public_client):
    assert public_client.get("/v1/public/cases/BR-99999/status").status_code == 404


def test_lookups_are_rate_limited_per_caller(seeded, public_client, monkeypatch):
    public_router._lookups.clear()
    headers = {"CF-Connecting-IP": "203.0.113.50"}
    codes = [public_client.get("/v1/public/cases/BR-151/status", headers=headers).status_code for _ in range(61)]
    assert codes[:60] == [200] * 60 and codes[60] == 429
    assert public_client.get("/v1/public/cases/BR-151/status", headers={"CF-Connecting-IP": "203.0.113.51"}).status_code == 200
