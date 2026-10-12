"""The reporter's endpoints (public listener, no login; PRD F-L2, §11.1).

POST /v1/public/voice-turns   one clip (≤ 30 s) from the reporter PWA → report → case
POST /v1/public/text-turns    the PWA's "type instead" link
GET  /v1/public/turns/{id}    the case id once the pipeline has made it (for this device only)

The reply is the one fixed sentence (REPLY), never generated text. The PWA plays the team's recorded Hindi
clip (apps/web/public/audio/hi/registered.mp3, human task H-05) if it exists, and shows the text either way.

A reporter is identified only by a random device id the PWA keeps in localStorage. It is hashed, treated
like a phone number in duplicate matching, and links the device to its case for the optional
"Is that right?" check. Caps: 5 voice turns a minute per device and 20 a minute in total (per-IP limits
don't work behind the tunnel or venue NAT).
"""

import asyncio
import hashlib
import os
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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

router = APIRouter(prefix="/v1/public", tags=["public"])
MAX_UPLOAD = 2 * 1024 * 1024
REPLY = {"hi": "आपकी रिपोर्ट दर्ज हो गई है। आपको कुछ याद रखने की ज़रूरत नहीं।",
         "latin": "Aapki report darj ho gayi hai. Aapko kuch yaad rakhne ki zaroorat nahi.",
         "en": "Your report is registered. You don't need to remember anything."}


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
