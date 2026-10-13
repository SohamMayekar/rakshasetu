"""GET /v1/queue[?incident=] — "Needs you now" for the signed-in desk user (local listener, scoped in SQL).
Without `incident` it is the national queue: every incident this person may see."""

from fastapi import APIRouter, Depends

from app.core.auth import Scope, require
from app.core.listener import require_local
from app.db import get_engine
from app.modules.queue.service import queue

router = APIRouter(tags=["queue"], dependencies=[Depends(require_local)])


@router.get("/v1/queue")
def needs_you_now(incident: str | None = None, scope: Scope = Depends(require("queue.view"))) -> dict:
    with get_engine().connect() as conn:
        return queue(conn, scope, incident)
