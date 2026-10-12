"""The reporter's endpoints (public listener, no login; PRD F-L2, §11.1).

POST /v1/public/voice-turns   one clip (≤ 30 s) from the reporter PWA → report → case
POST /v1/public/text-turns    the PWA's "type instead" link
GET  /v1/public/turns/{id}    the case id once the pipeline has made it (for this device only)

The reply is the one fixed sentence (REPLY), never generated text. The PWA plays the team's recorded clip of
it (apps/web/public/audio/en/registered.mp3, human task H-05) if it exists, and shows the text either way.
English only for now (decision D17).

A reporter is identified only by a random device id the PWA keeps in localStorage. It is hashed, treated
like a phone number in duplicate matching, and links the device to its case for the optional
"Is that right?" check. Caps: 5 voice turns a minute per device and 20 a minute in total (per-IP limits
don't work behind the tunnel or venue NAT).
"""

import asyncio
import hashlib
import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_config
from app.contracts import CanonicalReport, Content, Reporter, Source
from app.core import storage
from app.core.audio import BadAudio, measure, to_wav16k
from app.core.eventlog import Actor
from app.db import get_engine
from app.modules.intake.service import accept
from app.settings import get_settings

router = APIRouter(prefix="/v1/public", tags=["public"])
MAX_UPLOAD = 2 * 1024 * 1024
REPLY = {"en": "Your report is registered. You don't need to remember anything."}


def device_hash(device_id: str) -> str:
    return hashlib.sha256(device_id.encode()).hexdigest()


def _caps(dev: str) -> None:
    caps = get_config().voice_caps
    with get_engine().connect() as c:
        r = c.execute(text("SELECT count(*) FILTER (WHERE device_hash = :d) AS mine, count(*) AS everyone FROM reports"
                           " WHERE channel = 'voice' AND received_at > now() - interval '1 minute'"), {"d": dev}).one()
    if r.mine >= caps["per_device_per_min"] or r.everyone >= caps["global_per_min"]:
        raise HTTPException(429, "Please wait a moment and try again. If urgent, call 112 / 1077.")


def _wait_seconds() -> float:
    return float(os.environ.get("VOICE_WAIT_SECONDS", "15"))


async def _wait_for_case(report_id: int) -> dict:
    """The case is made by the worker straight after the clip; wait briefly so the phone can show its id."""
    deadline = asyncio.get_running_loop().time() + _wait_seconds()
    while True:
        st = await run_in_threadpool(turn_status, report_id)
        if st["public_id"] or asyncio.get_running_loop().time() >= deadline:
            return st
        await asyncio.sleep(0.25)


def turn_status(report_id: int) -> dict:
    with get_engine().connect() as c:
        r = c.execute(text("SELECT r.status, c.public_id FROM reports r LEFT JOIN cases c ON c.id = r.case_id"
                           " WHERE r.id = :id"), {"id": report_id}).one_or_none()
    if not r:
        return {"report_id": report_id, "public_id": None, "status": "unknown"}
    return {"report_id": report_id, "public_id": r.public_id, "status": "registered" if r.public_id else "processing"}


def _register_voice(upload_path: str, device_id: str, session_id: str, incident: str) -> dict:
    caps = get_config().voice_caps
    dev = device_hash(device_id)
    _caps(dev)
    try:
        wav = to_wav16k(upload_path, max_seconds=caps["max_clip_seconds"])
    except BadAudio:
        raise HTTPException(422, {"code": "bad_audio", "message": "Couldn't play that recording. Try again, or type."}) from None
    seconds, loudness = measure(wav)
    if seconds < caps["min_clip_seconds"] or loudness < 0.003:
        raise HTTPException(422, {"code": "empty_clip", "message": "Didn't hear anything, try again."})
    with open(upload_path, "rb") as f:
        orig_sha, orig_size = storage.store_bytes(f.read(), MAX_UPLOAD)
    wav_sha, _ = storage.store_bytes(wav, 10 * MAX_UPLOAD)
    report = CanonicalReport(schema_version="1", idempotency_key=session_id, channel="voice", incident_hint=incident,
                             reporter=Reporter(device_id=device_id, relation="unknown"),
                             content=Content(audio_ref=storage.uri_for(orig_sha)), source=Source(system="reporter-pwa"))
    with get_engine().begin() as conn:
        res = accept(conn, report, source_ns=f"voice:{dev[:16]}", actor=Actor("reporter", dev[:12], "reporter"))
        if not res.replay:
            conn.execute(text(
                "INSERT INTO evidence (report_id, type, uri, sha256, mime, bytes, added_by, meta)"
                " VALUES (:r, 'audio', :uri, :sha, 'audio/original', :n, 'reporter', CAST(:meta AS jsonb))"),
                {"r": res.report_id, "uri": storage.uri_for(orig_sha), "sha": orig_sha, "n": orig_size,
                 "meta": f'{{"wav_sha256": "{wav_sha}", "seconds": {seconds:.2f}}}'})
    return {"report_id": res.report_id, "replay": res.replay}


