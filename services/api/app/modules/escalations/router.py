"""Escalations (PRD §11.1): GET /v1/escalations?incident=&open=true · POST /v1/escalations/{id}/ack.
Officers of the escalation's district (scoped in SQL); routed to a role, never a named person."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.auth import Scope, require
from app.core.clock import hhmmss
from app.core.eventlog import Actor, append_event
from app.core.listener import require_local
from app.db import get_engine

router = APIRouter(prefix="/v1/escalations", tags=["escalations"], dependencies=[Depends(require_local)])


def _where(scope: Scope) -> tuple[str, dict]:
    if scope.role == "admin":
        return "TRUE", {}
    return ("(e.incident_id = ANY(:scope_incidents) AND e.district_id = ANY(:scope_districts))",
            {"scope_incidents": list(scope.incident_ids), "scope_districts": list(scope.district_ids)})


def _view(r) -> dict:
    d = dict(r._mapping)
    for k in ("opened_at", "acked_at", "resolved_at"):
        d[k] = d[k].isoformat() if d[k] else None
    d["case_ids"] = list(d["case_ids"])
    return d


@router.get("")
def list_escalations(incident: str, open: bool = True, scope: Scope = Depends(require("escalation.ack"))) -> list[dict]:
    where, params = _where(scope)
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT e.*, t.name AS team, u.name AS acked_by_name FROM escalations e JOIN incidents i ON i.id = e.incident_id"
            " LEFT JOIN teams t ON t.id = e.team_id LEFT JOIN users u ON u.id = e.acked_by"
            f" WHERE i.code = :code AND (NOT :open OR e.status <> 'resolved') AND {where} ORDER BY e.level DESC, e.opened_at"),
            {**params, "code": incident, "open": open}).all()
    return [_view(r) for r in rows]


@router.post("/{eid}/ack")
def ack(eid: int, scope: Scope = Depends(require("escalation.ack"))) -> dict:
    """"I'm on it." A second officer acknowledging the same escalation gets a 409 naming who and when (T7)."""
    where, params = _where(scope)
    with get_engine().begin() as conn:
        e = conn.execute(text(f"SELECT e.*, u.name AS acked_by_name FROM escalations e LEFT JOIN users u ON u.id = e.acked_by"
                              f" WHERE e.id = :id AND {where} FOR UPDATE OF e"), {**params, "id": eid}).one_or_none()
        if e is None:
            raise HTTPException(404, "No such escalation")
        if e.status == "resolved":
            raise HTTPException(409, f"Already resolved: {e.resolution}")
        if e.status == "acked":
            raise HTTPException(409, f"Already acknowledged by {e.acked_by_name} at {hhmmss(e.acked_at)}")
        conn.execute(text("UPDATE escalations SET status = 'acked', acked_by = :u, acked_at = now() WHERE id = :id"),
                     {"u": scope.user_id, "id": eid})
        append_event(conn, actor=Actor("user", str(scope.user_id), scope.role), action="escalation.acked",
                     entity_type="escalation", entity_id=eid, incident_id=e.incident_id, district_id=e.district_id,
                     team_id=e.team_id, data={"escalation_id": eid, "by": scope.name})
    return {"escalation_id": eid, "status": "acked"}
