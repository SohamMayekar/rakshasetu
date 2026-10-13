"""Telemetry: a partner's signed sensor readings, read against two lines; only a change of state is on the chain."""

import json
import time
import uuid

import pytest

from app.channels.partner import sign
from tests.conftest import login, needs_db, one

pytestmark = needs_db
SECRET = "test-partner-secret"


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("PARTNER_DEMO_SECRET", SECRET)


def _reading(client, value, *, incident="BR", key=None, ts=None, secret=SECRET, **sensor):
    spec = {"code": "G-03", "name": "Gandak gauge", "kind": "water_level", "unit": "m", "warn_at": 3.0, "danger_at": 4.0, **sensor}
    body = {"idempotency_key": key or f"reading-{uuid.uuid4()}", "incident": incident, "value": value, "simulated": True, "sensor": spec}
    raw = json.dumps(body).encode()
    ts = str(ts if ts is not None else int(time.time()))
    return client.post("/v1/ingest/telemetry", content=raw, headers={
        "Content-Type": "application/json", "X-RakshaSetu-Partner": "demo-partner", "X-RakshaSetu-Timestamp": ts,
        "X-RakshaSetu-Signature": sign(secret, ts, raw), "Idempotency-Key": body["idempotency_key"]})


def test_a_reading_creates_the_sensor_and_only_a_change_of_state_is_on_the_chain(seeded, public_client, app_db):
    assert _reading(public_client, 1.2).status_code == 202            # unknown → ok: nothing to say
    assert _reading(public_client, 3.4).json()["state"] == "warn"
    assert _reading(public_client, 3.5).json()["state"] == "warn"     # no change: no event
    assert _reading(public_client, 4.3).json()["state"] == "danger"
    changes = one(app_db, "SELECT count(*) FROM events WHERE action = 'sensor.state_changed'")
    assert changes == 2
    assert one(app_db, "SELECT count(*) FROM sensor_readings") == 4
    assert one(app_db, "SELECT state FROM sensors WHERE code = 'G-03'") == "danger"


def test_a_replayed_reading_is_counted_once(seeded, public_client, app_db):
    first = _reading(public_client, 2.0, key="same-reading-key-1")
    again = _reading(public_client, 2.0, key="same-reading-key-1")
    assert first.status_code == 202 and again.status_code == 200
    assert again.headers["Idempotent-Replay"] == "true"
    assert one(app_db, "SELECT count(*) FROM sensor_readings") == 1


def test_a_bad_signature_and_a_stale_timestamp_are_refused(seeded, public_client, app_db):
    assert _reading(public_client, 2.0, secret="wrong").status_code == 401
    assert _reading(public_client, 2.0, ts=int(time.time()) - 900).status_code == 401
    assert one(app_db, "SELECT count(*) FROM sensors") == 0


def test_the_desk_sees_sensors_in_its_scope_and_the_public_does_not(seeded, client, public_client):
    _reading(public_client, 4.5, incident="BR")
    assert public_client.get("/v1/telemetry").status_code in (401, 404)   # the local listener only
    login(client, "admin")
    sensors = client.get("/v1/telemetry").json()
    assert [s["code"] for s in sensors] == ["G-03"]
    assert sensors[0]["state"] == "danger" and sensors[0]["simulated"] is True and sensors[0]["trend"] == [4.5]
    login(client, "spatil")   # the Mumbai duty officer: not in Bihar
    assert client.get("/v1/telemetry").json() == []