@router.post("/voice-turns")
async def voice_turn(audio: UploadFile = File(...), device_id: str = Form(..., min_length=8, max_length=100),
                     session_id: str = Form(..., min_length=8, max_length=100),
                     incident: str = Form("BR", pattern=r"^[A-Z]{2,4}$")) -> dict:
    data = await audio.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Clip too large")
    with tempfile.NamedTemporaryFile(suffix=".upload") as tmp:
        tmp.write(data)
        tmp.flush()
        reg = await run_in_threadpool(_register_voice, tmp.name, device_id, session_id, incident)
    return {**(await _wait_for_case(reg["report_id"])), "reply": REPLY}


class TextTurn(BaseModel):
    device_id: str = Field(min_length=8, max_length=100)
    session_id: str = Field(min_length=8, max_length=100)
    incident: str = Field("BR", pattern=r"^[A-Z]{2,4}$")
    text: str = Field(min_length=2, max_length=2000)


@router.post("/text-turns")
async def text_turn(body: TextTurn) -> dict:
    dev = device_hash(body.device_id)

    def register():
        report = CanonicalReport(schema_version="1", idempotency_key=body.session_id, channel="web_form",
                                 incident_hint=body.incident, reporter=Reporter(device_id=body.device_id),
                                 content=Content(text=body.text), source=Source(system="reporter-pwa"))
        with get_engine().begin() as conn:
            return accept(conn, report, source_ns=f"voice:{dev[:16]}", actor=Actor("reporter", dev[:12], "reporter"),
                          lane="live_voice")
    res = await run_in_threadpool(register)
    return {**(await _wait_for_case(res.report_id)), "reply": REPLY}


@router.get("/turns/{report_id}")
def turn(report_id: int, device_id: str) -> dict:
    """Only the device that sent the report can poll it."""
    with get_engine().connect() as c:
        owner = c.execute(text("SELECT device_hash FROM reports WHERE id = :id"), {"id": report_id}).scalar()
    if owner != device_hash(device_id):
        raise HTTPException(404, "Not found")
    return turn_status(report_id)



class Callback(BaseModel):
    device_id: str = Field(min_length=8, max_length=100)
    phone: str = Field(min_length=6, max_length=40)


@router.post("/cases/{public_id}/callback")
def add_callback(public_id: str, body: Callback) -> dict:
    """After registration only, optional: 'A number we can call back?'. Only the device that reported can add
    it, and only once per report (what someone told us is never overwritten)."""
    from app.core.eventlog import append_event
    from app.core.phones import protect
    p = protect(body.phone)
    if not p["hash"]:
        raise HTTPException(422, "That doesn't look like an Indian mobile number")
    with get_engine().begin() as c:
        r = c.execute(text("SELECT r.id, r.case_id, c.incident_id, c.district_id FROM reports r JOIN cases c ON c.id = r.case_id"
                           " WHERE c.public_id = :p AND r.device_hash = :d ORDER BY r.id DESC LIMIT 1"),
                      {"p": public_id, "d": device_hash(body.device_id)}).one_or_none()
        if r is None:
            raise HTTPException(404, "Not found")
        n = c.execute(text("UPDATE reports SET reporter_phone_enc = :e, reporter_phone_hash = :h, reporter_phone_masked = :m"
                           " WHERE id = :id AND reporter_phone_hash IS NULL"),
                      {"e": p["enc"], "h": p["hash"], "m": p["masked"], "id": r.id}).rowcount
        if n:
            append_event(c, actor=Actor("reporter", device_hash(body.device_id)[:12], "reporter"),
                         action="report.callback_added", entity_type="report", entity_id=r.id, incident_id=r.incident_id,
                         district_id=r.district_id, case_id=r.case_id, data={"phone": p["masked"]})
    return {"ok": True, "saved": bool(n)}


# --- status page (PRD F-L3) -------------------------------------------------------------------------------
# What the public may see about a case: its step and when it last changed. Never names, phone numbers,
# location, priority, escalation state or an ETA. "Help assigned", never "help on the way": we don't know
# the boat is moving. When a team goes quiet the page doesn't change; only "last update" ages.

