"""Teams (PRD §11.1). POST /v1/teams/me/heartbeat: "last seen" while the responder app is open.
The heartbeat is DISPLAY ONLY: it never extends a check-in deadline (PRD F-S1; contact.heartbeat_extends_deadline
is fixed to false in the config schema). No event is written for it: it isn't a decision or a state change."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.auth import Scope, current_scope
from app.db import get_engine

router = APIRouter(prefix="/v1/teams", tags=["teams"])


@router.post("/me/heartbeat")
def heartbeat(scope: Scope = Depends(current_scope)) -> dict:
    if scope.role != "team_lead" or not scope.team_id:
        raise HTTPException(403, "Only a team lead's app sends a heartbeat")
    with get_engine().begin() as conn:
        seen = conn.execute(text("UPDATE teams SET last_seen_at = now() WHERE id = :t RETURNING last_seen_at"),
                            {"t": scope.team_id}).scalar()
    return {"last_seen_at": seen.isoformat(), "extends_deadline": False}
