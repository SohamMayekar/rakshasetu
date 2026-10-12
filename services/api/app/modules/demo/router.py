"""Demo controls (PRD F-C12): local listener only, DEMO_MODE only, never through the tunnel; System admin.

    GET  /v1/demo/status              demo mode, listener, public URL, language model on/off, a running surge
    GET  /v1/demo/scenes              the reset points, in demo order (data/scenarios/BR/demo.yaml)
    POST /v1/demo/reset {scene}       seed + replay the scenes before it (app/modules/demo/scenes.py)
    POST /v1/demo/language-model {on} F-C14: STT stays on, so say "language model"
    POST /v1/demo/surge {rate, duration}   app/surge.py in the background (synthetic, pre-structured)
    GET  /v1/demo/clips               the recorded clips (data/scenarios/BR/clips/)
    POST /v1/demo/play-clip {clip}    one clip through the SAME voice pipeline as the reporter page
    GET  /v1/demo/qr?target=reporter|son   an SVG QR code of a PUBLIC_URL page, for a phone to scan
"""

import shutil
import subprocess
import sys
import tempfile
import time
import uuid

import segno
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.config import get_config
from app.core.auth import Scope, require
from app.core.eventlog import Actor, append_event
from app.core.flags import language_model_enabled, set_flag
from app.core.listener import listener_of, require_demo
from app.db import get_engine
from app.modules.demo import scenes
from app.modules.public.router import _register_voice, device_hash  # the reporter page's own path, not a copy
from app.providers.base import api_key
from app.providers.base import mode as provider_mode
from app.settings import get_settings

router = APIRouter(prefix="/v1/demo", tags=["demo"], dependencies=[Depends(require_demo)])
AUDIO = {".ogg", ".webm", ".mp3", ".wav", ".m4a"}
_surge: dict = {}        # the one background surge: {"proc", "until", "rate", "duration"}


def _actor(scope: Scope) -> Actor:
    return Actor("user", str(scope.user_id), scope.role)


def _surge_running() -> dict | None:
    p = _surge.get("proc")
    if p is None or p.poll() is not None:
        return None
    return {"rate": _surge["rate"], "duration": _surge["duration"], "seconds_left": max(0, round(_surge["until"] - time.time()))}


@router.get("/status")
def demo_status(request: Request) -> dict:
    s = get_settings()
    chain = get_config().providers
    keyed = {kind: [n for n in chain[kind] if api_key(n)] for kind in ("stt", "llm")}   # names only, never a key
    return {"demo_mode": s.demo_mode, "listener": listener_of(request), "public_url": s.public_url,
            "language_model": "on" if language_model_enabled() else "off", "provider_mode": provider_mode(),
            "keys": keyed, "surge": _surge_running()}


@router.get("/scenes")
def list_scenes(_: Scope = Depends(require("incident.admin"))) -> list[dict]:
    return scenes.script()["scenes"]


class ResetTo(BaseModel):
    scene: str = Field("son", max_length=20)


@router.post("/reset")
def reset(body: ResetTo, _: Scope = Depends(require("incident.admin"))) -> dict:
    """Wipes the database. Every open screen reloads itself (the event log starts a new chain)."""
    if _surge_running():
        raise HTTPException(409, "A surge is running: wait for it to finish, then reset")
    try:
        return scenes.reset(body.scene)
    except scenes.ScriptError as e:
        raise HTTPException(409, f"Reset stopped: {e}") from None


class Switch(BaseModel):
    on: bool


@router.post("/language-model")
def language_model(body: Switch, scope: Scope = Depends(require("incident.admin"))) -> dict:
    """F-C14: switch the language model off (or back on). Speech-to-text stays on, so say "language model"."""
    with get_engine().begin() as c:
        set_flag(c, "language_model_enabled", body.on, by=str(scope.user_id))
        append_event(c, actor=_actor(scope), action="demo.language_model",
                     entity_type="flag", entity_id="language_model_enabled", data={"on": body.on})
    return {"language_model": "on" if body.on else "off"}


