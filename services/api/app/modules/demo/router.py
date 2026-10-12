"""Demo controls (PRD F-C12): local listener only, DEMO_MODE only. Reset, surge and the rest land in later milestones."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.core.auth import Scope, require
from app.core.eventlog import Actor, append_event
from app.core.flags import language_model_enabled, set_flag
from app.core.listener import listener_of, require_demo
from app.db import get_engine
from app.settings import get_settings

router = APIRouter(prefix="/v1/demo", tags=["demo"], dependencies=[Depends(require_demo)])


@router.get("/status")
def demo_status(request: Request) -> dict:
    s = get_settings()
    return {"demo_mode": s.demo_mode, "listener": listener_of(request), "public_url": s.public_url,
            "language_model": "on" if language_model_enabled() else "off"}


class Switch(BaseModel):
    on: bool


@router.post("/language-model")
def language_model(body: Switch, scope: Scope = Depends(require("incident.admin"))) -> dict:
    """F-C14: switch the language model off (or back on). Speech-to-text stays on, so say "language model"."""
    with get_engine().begin() as c:
        set_flag(c, "language_model_enabled", body.on, by=str(scope.user_id))
        append_event(c, actor=Actor("user", str(scope.user_id), scope.role), action="demo.language_model",
                     entity_type="flag", entity_id="language_model_enabled", data={"on": body.on})
    return {"language_model": "on" if body.on else "off"}