STEPS = ["registered", "help_assigned", "team_reached", "rescued"]
STEP_OF = {"reported": "registered", "checked": "registered", "assigned": "help_assigned",
           "acknowledged": "help_assigned", "reached": "team_reached", "rescued": "rescued", "closed": "rescued"}
STEP_EVENTS = ("assignment.created", "assignment.reached", "rescue.recorded",
               "rescue.partial", "case.closed", "case.reopened", "case.cancelled")
_lookups: dict[str, list[float]] = {}


def _rate_limit(request) -> None:
    import time
    key = request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")
    per_min = get_config().status_page.get("lookups_per_min_per_ip", 60)
    now = time.monotonic()
    recent = [t for t in _lookups.get(key, []) if now - t < 60]
    if len(recent) >= per_min:
        raise HTTPException(429, "Too many lookups; wait a minute")
    recent.append(now)
    _lookups[key] = recent


def public_status(public_id: str) -> dict | None:
    with get_engine().connect() as c:
        case = c.execute(text("SELECT id, public_id, status, parent_case_id, queue_since AS created_at FROM cases"
                              " WHERE public_id = :p"),
                         {"p": public_id}).one_or_none()
        if case is None:
            return None
        merged_into = None
        if case.status == "merged" and case.parent_case_id:   # P1 #12: the merged-ID redirect
            parent = c.execute(text("SELECT id, public_id, status, queue_since AS created_at FROM cases WHERE id = :i"),
                               {"i": case.parent_case_id}).one()
            merged_into, case = parent.public_id, parent
        others = c.execute(text("SELECT count(*) FROM reports WHERE case_id = :c"), {"c": case.id}).scalar() - 1
        last = c.execute(text("SELECT max(at) FROM events WHERE case_id = :c AND action = ANY(:a)"),
                         {"c": case.id, "a": list(STEP_EVENTS)}).scalar() or case.created_at
    step = "closed" if case.status == "cancelled" else STEP_OF.get(case.status, "registered")
    return {"public_id": public_id, "tracked_as": merged_into, "other_reports": max(others, 0) if merged_into else None,
            "step": step, "steps": STEPS, "last_update_at": last.isoformat()}


@router.get("/cases/{public_id}/status")
def case_status(public_id: str, request: Request, device: str | None = None) -> dict:
    _rate_limit(request)
    st = public_status(public_id)
    if st is None:
        raise HTTPException(404, "No case with that number")
    if device:   # only the device that reported this case may be asked; anyone else sees just the step
        st["check"] = family_question(st["tracked_as"] or public_id, device)
    if get_settings().demo_mode:   # the demo's QR may hand this page the son's synthetic device (never otherwise)
        st["demo"] = True
    return st


# --- the family's optional check (PRD F-S3, T9) ---------------------------------------------------------------
# After "rescued", the device that reported the case sees one question: "Team says 6 people were rescued. Is that
# right? Yes / No · You don't have to answer." Silence never blocks a closure and never counts against anyone.

def _linked(c, case_id: int, device_id: str):
    """(report, on_site) if this device reported this case (or a case folded into it), else None. On site = the
    person in danger themself, by relation or by what they said ("hum chhat par hain")."""
    return c.execute(text(
        "WITH RECURSIVE fam(id) AS (SELECT CAST(:c AS bigint) UNION SELECT k.id FROM cases k JOIN fam ON k.parent_case_id = fam.id)"
        " SELECT r.id, (r.reporter_relation = 'self' OR coalesce((r.extraction->>'reporter_on_site')::boolean, false)) AS on_site"
        " FROM reports r WHERE r.case_id IN (SELECT id FROM fam) AND r.device_hash = :d ORDER BY on_site DESC, r.id LIMIT 1"),
        {"c": case_id, "d": device_hash(device_id)}).one_or_none()


def _rescue(c, case_id: int):
    """The rescue that closed the case, with everyone taken on every trip (4 + 2 → "6 people were rescued")."""
    return c.execute(text("SELECT id, (SELECT sum(x.people_taken) FROM rescues x WHERE x.case_id = :c AND x.corroborates"
                          " IS NULL AND x.outcome IN ('partial', 'rescued')) AS people_taken FROM rescues WHERE case_id = :c"
                          " AND corroborates IS NULL"
                          " AND outcome = 'rescued' ORDER BY id DESC LIMIT 1"), {"c": case_id}).one_or_none()


