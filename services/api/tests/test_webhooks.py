"""PRD §11.4: outbound partner webhooks. Signed with the partner's secret, delivered as retried jobs, logged in the
partner log; report.created carries facts and the circle but never a phone, a name or the words; media links
work for 15 minutes; nothing is sent without a URL."""

import json
import os
import threading
import uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jsonschema
import pytest
from sqlalchemy import text

from app.core.jobs import drain
from app.modules.partners import webhooks
from app.pipeline import register_handlers
from app.webhook_sink import verified
from tests.conftest import login, needs_db, one, rows

pytestmark = needs_db
SECRET = "test-partner-secret"


class Receiver:
    """A partner's endpoint on a free local port: keeps what it was sent; answers `status`."""
    def __init__(self):
        self.got: list[dict] = []
        self.status = 200
        me = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                me.got.append({"headers": dict(self.headers), "raw": raw, "why_not": verified(self.headers, raw)})
                self.send_response(me.status)
                self.end_headers()

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/hook"

    def bodies(self, topic=None) -> list[dict]:
        out = [json.loads(g["raw"]) for g in self.got]
        return [b for b in out if topic is None or b["topic"] == topic]


@pytest.fixture
def partner(monkeypatch):
    monkeypatch.setenv("PARTNER_DEMO_SECRET", SECRET)
    monkeypatch.setattr("app.webhook_sink.SECRET", SECRET)
    r = Receiver()
    monkeypatch.setenv("DEMO_PARTNER_WEBHOOK_URL", r.url)
    yield r
    r.server.shutdown()


def contract(name: str) -> dict:
    """A schema from packages/contracts, the partner contract card's own files."""
    with open(os.path.join(os.environ.get("CONTRACTS_DIR", "/contracts"), name)) as f:
        return json.load(f)


def _run(app_db):
    """The ticker's dispatch, then the worker; deliveries waiting for their report are made runnable again."""
    for _ in range(3):
        webhooks.dispatch(app_db)
        drain(app_db)
        with app_db.begin() as c:
            c.execute(text("UPDATE jobs SET run_at = now() WHERE kind = 'webhook.deliver' AND done_at IS NULL AND dead_at IS NULL"))


def test_a_new_report_is_one_signed_report_created_with_facts_but_no_people(seeded, client, app_db, partner):
    register_handlers()
    webhooks.dispatch(app_db)                     # the first look starts the stream at "now": history is not replayed
    login(client, "rdas")
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "phone": "+91 98765 74101", "client_id": str(uuid.uuid4()),
                                               "text": "Ramesh Das's family is in Thawe village, behind the Durga temple. 6 people are stuck on the roof"}).json()["report_id"]
    _run(app_db)
    (b,) = [b for b in partner.bodies("report.created") if b["data"]["report_id"] == rid]
    d = b["data"]
    assert d["people"]["count"] == 6 and "trapped_on_roof" in d["hazards"] and d["circle"]["radius_m"] > 0 and d["case"].startswith("BR-")
    raw = next(g["raw"] for g in partner.got if json.loads(g["raw"])["id"] == b["id"]).decode()
    assert "Ramesh" not in raw and "98765" not in raw and "Durga temple" not in raw     # facts, never people or words
    g = next(g for g in partner.got if json.loads(g["raw"])["id"] == b["id"])
    assert g["why_not"] is None and g["headers"]["X-RakshaSetu-Event"] == "report.created"   # the partner can verify us
    assert g["headers"]["X-RakshaSetu-Delivery"] == b["id"]
    log = rows(app_db, "SELECT status, endpoint FROM partner_calls WHERE direction = 'out' AND endpoint LIKE 'report.created%'")
    assert log and all(r.status == 200 for r in log)
    assert sum(x["data"]["report_id"] == rid for x in partner.bodies("report.created")) == 1   # once, however often we look
    for body in partner.bodies():                                                     # what we send is what the card says
        jsonschema.validate(body, contract("webhook.schema.json"))


def test_a_refused_delivery_is_retried_and_every_attempt_is_in_the_partner_log(seeded, client, app_db, partner):
    register_handlers()
    webhooks.dispatch(app_db)
    partner.status = 500
    login(client, "rdas")
    pid = one(app_db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE c.status = 'reported'"
                      " AND c.checked_at IS NULL AND d.name = 'Gopalganj' ORDER BY c.id LIMIT 1")   # R. Das's district
    assert client.post(f"/v1/cases/{pid}/check", json={}).status_code == 200
    webhooks.dispatch(app_db)
    drain(app_db)
    job = rows(app_db, "SELECT attempts, done_at, error FROM jobs WHERE kind = 'webhook.deliver' AND payload->>'topic' = 'case.updated'")[0]
    assert job.attempts == 1 and job.done_at is None and "500" in job.error           # will be tried again, with backoff
    partner.status = 200
    _run(app_db)
    calls = [r.status for r in rows(app_db, "SELECT status FROM partner_calls WHERE direction = 'out' AND endpoint LIKE 'case.updated%' ORDER BY id")]
    assert calls[0] == 500 and calls[-1] == 200
    (b,) = partner.bodies("case.updated")[-1:]
    assert b["data"]["case"] == pid and b["data"]["status"] == "checked"