class Surge(BaseModel):
    rate: float = Field(50, gt=0, le=200)
    duration: float = Field(60, gt=0, le=300)


@router.post("/surge")
def start_surge(body: Surge, scope: Scope = Depends(require("incident.admin"))) -> dict:
    """The same generator as `make surge`, in the background. Synthetic, pre-structured: no language model."""
    if running := _surge_running():
        raise HTTPException(409, f"A surge is already running ({running['seconds_left']} s left)")
    proc = subprocess.Popen([sys.executable, "-m", "app.surge", "--rate", str(body.rate), "--duration", str(body.duration)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    _surge.update(proc=proc, until=time.time() + body.duration, rate=body.rate, duration=body.duration)
    with get_engine().begin() as c:
        append_event(c, actor=_actor(scope), action="demo.surge_started", entity_type="demo", entity_id="surge",
                     data={"rate": body.rate, "duration": body.duration, "synthetic": True})
    return {"started": True, **_surge_running()}


@router.get("/clips")
def clips(_: Scope = Depends(require("incident.admin"))) -> list[dict]:
    folder = scenes.pack() / "clips"
    return [{"clip": f"clips/{p.name}", "synthetic": ".synthetic." in p.name, "bytes": p.stat().st_size}
            for p in sorted(folder.iterdir()) if p.suffix in AUDIO]


class Play(BaseModel):
    clip: str = Field(pattern=r"^clips/[A-Za-z0-9._-]+$")
    device_id: str | None = Field(default=None, min_length=8, max_length=100)
    incident: str = Field("BR", pattern=r"^[A-Z]{2,4}$")


@router.post("/play-clip")
def play_clip(body: Play, scope: Scope = Depends(require("incident.admin"))) -> dict:
    """PRD §16.4: a stored clip through the same live pipeline as a reporter's voice (say so on stage). It comes
    from the son's phone in the demo script unless another device is named."""
    path = (scenes.pack() / body.clip).resolve()
    if path.parent != (scenes.pack() / "clips").resolve() or path.suffix not in AUDIO or not path.is_file():
        raise HTTPException(404, "No such clip")
    device = body.device_id or scenes.script()["son"]["device_id"]
    with tempfile.NamedTemporaryFile(suffix=path.suffix) as tmp:
        shutil.copyfile(path, tmp.name)
        reg = _register_voice(tmp.name, device, f"clip-{uuid.uuid4()}", body.incident)
    with get_engine().begin() as c:
        append_event(c, actor=_actor(scope), action="demo.clip_played", entity_type="report", entity_id=reg["report_id"],
                     data={"report_id": reg["report_id"], "clip": body.clip, "synthetic_voice": ".synthetic." in path.name})
    return reg


@router.get("/qr")
def qr(target: str, _: Scope = Depends(require("incident.admin"))) -> Response:
    """A QR code for a phone: the reporter page, or the son's status page AS the son's phone (after a reset the
    family's question is asked only of that device). Only PUBLIC_URL pages: a phone can't reach localhost."""
    base = get_settings().public_url.rstrip("/")
    if not base:
        raise HTTPException(409, "Set PUBLIC_URL in .env to the tunnel's address first")
    if target == "reporter":
        url = f"{base}/r"
    elif target == "son":
        s = scenes.script()["son"]
        with get_engine().connect() as c:
            pid = c.execute(text("SELECT c.public_id FROM reports r JOIN cases c ON c.id = r.case_id"
                                 " WHERE r.device_hash = :d ORDER BY r.id DESC LIMIT 1"),
                            {"d": device_hash(s["device_id"])}).scalar()
        if not pid:
            raise HTTPException(404, "The son's phone hasn't reported yet (reset to a later scene, or play the clip)")
        url = f"{base}/s/{pid}#device={s['device_id']}"
    else:
        raise HTTPException(422, "target is reporter or son")
    svg = segno.make(url, error="m").svg_inline(scale=5, border=2)
    return Response(svg, media_type="image/svg+xml", headers={"X-QR-URL": url, "Cache-Control": "no-store"})

