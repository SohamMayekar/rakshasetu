"""T1 (PRD §13.6, scenario L): the same report posted twice → one report; a replay returns the original id.
Also: idempotency keys are namespaced by the authenticated source, never taken from the body."""

import pytest

from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = [needs_db, pytest.mark.scenario]

BODY = {"schema_version": "1", "idempotency_key": "call-0001", "channel": "web_form", "incident_hint": "BR",
        "reporter": {"phone": "+91 98765 30001", "relation": "family"},
        "content": {"text": "Thawe mein 6 log chhat par fase hain"}}


def test_t1_same_report_twice_is_one_report_and_the_replay_returns_the_original(seeded, client, app_db):
    login(client, "priya")
    first = client.post("/v1/ingest/reports", json=BODY)
    again = client.post("/v1/ingest/reports", json=BODY)
    assert first.status_code == 202 and "Idempotent-Replay" not in first.headers
    assert again.status_code == 200 and again.headers["Idempotent-Replay"] == "true"
    assert again.json()["report_id"] == first.json()["report_id"]
    assert one(app_db, "SELECT count(*) FROM reports WHERE idempotency_key = 'call-0001'") == 1
    assert one(app_db, "SELECT count(*) FROM jobs WHERE payload->>'report_id' = :r", r=str(first.json()["report_id"])) == 1
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'report.received'"
                       " AND (body::jsonb->'data'->>'report_id')::int = :r", r=first.json()["report_id"]) == 1


def test_t1_keys_are_namespaced_by_the_authenticated_source(seeded, client, app_db):
    login(client, "priya")
    a = client.post("/v1/ingest/reports", json=BODY).json()["report_id"]
    login(client, "rdas")                       # a different caller can't collide with (or pre-claim) priya's key
    b = client.post("/v1/ingest/reports", json=BODY).json()["report_id"]
    assert a != b
    assert {r for r in [one(app_db, "SELECT source_ns FROM reports WHERE id = :i", i=a),
                        one(app_db, "SELECT source_ns FROM reports WHERE id = :i", i=b)]} == {
        f"user:{one(app_db, 'SELECT id FROM users WHERE username = :u', u='priya')}",
        f"user:{one(app_db, 'SELECT id FROM users WHERE username = :u', u='rdas')}"}


def test_t1_one_report_becomes_exactly_one_case_even_if_processed_twice(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    rid = client.post("/v1/ingest/reports", json=BODY).json()["report_id"]
    drain(app_db)
    from app.pipeline.run import process_report
    process_report(app_db, {"report_id": rid})        # a duplicate delivery of the same job
    assert one(app_db, "SELECT count(*) FROM cases c JOIN reports r ON r.case_id = c.id WHERE r.id = :r", r=rid) == 1
    case = client.get(f"/v1/cases/{one(app_db, 'SELECT case_id FROM reports WHERE id = :r', r=rid)}").json()
    assert case["district"] == "Gopalganj" and case["priority"] == "P4"


def test_the_report_text_is_kept_verbatim(seeded, client, app_db):
    login(client, "priya")
    rid = client.post("/v1/ingest/reports", json=BODY).json()["report_id"]
    assert one(app_db, "SELECT text FROM reports WHERE id = :r", r=rid) == BODY["content"]["text"]


def test_a_malformed_report_is_refused_with_422(seeded, client):
    login(client, "priya")
    assert client.post("/v1/ingest/reports", json={**BODY, "channel": "sms"}).status_code == 422
    assert client.post("/v1/ingest/reports", json={**BODY, "priority": "P1"}).status_code == 422
