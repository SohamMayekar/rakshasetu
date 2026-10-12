"""Outbound partner webhooks (PRD §11.4): what a subscribed partner hears from us, signed like every partner call.

    report.created    a report has been read: its structured facts, the circle and the time. No phone, no names,
                      no words (they can hold either): a partner gets facts, never people.
    evidence.created  a media item (audio) with a link that works for 15 minutes. Text records (the message as
                      received, transcripts, sheet rows) are never sent: they carry names and numbers.
    case.updated      a case's state after a change: status, priority, headcount, the circle, its version.
    audit.head        our audit head (seq + hash) every 5 min, for a partner to anchor in its own ledger.

How: the ticker calls dispatch() every 5 s. For each partner with a webhook URL it reads the events after that
partner's cursor (webhook_cursors), keeps the ones in its incidents and subscriptions, and enqueues one
`webhook.deliver` job per delivery (dedupe keys make a re-read harmless). The worker posts it, signed with the
partner's own secret (X-RakshaSetu-Timestamp + X-RakshaSetu-Signature: v1=HMAC-SHA256(secret, ts + "." + body)),
with X-RakshaSetu-Delivery as the receiver's idempotency key. A non-2xx answer or a network error is retried
with backoff (jobs, R20), so a partner can get a delivery twice and must dedupe by its id. Every attempt is a
row in the partner log ("from us"). Nothing is sent while a partner's URL is unset or the partner is disabled.
"""

import hashlib
import hmac
import json
import os
import time
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import Connection, Engine, text

from app.channels.partner import sign
from app.config import Partner, get_bundle, get_config, parse_duration
from app.core.jobs import enqueue, handler
from app.modules.partners import log as partner_log
from app.settings import get_settings

TOPICS = ("report.created", "evidence.created", "case.updated", "audit.head")
CASE_ACTIONS = {"case.checked", "case.updated", "case.priority_changed", "case.priority_overridden", "case.priority_released",
                "case.location_changed", "case.location_moved", "case.location_tightened", "case.merged", "case.absorbed",
                "case.unmerged", "case.closed", "case.cancelled", "case.reopened", "assignment.created", "assignment.acknowledged",
                "assignment.reached", "assignment.reassigned", "assignment.released", "rescue.recorded", "rescue.partial",
                "rescue.confirmed", "rescue.disputed"}
MEDIA = {"audio"}


def _cfg() -> dict:
    return get_config().webhooks or {}


def url_of(p: Partner) -> str:
    return os.environ.get(p.webhook_url_env, "").strip() if p.webhook_url_env else ""


def subscribed() -> list[Partner]:
    return [p for p in get_bundle().partners if p.enabled and url_of(p) and p.subscriptions]


def _lane(p: Partner) -> str:
    return p.lane or "whatsapp_partner"


# --- what goes into a delivery (read when it is sent, so it is current; never a phone, a name or the words) ---

def _circle(c) -> dict | None:
    if c.lat is None:
        return None
    return {"lat": round(c.lat, 5), "lng": round(c.lng, 5), "radius_m": c.radius_m, "confidence": c.location_confidence}


CASE_SQL = ("SELECT c.id, c.public_id, i.code AS incident, c.status, c.priority, c.people_count, c.people_count_kind,"
            " c.people_remaining, c.hazards, c.needs, c.vulnerable, c.radius_m, c.location_confidence, c.location_text,"
            " ST_Y(c.geom::geometry) AS lat, ST_X(c.geom::geometry) AS lng, c.version, c.updated_at"
            " FROM cases c JOIN incidents i ON i.id = c.incident_id WHERE c.id = :c")


def case_data(conn: Connection, case_id: int) -> dict | None:
    c = conn.execute(text(CASE_SQL), {"c": case_id}).one_or_none()
    if c is None:
        return None
    return {"case": c.public_id, "incident": c.incident, "status": c.status, "priority": c.priority,
            "people": {"count": c.people_count, "kind": c.people_count_kind, "remaining": c.people_remaining},
            "hazards": list(c.hazards or []), "needs": list(c.needs or []), "vulnerable": list(c.vulnerable or []),
            "place": c.location_text, "circle": _circle(c), "version": c.version, "updated_at": c.updated_at.isoformat()}


def report_data(conn: Connection, report_id: int) -> dict | None:
    """None until the pipeline has read it (the delivery then waits; see deliver()); {} if it is gone."""
    r = conn.execute(text("SELECT r.id, r.case_id, r.channel, r.received_at, r.extraction_method, r.is_forward"
                          " FROM reports r WHERE r.id = :r"), {"r": report_id}).one_or_none()
    if r is None:
        return {}
    if r.case_id is None:
        return None
    case = case_data(conn, r.case_id)
    return {"report_id": r.id, "received_at": r.received_at.isoformat(), "channel": r.channel, "is_forward": r.is_forward,
            "read_by": r.extraction_method, **(case or {})}


