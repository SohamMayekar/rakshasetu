"""Teams (PRD §11.1).

POST /v1/teams/{id}/contact   an officer's radio log: team-level, refreshes every live assignment (local)
GET  /v1/teams?incident=      the district's teams with status, load, last contact and last seen (local)
POST /v1/teams/me/heartbeat   "last seen" while the responder app is open.
The heartbeat is DISPLAY ONLY: it never extends a check-in deadline (PRD F-S1; contact.heartbeat_extends_deadline
is fixed to false in the config schema). No event is written for it: it isn't a decision or a state change."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.auth import Scope, current_scope, require
from app.core.eventlog import Actor
from app.core.listener import require_local
from app.db import get_engine
from app.modules.cases.service import NotAllowed
from app.modules.teams.service import heard_from

router = APIRouter(prefix="/v1/teams", tags=["teams"])


@router.post("/me/heartbeat")
def heartbeat(scope: Scope = Depends(current_scope)) -> dict:
    if scope.role != "team_lead" or not scope.team_id:
        raise HTTPException(403, "Only a team lead's app sends a heartbeat")
    with get_engine().begin() as conn:
        seen = conn.execute(text("UPDATE teams SET last_seen_at = now() WHERE id = :t RETURNING last_seen_at"),
                            {"t": scope.team_id}).scalar()
    return {"last_seen_at": seen.isoformat(), "extends_deadline": False}


class Contact(BaseModel):
    kind: str = Field(default="radio", pattern="^radio$")
    channel: str
    new_eta: int | None = None
    note: str | None = Field(default=None, max_length=300)


@router.post("/{team_id}/contact", dependencies=[Depends(require_local)])
def contact(team_id: int, body: Contact, scope: Scope = Depends(require("team.radio_contact"))) -> dict:
    with get_engine().begin() as conn:
        team = conn.execute(text("SELECT * FROM teams WHERE id = :t FOR UPDATE"), {"t": team_id}).one_or_none()
        if team is None or (scope.role != "admin" and (team.incident_id not in scope.incident_ids
                                                       or team.district_id not in scope.district_ids)):
            raise HTTPException(404, "No such team")
        try:
            return heard_from(conn, team=team, actor=Actor("user", str(scope.user_id), scope.role), by=scope.name,
                              channel=body.channel, new_eta=body.new_eta, note=body.note)
        except NotAllowed as e:
            raise HTTPException(409, e.message) from None


@router.get("", dependencies=[Depends(require_local)])
def list_teams(incident: str, scope: Scope = Depends(require("queue.view"))) -> list[dict]:
    params = {"code": incident, "inc": list(scope.incident_ids), "dist": list(scope.district_ids)}
    where = "TRUE" if scope.role == "admin" else "t.incident_id = ANY(:inc) AND t.district_id = ANY(:dist)"
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT t.id, t.name, t.agency, t.capabilities, t.has_app, t.radio_channel, t.status, t.status_reason,"
            " t.max_active, t.last_contact_at, t.last_seen_at, d.name AS district,"
            " (SELECT count(*) FROM assignments a WHERE a.team_id = t.id AND a.state IN ('open', 'overdue')) AS active,"
            " (SELECT count(*) FROM assignments a WHERE a.team_id = t.id AND a.state = 'reassigned'"
            "    AND a.standdown_acked_at IS NULL) AS standdowns_owed"
            " FROM teams t JOIN incidents i ON i.id = t.incident_id JOIN districts d ON d.id = t.district_id"
            f" WHERE i.code = :code AND {where} ORDER BY t.name"), params).all()
    out = []
    for r in rows:
        d = dict(r._mapping)
        for k in ("last_contact_at", "last_seen_at"):
            d[k] = d[k].isoformat() if d[k] else None
        out.append(d)
    return out
