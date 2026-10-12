"""F-L1: every P0 channel creates a case through the same code path (one integration test per channel).
Desk and partner here; voice (m20) and spreadsheet (m30) add theirs. Partner signing per rule R19."""

import json
import os
import time
import uuid

import pytest

from app.channels.partner import sign
from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = needs_db
SECRET = "test-partner-secret"


@pytest.fixture(autouse=True)
def _partner_secret(monkeypatch):
    monkeypatch.setenv("PARTNER_DEMO_SECRET", SECRET)
    register_handlers()


def _case_of(app_db, report_id):
    return one(app_db, "SELECT c.public_id FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.id = :r", r=report_id)


def test_desk_paste_becomes_a_case(seeded, client, app_db):
    login(client, "priya")
    r = client.post("/v1/ingest/desk", json={"incident": "BR", "text": "Mirganj mein 4 log fase hain",
                                             "client_id": str(uuid.uuid4()), "phone": "+91 98765 30002",
                                             "pasted_forward": True})
    assert r.status_code == 202
    drain(app_db)
    rid = r.json()["report_id"]
    assert _case_of(app_db, rid).startswith("BR-")
    assert one(app_db, "SELECT channel || '/' || reporter_relation FROM reports WHERE id = :r", r=rid) == "web_form/forwarder"


def test_desk_form_is_local_only(seeded, public_client):
    login(public_client, "priya", "rakshasetu")
    r = public_client.post("/v1/ingest/desk", json={"incident": "BR", "text": "x", "client_id": "abcdefgh"})
    assert r.status_code == 404


def _signed(body: dict, partner="demo-partner", key=None, ts=None, secret=SECRET):
    raw = json.dumps(body).encode()
    ts = str(ts if ts is not None else int(time.time()))
    return raw, {"Content-Type": "application/json", "X-RakshaSetu-Partner": partner,
                 "X-RakshaSetu-Timestamp": ts, "X-RakshaSetu-Signature": sign(secret, ts, raw),
                 "Idempotency-Key": key if key is not None else body["idempotency_key"]}


PARTNER_REPORT = {"schema_version": "1", "idempotency_key": "inc_19", "channel": "partner", "incident_hint": "BR",
                  "content": {"text": "Hathua: 5 log ghar mein band hain"},
                  "source": {"system": "team-ai1", "ref": "inc_19", "simulated": True}}


def test_signed_partner_report_becomes_a_case_once(seeded, public_client, app_db):
    raw, headers = _signed(PARTNER_REPORT)
    first = public_client.post("/v1/ingest/reports", content=raw, headers=headers)
    again = public_client.post("/v1/ingest/reports", content=raw, headers=headers)
    assert first.status_code == 202 and again.status_code == 200 and again.headers["Idempotent-Replay"] == "true"
    drain(app_db)
    rid = first.json()["report_id"]
    assert _case_of(app_db, rid).startswith("BR-")
    assert one(app_db, "SELECT source_ns FROM reports WHERE id = :r", r=rid) == "partner:demo-partner"
    assert one(app_db, "SELECT source->>'simulated' FROM reports WHERE id = :r", r=rid) == "true"


@pytest.mark.parametrize("label,mutate,status", [
    ("bad signature", lambda raw, h: (raw, {**h, "X-RakshaSetu-Signature": "v1=" + "0" * 64}), 401),
    ("body changed after signing", lambda raw, h: (raw.replace(b"5 log", b"9 log"), h), 401),
    ("stale timestamp", None, 401),
    ("unknown partner", lambda raw, h: (raw, {**h, "X-RakshaSetu-Partner": "nobody"}), 401),
    ("missing idempotency key", lambda raw, h: (raw, {k: v for k, v in h.items() if k != "Idempotency-Key"}), 400),
    ("key differs from the body", lambda raw, h: (raw, {**h, "Idempotency-Key": "other"}), 400),
])
def test_partner_signing_rejections(seeded, public_client, label, mutate, status):
    if label == "stale timestamp":
        raw, headers = _signed(PARTNER_REPORT, ts=int(time.time()) - 400)
    else:
        raw, headers = mutate(*_signed(PARTNER_REPORT))
    r = public_client.post("/v1/ingest/reports", content=raw, headers=headers)
    assert r.status_code == status, (label, r.text)
    if label == "stale timestamp":
        assert "replay rejected" in r.json()["detail"]


def test_partner_cannot_report_into_an_incident_it_isnt_scoped_to(seeded, public_client, monkeypatch):
    from app.config import get_bundle
    p = get_bundle().partners[0]
    monkeypatch.setattr(p, "incidents", ["OD"])
    raw, headers = _signed({**PARTNER_REPORT, "idempotency_key": "x1"})
    assert public_client.post("/v1/ingest/reports", content=raw, headers=headers).status_code == 403


def test_disabled_partner_is_refused(seeded, public_client, monkeypatch):
    from app.config import get_bundle
    monkeypatch.setattr(get_bundle().partners[0], "enabled", False)
    raw, headers = _signed({**PARTNER_REPORT, "idempotency_key": "x2"})
    assert public_client.post("/v1/ingest/reports", content=raw, headers=headers).status_code == 401


def test_an_unsigned_anonymous_post_is_refused(seeded, public_client):
    r = public_client.post("/v1/ingest/reports", json=PARTNER_REPORT)
    assert r.status_code == 401
    assert os.environ["PARTNER_DEMO_SECRET"] == SECRET