def evidence_url(p: Partner, evidence_id: int, ttl: timedelta | None = None) -> tuple[str, int]:
    exp = int(time.time() + (ttl or parse_duration(_cfg().get("evidence_url_ttl", "15m"))).total_seconds())
    base = (get_settings().public_url or "").rstrip("/")
    return f"{base}/v1/partners/evidence/{evidence_id}/file?p={p.id}&exp={exp}&sig={link_sig(p.id, evidence_id, exp)}", exp


def link_sig(partner: str, evidence_id: int, exp: int) -> str:
    key = (get_settings().secret_key or "").encode()
    return hmac.new(key, f"{partner}.{evidence_id}.{exp}".encode(), hashlib.sha256).hexdigest()


def link_ok(partner: str, evidence_id: int, exp: int, sig: str) -> bool:
    return exp >= time.time() and hmac.compare_digest(sig, link_sig(partner, evidence_id, exp))


# --- a reset is not news: the streams pause during one and restart at "now" after it ------------------------

RESET_LOCK = (72, 4)   # two-key advisory lock: never collides with R1's lock(1) or the dedupe hashtext locks


@contextmanager
def quiet_streams(engine: Engine):
    """Hold this around a seed or a demo reset. The ticker skips dispatch while it is held, and on the way out
    every partner's stream restarts at the current head with nothing queued, so a partner never receives the
    seed or a replayed scene as if it were new."""
    conn = engine.connect()
    conn.execute(text("SELECT pg_advisory_lock(:a, :b)"), {"a": RESET_LOCK[0], "b": RESET_LOCK[1]})
    conn.commit()
    try:
        yield
    finally:
        with conn.begin():
            restart_streams(conn)
        conn.execute(text("SELECT pg_advisory_unlock(:a, :b)"), {"a": RESET_LOCK[0], "b": RESET_LOCK[1]})
        conn.commit()
        conn.close()


def restart_streams(conn: Connection) -> None:
    head = conn.execute(text("SELECT coalesce(max(seq), 0) FROM events")).scalar_one()
    for p in get_bundle().partners:
        conn.execute(text("INSERT INTO webhook_cursors (partner, last_seq) VALUES (:p, :s)"
                          " ON CONFLICT (partner) DO UPDATE SET last_seq = :s, last_head_at = NULL"), {"p": p.id, "s": head})
    conn.execute(text("DELETE FROM jobs WHERE kind = 'webhook.deliver' AND done_at IS NULL"))


# --- dispatch: events → deliveries (the ticker, every 5 s) -----------------------------------------------------

def dispatch(engine: Engine) -> int:
    """Turn new events into delivery jobs for every subscribed partner. Returns how many were enqueued."""
    made = 0
    for p in subscribed():
        with engine.begin() as conn:
            made += _dispatch_one(conn, p)
    return made


def _dispatch_one(conn: Connection, p: Partner) -> int:
    if not conn.execute(text("SELECT pg_try_advisory_xact_lock_shared(:a, :b)"), {"a": RESET_LOCK[0], "b": RESET_LOCK[1]}).scalar():
        return 0                                  # a seed or a demo reset is running: say nothing until it ends
    head = conn.execute(text("SELECT seq, hash, at FROM events ORDER BY seq DESC LIMIT 1")).one_or_none()
    if head is None:
        return 0
    cur = conn.execute(text("SELECT last_seq, last_head_at FROM webhook_cursors WHERE partner = :p FOR UPDATE"),
                       {"p": p.id}).one_or_none()
    if cur is None or cur.last_seq > head.seq:   # first time, or the demo was reset: start from now, replay nothing
        conn.execute(text("INSERT INTO webhook_cursors (partner, last_seq) VALUES (:p, :s)"
                          " ON CONFLICT (partner) DO UPDATE SET last_seq = :s, last_head_at = NULL"), {"p": p.id, "s": head.seq})
        cur = conn.execute(text("SELECT last_seq, last_head_at FROM webhook_cursors WHERE partner = :p"), {"p": p.id}).one()
    made = 0
    rows = conn.execute(text(
        "SELECT e.seq, e.action, e.entity_type, e.entity_id, e.case_id, i.code AS incident"
        " FROM events e LEFT JOIN incidents i ON i.id = e.incident_id WHERE e.seq > :s ORDER BY e.seq LIMIT :n"),
        {"s": cur.last_seq, "n": int(_cfg().get("batch", 500))}).all()
    for e in rows:
        if p.incidents and e.incident not in p.incidents:
            continue
        for topic, ref, key in _topics(conn, p, e):
            made += enqueue(conn, "webhook.deliver", {"partner": p.id, "topic": topic, "ref": ref}, _lane(p),
                            dedupe_key=f"wh:{p.id}:{key}", max_attempts=int(_cfg().get("max_attempts", 6))) is not None
    last = rows[-1].seq if rows else cur.last_seq
    every = parse_duration(_cfg().get("audit_head_every", "5m"))
    head_due = "audit.head" in p.subscriptions and (cur.last_head_at is None or cur.last_head_at < datetime.now(UTC) - every)
    if head_due:
        made += enqueue(conn, "webhook.deliver", {"partner": p.id, "topic": "audit.head",
                                                  "ref": {"seq": head.seq, "head_hash": head.hash, "at": head.at.isoformat()}},
                        _lane(p), dedupe_key=f"wh:{p.id}:head:{head.seq}", max_attempts=int(_cfg().get("max_attempts", 6))) is not None
    conn.execute(text("UPDATE webhook_cursors SET last_seq = :s, last_head_at = CASE WHEN :h THEN now() ELSE last_head_at END"
                      " WHERE partner = :p"), {"s": last, "h": head_due, "p": p.id})
    return made


