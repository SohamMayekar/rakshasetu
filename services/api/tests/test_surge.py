"""PRD F-C5: the surge generator's reports are honest synthetic data, queue behind real work, and show up on
the surge screen (/v1/metrics/surge)."""

import json
import random
import time

import pytest

from app.channels.partner import sign
from app.core.jobs import drain
from app.pipeline import register_handlers
from app.surge import household
from tests.conftest import login, needs_db, one

SECRET = "test-partner-secret"


def _quotes(ex: dict) -> list[str]:
    loc = ex["location"]
    return [q for q in [ex["people_count"]["quote"], *(x["quote"] for k in ("hazards", "needs", "vulnerable") for x in ex[k]),
                        *(p["quote"] for p in ex["person_names"]), *(lm["quote"] for lm in loc["landmarks"]),
                        (loc["village_or_locality"] or {}).get("quote")] if q]


def test_every_generated_fact_quotes_the_report_text():
    rng = random.Random(7)
    for n in range(500):
        h = household(rng, n)
        assert h["phone"].startswith("+9199")                              # synthetic numbers only
        assert all(q in h["text"] for q in _quotes(h["structured"])), h
        for p in h["structured"]["person_names"]:
            assert p["quote"].startswith(p["name"])


def _post(client, partner: str, h: dict, key: str):
    raw = json.dumps({"schema_version": "1", "idempotency_key": key, "channel": "partner", "incident_hint": h["incident"],
                      "reporter": {"phone": h["phone"], "relation": "unknown"}, "content": {"text": h["text"], "language": "hi"},
                      "structured": h["structured"], "source": {"system": "surge.py", "simulated": True}}).encode()
    ts = str(int(time.time()))
    return client.post("/v1/ingest/reports", content=raw, headers={
        "Content-Type": "application/json", "Idempotency-Key": key, "X-RakshaSetu-Partner": partner,
        "X-RakshaSetu-Timestamp": ts, "X-RakshaSetu-Signature": sign(SECRET, ts, raw)})


@needs_db
def test_surge_reports_queue_behind_real_partners_and_show_on_the_surge_screen(seeded, client, public_client, app_db,
                                                                               monkeypatch):
    monkeypatch.setenv("PARTNER_DEMO_SECRET", SECRET)
    register_handlers()
    rng = random.Random(3)
    surge_id = _post(public_client, "surge-generator", household(rng, 1), "surge-t-1").json()["report_id"]
    real_id = _post(public_client, "demo-partner", household(rng, 2), "surge-t-2").json()["report_id"]
    lane_of = "SELECT lane FROM jobs WHERE payload->>'report_id' = CAST(:r AS text)"
    assert one(app_db, lane_of, r=surge_id) == "surge"
    assert one(app_db, lane_of, r=real_id) == "whatsapp_partner"   # a real partner's simulated report isn't demoted

    login(client, "priya")
    m = client.get("/v1/metrics/surge").json()
    assert m["ingest"]["accepted"] >= 2 and m["ingest"]["p95_ms"] is not None
    assert m["lanes"]["surge"]["waiting"] >= 1
    drain(app_db)
    m = client.get("/v1/metrics/surge").json()
    assert "surge" not in m["lanes"] and m["last_minute"]["reports"] >= 2 and m["last_minute"]["cases"] >= 1
    assert one(app_db, "SELECT case_id IS NOT NULL FROM reports WHERE id = :r", r=surge_id)


@needs_db
def test_surge_screen_is_desk_only(seeded, public_client):
    login(public_client, "priya", "rakshasetu")
    assert public_client.get("/v1/metrics/surge").status_code == 404


@pytest.mark.parametrize("user,status", [("priya", 200), ("boat5", 403)])
@needs_db
def test_surge_screen_needs_totals_view(seeded, client, user, status):
    login(client, user)
    assert client.get("/v1/metrics/surge").status_code == status
