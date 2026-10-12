"""intake.accept(): the single front door for every channel (PRD F-L1, rules R3 and R4).

1. Write first: the report row and its processing job are inserted in ONE transaction, before any AI
   runs, and the report id is returned straight away. If the worker dies, the job is still there.
2. Idempotency: the key is namespaced by the AUTHENTICATED source (`user:7`, `partner:team-ai1`,
   `voice:<device>`, `seed`), set by the server, never read from the body. A retry returns the original
   report id; nothing is inserted twice (`UNIQUE (source_ns, idempotency_key)`).
3. The report is immutable: what someone told us is never edited.
"""

import hashlib
from dataclasses import dataclass

from sqlalchemy import Connection, text

from app.contracts import CanonicalReport
from app.core.eventlog import Actor, append_event
from app.core.jobs import enqueue
from app.core.phones import protect

# Which job lane each channel's processing uses (rule R20). A call-taker typing a live call is as
# urgent as live voice; partner and WhatsApp come next; imports and surge wait their turn.
CHANNEL_LANE = {"voice": "live_voice", "web_form": "live_voice", "whatsapp": "whatsapp_partner",
                "partner": "whatsapp_partner", "spreadsheet": "import"}


@dataclass
class Accepted:
    report_id: int
    replay: bool
    incident_id: int | None


def _incident(conn: Connection, code: str | None) -> tuple[int | None, str | None]:
    if not code:
        return None, None
    r = conn.execute(text("SELECT id, status FROM incidents WHERE code = :c"), {"c": code}).one_or_none()
    return (r.id, r.status) if r else (None, None)


def accept(conn: Connection, report: CanonicalReport, *, source_ns: str, actor: Actor,
           lane: str | None = None, district_id: int | None = None) -> Accepted:
    """Insert the report and its job (one transaction, the caller's). Returns the id, or the original on replay."""
    incident_id, incident_status = _incident(conn, report.incident_hint)
    if incident_status == "closed":
        incident_id = None   # a closed incident is read-only; the report still gets a home in review
    phone = protect(report.reporter.phone)
    text_body = report.content.text
    device_hash = (hashlib.sha256(report.reporter.device_id.encode()).hexdigest()
                   if report.reporter.device_id else None)
    new_id = conn.execute(text(
        "INSERT INTO reports (incident_id, channel, schema_version, source_ns, idempotency_key,"
        " original_reported_at, reporter_phone_enc, reporter_phone_hash, reporter_phone_masked, device_hash,"
        " reporter_name, reporter_relation, is_forward, text_sha256, language, text, structured, source)"
        " VALUES (:inc, :channel, :ver, :ns, :key, :orig, :penc, :phash, :pmask, :dev, :name, :rel, :fwd,"
        "         :tsha, :lang, :text, CAST(:structured AS jsonb), CAST(:source AS jsonb))"
        " ON CONFLICT (source_ns, idempotency_key) DO NOTHING RETURNING id"),
        dict(inc=incident_id, channel=report.channel, ver=report.schema_version, ns=source_ns,
             key=report.idempotency_key, orig=report.received_at, penc=phone["enc"], phash=phone["hash"],
             pmask=phone["masked"], dev=device_hash, name=report.reporter.name, rel=report.reporter.relation,
             fwd=report.reporter.relation == "forwarder",
             tsha=hashlib.sha256(text_body.encode()).hexdigest() if text_body else None,
             lang=report.content.language, text=text_body,
             structured=None if report.structured is None else _json(report.structured),
             source=_json({**report.source.model_dump(mode="json"), "district_hint": district_id}))).scalar()
    if new_id is None:   # a replay: same source, same key
        r = conn.execute(text("SELECT id, incident_id FROM reports WHERE source_ns = :ns AND idempotency_key = :key"),
                         {"ns": source_ns, "key": report.idempotency_key}).one()
        return Accepted(report_id=r.id, replay=True, incident_id=r.incident_id)
    enqueue(conn, "report.process", {"report_id": new_id}, lane or CHANNEL_LANE[report.channel],
            dedupe_key=f"report:{new_id}:process")
    append_event(conn, actor=actor, action="report.received", entity_type="report", entity_id=new_id,
                 incident_id=incident_id, district_id=district_id,
                 data={"report_id": new_id, "channel": report.channel, "source_ns": source_ns,
                       "phone": phone["masked"], "is_forward": report.reporter.relation == "forwarder",
                       "simulated": report.source.simulated})
    return Accepted(report_id=new_id, replay=False, incident_id=incident_id)


def _json(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, default=str)