def _topics(conn: Connection, p: Partner, e) -> list[tuple[str, dict, str]]:
    out = []
    subs = set(p.subscriptions)
    if e.action == "report.received" and "report.created" in subs:
        out.append(("report.created", {"report_id": int(e.entity_id)}, f"report:{e.entity_id}"))
    if e.action == "evidence.added" and "evidence.created" in subs:
        ev = conn.execute(text("SELECT id, type FROM evidence WHERE id = :i"), {"i": int(e.entity_id)}).one_or_none()
        if ev is not None and ev.type in MEDIA:
            out.append(("evidence.created", {"evidence_id": ev.id}, f"evidence:{ev.id}"))
    if e.action in CASE_ACTIONS and e.case_id is not None and "case.updated" in subs:
        version = conn.execute(text("SELECT version FROM cases WHERE id = :c"), {"c": e.case_id}).scalar()
        out.append(("case.updated", {"case_id": e.case_id}, f"case:{e.case_id}:v{version}"))   # one per case version
    return out


# --- delivery (the worker) ------------------------------------------------------------------------------------

def build(conn: Connection, p: Partner, topic: str, ref: dict) -> dict | None:
    if topic == "report.created":
        data = report_data(conn, ref["report_id"])
    elif topic == "evidence.created":
        ev = conn.execute(text("SELECT e.id, e.type, e.sha256, e.mime, e.bytes, e.captured_at, c.public_id, i.code"
                               " FROM evidence e LEFT JOIN cases c ON c.id = e.case_id LEFT JOIN incidents i ON i.id = c.incident_id"
                               " WHERE e.id = :i"), {"i": ref["evidence_id"]}).one_or_none()
        if ev is None:
            return {}
        url, exp = evidence_url(p, ev.id)
        data = {"evidence_id": ev.id, "case": ev.public_id, "incident": ev.code, "type": ev.type, "sha256": ev.sha256,
                "mime": ev.mime, "bytes": ev.bytes, "captured_at": ev.captured_at.isoformat(), "url": url,
                "url_expires_at": datetime.fromtimestamp(exp, UTC).isoformat()}
    elif topic == "case.updated":
        data = case_data(conn, ref["case_id"]) or {}
    else:
        data = dict(ref)
    return data


@handler("webhook.deliver")
def deliver(engine: Engine, payload: dict) -> None:
    from app.core.jobs import RetryLater
    p = next((x for x in get_bundle().partners if x.id == payload["partner"]), None)
    url = url_of(p) if p else ""
    if p is None or not p.enabled or not url:
        return                                     # switched off since it was queued: drop it, quietly
    with engine.connect() as conn:
        data = build(conn, p, payload["topic"], payload["ref"])
    if data is None:
        raise RetryLater(5, "the report hasn't been read yet")
    if data == {}:
        return                                     # the thing is gone (a demo reset): nothing to say
    delivery = str(uuid.uuid5(uuid.NAMESPACE_URL, f"rakshasetu:{p.id}:{payload['topic']}:{json.dumps(payload['ref'], sort_keys=True)}"))
    body = json.dumps({"id": delivery, "topic": payload["topic"], "sent_at": datetime.now(UTC).isoformat(), "data": data},
                      ensure_ascii=False, separators=(",", ":")).encode()
    secret = os.environ.get(p.secret_env, "")
    ts = str(int(time.time()))
    headers = {"Content-Type": "application/json", "X-RakshaSetu-Event": payload["topic"], "X-RakshaSetu-Delivery": delivery,
               "X-RakshaSetu-Timestamp": ts, "X-RakshaSetu-Signature": sign(secret, ts, body), "User-Agent": "RakshaSetu-Webhooks/1"}
    t0 = time.perf_counter()
    status, why = 0, None
    try:
        r = httpx.post(url, content=body, headers=headers, timeout=float(_cfg().get("timeout_s", 5)))
        status = r.status_code
        why = None if r.is_success else f"{status} · {r.text[:120]}"
    except httpx.HTTPError as e:
        why = f"network · {type(e).__name__}"
    partner_log.write(p.id, "out", "POST", f"{payload['topic']} → {_host(url)}", status, int((time.perf_counter() - t0) * 1000),
                      {"body_sha256": partner_log.body_hash(body), "note": why, "signature_ok": None})
    if why:
        raise RuntimeError(f"webhook {payload['topic']} to {p.id} not accepted: {why}")   # retried with backoff


def _host(url: str) -> str:
    return httpx.URL(url).host or url