def test_audit_head_goes_out_on_its_interval(seeded, client, app_db, partner):
    register_handlers()
    _run(app_db)
    head = one(app_db, "SELECT max(seq) FROM events")
    (b,) = partner.bodies("audit.head")
    assert b["data"]["seq"] <= head and len(b["data"]["head_hash"]) == 64
    login(client, "rdas")
    pid = one(app_db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE c.checked_at IS NULL"
                      " AND c.status = 'reported' AND d.name = 'Gopalganj' ORDER BY c.id LIMIT 1")
    client.post(f"/v1/cases/{pid}/check", json={})                                       # the head moves on
    _run(app_db)
    assert len(partner.bodies("audit.head")) == 1                                       # but not again until 5 min have passed
    with app_db.begin() as c:
        c.execute(text("UPDATE webhook_cursors SET last_head_at = now() - interval '6 minutes'"))
    _run(app_db)
    heads = [x["data"]["seq"] for x in partner.bodies("audit.head")]
    assert len(heads) == 2 and heads[1] > heads[0]                                     # the new head; the same head is never sent twice


def test_a_media_link_works_for_its_partner_until_it_expires(seeded, app_db, public_client):
    from app.config import get_bundle
    from app.modules.evidence.service import add
    p = next(x for x in get_bundle().partners if x.id == "demo-partner")
    case = one(app_db, "SELECT to_jsonb(x) FROM (SELECT id, incident_id, district_id FROM cases ORDER BY id LIMIT 1) x")
    with app_db.begin() as c:
        from app.core.eventlog import Actor
        audio = add(c, type="audio", content=b"OggS fake clip", mime="audio/ogg", actor=Actor("system", None, "system"),
                    added_by="test", meta={}, case_id=case["id"], incident_id=case["incident_id"], district_id=case["district_id"])
        note = add(c, type="message", content=b"Ramesh, +91 98765 74101", mime="text/plain", actor=Actor("system", None, "system"),
                   added_by="test", meta={}, case_id=case["id"], incident_id=case["incident_id"], district_id=case["district_id"])
    url, _ = webhooks.evidence_url(p, audio)
    path = url[url.index("/v1/"):]
    r = public_client.get(path)
    assert r.status_code == 200 and r.content == b"OggS fake clip"
    assert public_client.get(path.replace("sig=", "sig=0")).status_code == 403                       # tampered
    old, _ = webhooks.evidence_url(p, audio, ttl=timedelta(seconds=-1))
    assert public_client.get(old[old.index("/v1/"):]).status_code == 403                             # expired
    text_url, _ = webhooks.evidence_url(p, note)
    assert public_client.get(text_url[text_url.index("/v1/"):]).status_code == 404                   # text never leaves


def test_without_a_url_nothing_is_sent(seeded, app_db, monkeypatch):
    monkeypatch.delenv("DEMO_PARTNER_WEBHOOK_URL", raising=False)
    assert webhooks.dispatch(app_db) == 0
    assert one(app_db, "SELECT count(*) FROM webhook_cursors") == 0


def test_a_reset_is_not_news(seeded, client, app_db, owner_db, partner):
    """While a seed or demo reset holds the streams, nothing is dispatched; afterwards each stream restarts at the
    head with nothing queued, so the partner never receives the seed or a replayed scene."""
    register_handlers()
    webhooks.dispatch(app_db)
    login(client, "rdas")
    with webhooks.quiet_streams(owner_db):
        client.post("/v1/ingest/desk", json={"incident": "BR", "text": "In Mirganj village 4 people are on the roof",
                                             "client_id": str(uuid.uuid4())})
        drain(app_db, kinds=["report.process"])
        assert webhooks.dispatch(app_db) == 0
    assert one(app_db, "SELECT last_seq FROM webhook_cursors WHERE partner = 'demo-partner'") == one(app_db, "SELECT max(seq) FROM events")
    assert one(app_db, "SELECT count(*) FROM jobs WHERE kind = 'webhook.deliver' AND done_at IS NULL") == 0
    _run(app_db)
    assert not partner.bodies("report.created")


def test_the_contract_cards_annotation_schema_matches_what_we_accept():
    schema = contract("annotation.schema.json")
    good = [{"idempotency_key": "ann-00000001", "kind": "priority", "target": {"case": "BR-199"}, "value": "P1", "confidence": 0.78},
            {"idempotency_key": "ann-00000002", "kind": "credibility", "target": {"evidence_sha256": "a" * 64}, "value": "likely recycled"},
            {"idempotency_key": "ann-00000003", "kind": "anchor_receipt", "target": {"seq": 232, "head_hash": "b" * 64}, "value": "tx 0xab"}]
    for body in good:
        jsonschema.validate(body, schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**good[0], "value": "urgent"}, schema)                    # a priority is P1–P4
