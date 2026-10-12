"""Incidents as data (PRD F-C1, F-C12, §5.3). A fourth incident is created through the API and receives reports
with NO code change: every query is keyed by the incident, and intake finds it by its code.

GET   /v1/incidents          the incidents this user may see, each with its promise bar (local)
POST  /v1/incidents          create one, with its districts (incident.admin)
PATCH /v1/incidents/{id}     its lifecycle: draft → active → standing_down → closed (incident.admin)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.auth import Scope, current_scope, require
from app.core.eventlog import Actor, append_event
from app.core.listener import require_local
from app.db import get_engine
from app.modules.metrics.service import promises

router = APIRouter(prefix="/v1/incidents", tags=["incidents"], dependencies=[Depends(require_local)])
NEXT = {"draft": {"active"}, "active": {"standing_down"}, "standing_down": {"active", "closed"}, "closed": set()}


@router.get("")
def list_incidents(scope: Scope = Depends(current_scope)) -> list[dict]:
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT i.id, i.code, i.name, i.type, i.states, i.status, ST_Y(i.center::geometry) AS lat,"
            " ST_X(i.center::geometry) AS lng, (SELECT array_agg(d.name ORDER BY d.name) FROM districts d"
            " WHERE d.incident_id = i.id) AS districts FROM incidents i"
            " WHERE (:admin OR i.id = ANY(:ids)) ORDER BY i.id"),
            {"admin": scope.role == "admin", "ids": list(scope.incident_ids)}).all()
        out = []
        for r in rows:
            d = dict(r._mapping)
            d["districts"] = list(d["districts"] or [])
            d["promises"] = promises(conn, scope, r.code) if scope.can("totals.view") else None
            out.append(d)
    return out


class District(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    centroid: tuple[float, float]


class NewIncident(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{2,4}$")
    name: str = Field(min_length=3, max_length=200)
    type: str = Field(min_length=3, max_length=50)
    states: list[str] = Field(min_length=1, max_length=10)
    language: str = Field(default="hi", max_length=10)
    center: tuple[float, float]
    districts: list[District] = Field(min_length=1, max_length=50)
    status: str = Field(default="active", pattern="^(draft|active)$")


@router.post("", status_code=201)
def create_incident(body: NewIncident, scope: Scope = Depends(require("incident.admin"))) -> dict:
    actor = Actor("user", str(scope.user_id), scope.role)
    try:
        with get_engine().begin() as conn:
            iid = conn.execute(text(
                "INSERT INTO incidents (code, name, type, states, language, center, status) VALUES (:c, :n, :t, :s, :l,"
                " ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :st) RETURNING id"),
                {"c": body.code, "n": body.name, "t": body.type, "s": body.states, "l": body.language,
                 "lat": body.center[0], "lng": body.center[1], "st": body.status}).scalar_one()
            for d in body.districts:
                conn.execute(text("INSERT INTO districts (incident_id, name, state, centroid) VALUES (:i, :n, :s,"
                                  " ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography)"),
                             {"i": iid, "n": d.name, "s": d.state, "lat": d.centroid[0], "lng": d.centroid[1]})
            append_event(conn, actor=actor, action="incident.created", entity_type="incident", entity_id=iid, incident_id=iid,
                         data={"code": body.code, "name": body.name, "districts": [d.name for d in body.districts]})
    except IntegrityError:
        raise HTTPException(409, f"An incident with code {body.code} already exists") from None
    return {"incident_id": iid, "code": body.code}


class Status(BaseModel):
    status: str = Field(pattern="^(draft|active|standing_down|closed)$")
    reason: str = Field(min_length=3, max_length=300)


@router.patch("/{iid}")
def set_status(iid: int, body: Status, scope: Scope = Depends(require("incident.admin"))) -> dict:
    with get_engine().begin() as conn:
        cur = conn.execute(text("SELECT status FROM incidents WHERE id = :i FOR UPDATE"), {"i": iid}).scalar()
        if cur is None:
            raise HTTPException(404, "No such incident")
        if body.status not in NEXT[cur]:
            raise HTTPException(409, f"An incident that is {cur} can't become {body.status}")
        conn.execute(text("UPDATE incidents SET status = :s, closed_at = CASE WHEN :s = 'closed' THEN now() END WHERE id = :i"),
                     {"s": body.status, "i": iid})
        append_event(conn, actor=Actor("user", str(scope.user_id), scope.role), action="incident.updated",
                     entity_type="incident", entity_id=iid, incident_id=iid, reason=body.reason,
                     data={"from": cur, "to": body.status})
    return {"incident_id": iid, "status": body.status}
