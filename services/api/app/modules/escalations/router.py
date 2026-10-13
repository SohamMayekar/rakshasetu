"""Escalations (PRD §11.1), for officers of the escalation's district (scoped in SQL); routed to a role, never
a named person. The officer then does one of two things: Extend (heard on radio) or Reassign. Nothing here is
automatic. Two officers acting on the same escalation: the second gets a 409 naming who acted and when (T7).

GET  /v1/escalations?incident=&open=true
POST /v1/escalations/{id}/ack
POST /v1/escalations/{id}/extend     {channel, new_eta?}     = the team-level radio log
POST /v1/escalations/{id}/reassign   {case, team_id}         the old team owes a stand-down until its next contact
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.auth import Scope, require
from app.core.clock import hhmmss
from app.core.eventlog import Actor, append_event
from app.core.listener import require_local
from app.db import get_engine
from app.modules.assignments.service import _team_status, create
from app.modules.cases.service import Conflict, NotAllowed, lock_case
from app.modules.teams.service import heard_from

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
def list_escalations(incident: str | None = None, open: bool = True, scope: Scope = Depends(require("escalation.ack"))) -> list[dict]:
    where, params = _where(scope)
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT e.*, t.name AS team, u.name AS acked_by_name FROM escalations e JOIN incidents i ON i.id = e.incident_id"
            " LEFT JOIN teams t ON t.id = e.team_id LEFT JOIN users u ON u.id = e.acked_by"
            f" WHERE (CAST(:code AS text) IS NULL OR i.code = :code) AND (NOT :open OR e.status <> 'resolved') AND {where} ORDER BY e.level DESC, e.opened_at"),
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


def _open_escalation(conn, scope: Scope, eid: int):
    where, params = _where(scope)
    e = conn.execute(text(f"SELECT e.* FROM escalations e WHERE e.id = :id AND {where} FOR UPDATE OF e"),
                     {**params, "id": eid}).one_or_none()
    if e is None:
        raise HTTPException(404, "No such escalation")
    if e.status == "resolved":
        raise HTTPException(409, f"Already resolved: {e.resolution} at {hhmmss(e.resolved_at)}")
    if e.kind != "team_overdue":
        raise HTTPException(409, "Only a team's escalation can be extended or reassigned")
    return e


class Extend(BaseModel):
    channel: str
    new_eta: int | None = None


@router.post("/{eid}/extend")
def extend(eid: int, body: Extend, scope: Scope = Depends(require("team.radio_contact"))) -> dict:
    with get_engine().begin() as conn:
        e = _open_escalation(conn, scope, eid)
        team = conn.execute(text("SELECT * FROM teams WHERE id = :t FOR UPDATE"), {"t": e.team_id}).one()
        try:
            return heard_from(conn, team=team, actor=Actor("user", str(scope.user_id), scope.role), by=scope.name,
                              channel=body.channel, new_eta=body.new_eta)
        except NotAllowed as x:
            raise HTTPException(409, x.message) from None


class Reassign(BaseModel):
    case: str = Field(min_length=1, max_length=20)
    team_id: int


@router.post("/{eid}/reassign")
def reassign(eid: int, body: Reassign, scope: Scope = Depends(require("assignment.create"))) -> dict:
    actor = Actor("user", str(scope.user_id), scope.role)
    with get_engine().begin() as conn:
        e = _open_escalation(conn, scope, eid)
        case = lock_case(conn, scope, body.case)
        if case is None or case.id not in e.case_ids:
            raise HTTPException(404, "That case isn't in this escalation")
        old = conn.execute(text("SELECT a.*, t.name AS team FROM assignments a JOIN teams t ON t.id = a.team_id"
                                " WHERE a.case_id = :c AND a.state IN ('open', 'overdue') FOR UPDATE OF a"),
                           {"c": case.id}).one_or_none()
        if old is None or old.team_id != e.team_id:
            raise HTTPException(409, "Someone already moved this case on")
        new_team = conn.execute(text("SELECT * FROM teams WHERE id = :t FOR UPDATE"), {"t": body.team_id}).one_or_none()
        if new_team is None or new_team.id == old.team_id:
            raise HTTPException(409, "Pick another team")
        if new_team.status == "overdue":
            raise HTTPException(409, f"{new_team.name} is overdue too: radio them first")
        conn.execute(text("UPDATE assignments SET state = 'reassigned', ended_at = now(), end_reason = :r,"
                          " standdown_acked_at = NULL WHERE id = :a"),
                     {"r": f"reassigned to {new_team.name} by {scope.name}", "a": old.id})
        try:
            made = create(conn, case=case, team=new_team, actor=actor)
        except (Conflict, NotAllowed) as x:
            raise HTTPException(409, x.message) from None
        _team_status(conn, old.team_id)
        left = [c for c in e.case_ids if c != case.id]
        conn.execute(text("UPDATE escalations SET case_ids = :c, status = CASE WHEN cardinality(CAST(:c AS bigint[])) = 0"
                          " THEN 'resolved' ELSE status END, resolved_at = CASE WHEN cardinality(CAST(:c AS bigint[])) = 0"
                          " THEN now() END, resolution = CASE WHEN cardinality(CAST(:c AS bigint[])) = 0 THEN :why END"
                          " WHERE id = :e"), {"c": left, "e": eid, "why": f"reassigned by {scope.name}"})
        append_event(conn, actor=actor, action="assignment.reassigned", entity_type="assignment", entity_id=old.id,
                     incident_id=case.incident_id, district_id=case.district_id, case_id=case.id, team_id=old.team_id,
                     data={"from_team": old.team, "to_team": new_team.name, "new_assignment_id": made["assignment_id"],
                           "escalation_id": eid, "standdown_owed": True})
        return {**made, "from_team": old.team, "escalation_open": bool(left)}