def family_question(public_id: str, device_id: str) -> dict | None:
    with get_engine().connect() as c:
        case = c.execute(text("SELECT id, status FROM cases WHERE public_id = :p"), {"p": public_id}).one_or_none()
        if case is None or case.status not in ("rescued", "closed"):
            return None
        link, rescue = _linked(c, case.id, device_id), _rescue(c, case.id)
        if link is None or rescue is None:
            return None
        answered = c.execute(text("SELECT answer FROM family_checks WHERE case_id = :c AND device_hash = :d"),
                             {"c": case.id, "d": device_hash(device_id)}).scalar()
    return {"people_taken": rescue.people_taken, "answered": answered}


class Confirm(BaseModel):
    device_id: str = Field(min_length=8, max_length=100)
    answer: str = Field(pattern="^(yes|no)$")


@router.post("/cases/{public_id}/confirm")
def confirm(public_id: str, body: Confirm) -> dict:
    """Yes → "confirmed by family". No from the person who was there → the case reopens at once as P1 with its
    original time. No from a relative far away (who may simply not have heard yet) → "disputed": it can't
    auto-close and becomes an urgent officer task. A device that didn't report this case can't answer."""
    from app.core.eventlog import append_event
    with get_engine().begin() as c:
        case = c.execute(text("SELECT * FROM cases WHERE public_id = :p FOR UPDATE"), {"p": public_id}).one_or_none()
        if case is None:
            raise HTTPException(404, "No case with that number")
        if case.status == "merged" and case.parent_case_id:
            case = c.execute(text("SELECT * FROM cases WHERE id = :i FOR UPDATE"), {"i": case.parent_case_id}).one()
        link = _linked(c, case.id, body.device_id)
        if link is None:
            raise HTTPException(403, "Only the phone or device that reported this case can answer")
        rescue = _rescue(c, case.id)
        if rescue is None or case.status not in ("rescued", "closed"):
            raise HTTPException(409, "Nothing to confirm yet")
        dh = device_hash(body.device_id)
        done = c.execute(text("INSERT INTO family_checks (case_id, rescue_id, device_hash, on_site, answer)"
                              " VALUES (:c, :r, :d, :o, :a) ON CONFLICT (case_id, device_hash) DO NOTHING RETURNING id"),
                         {"c": case.id, "r": rescue.id, "d": dh, "o": link.on_site, "a": body.answer}).scalar()
        if done is None:
            raise HTTPException(409, "You already answered. Thank you.")
        actor = Actor("reporter", dh[:12], "reporter")
        base = dict(entity_type="case", entity_id=case.id, incident_id=case.incident_id, district_id=case.district_id,
                    case_id=case.id)
        if body.answer == "yes":
            c.execute(text("UPDATE cases SET flags = array_append(array_remove(flags, 'family_confirmed'), 'family_confirmed'),"
                           " version = version + 1, updated_at = now() WHERE id = :c"), {"c": case.id})
            append_event(c, actor=actor, action="rescue.confirmed", **base,
                         data={"rescue_id": rescue.id, "on_site": link.on_site, "people_taken": rescue.people_taken})
            return {"recorded": "yes"}
        if link.on_site:   # the person who was there says no: the team may have reached the wrong house
            status = "checked" if case.checked_at else "reported"
            c.execute(text("UPDATE cases SET status = :s, priority = 'P1', p1_rank = coalesce(p1_rank, 4),"
                           " flags = array_append(array_remove(array_remove(flags, 'reopened'), 'family_confirmed'), 'reopened'),"
                           " resolution = NULL, version = version + 1, updated_at = now() WHERE id = :c"),
                           {"s": status, "c": case.id})
            append_event(c, actor=actor, action="case.reopened", **base, reason="the person on site says they were not rescued",
                         data={"rescue_id": rescue.id, "by": "the family (on site)", "status": status, "priority": "P1"})
            return {"recorded": "no", "result": "reopened"}
        c.execute(text("UPDATE cases SET status = CASE WHEN status = 'closed' THEN 'rescued' ELSE status END,"
                       " flags = array_append(array_remove(flags, 'disputed'), 'disputed'), version = version + 1,"
                       " updated_at = now() WHERE id = :c"), {"c": case.id})
        append_event(c, actor=actor, action="rescue.disputed", **base,
                     data={"rescue_id": rescue.id, "on_site": False,
                           "line": "A relative far away says No: it can't close until an officer radios the team"})
        return {"recorded": "no", "result": "disputed"}
