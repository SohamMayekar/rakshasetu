"""Teams (PRD §11.1).

POST /v1/teams/{id}/contact   an officer's radio log: team-level, refreshes every live assignment (local)
GET  /v1/teams?incident=      the district's teams with status, load, last contact and last seen (local)
GET  /v1/teams/catalog        what a team can be and do: agencies and capabilities (the form's lists)
POST /v1/teams                add a team to an incident, with its capabilities and, if it has the app, its lead's sign-in
PATCH /v1/teams/{id}          change a team's capabilities, agency, capacity or radio channel (admin)
POST /v1/teams/me/heartbeat   "last seen" while the responder app is open.
The heartbeat is DISPLAY ONLY: it never extends a check-in deadline (PRD F-S1; contact.heartbeat_extends_deadline
is fixed to false in the config schema). No event is written for it: it isn't a decision or a state change."""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.capabilities import AGENCIES, CATALOG, KEYS
from app.core.auth import Scope, current_scope, require
from app.core.eventlog import Actor, append_event
from app.core.listener import require_local
from app.core.passwords import hash_password
from app.db import get_engine
from app.modules.cases.repo import head_seq
from app.modules.cases.service import NotAllowed
from app.modules.teams.service import heard_from
from app.settings import get_settings

router = APIRouter(prefix="/v1/teams", tags=["teams"])


@router.get("/catalog", dependencies=[Depends(require_local)])
def catalog(_: Scope = Depends(current_scope)) -> dict:
    """The lists the "add a team" form offers. A team may carry a capability not listed here; it is kept as written."""
    return {"capabilities": CATALOG, "agencies": AGENCIES}


class Lead(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-z0-9._-]+$")
    name: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=100)


class NewTeam(BaseModel):
    incident: str = Field(pattern=r"^[A-Z]{2,4}$")
    district: str = Field(min_length=2, max_length=100)
    name: str = Field(min_length=2, max_length=120)
    agency: str = Field(min_length=2, max_length=60)
    capabilities: list[str] = Field(default_factory=list, max_length=30)
    has_app: bool = True
    radio_channel: str | None = Field(default=None, max_length=30)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    max_active: int = Field(default=2, ge=1, le=20)
    lead: Lead | None = None


def _caps(raw: list[str]) -> list[str]:
    out: list[str] = []
    for c in raw:
        key = c.strip().lower().replace(" ", "_")
        if key and key not in out:
            out.append(key)
    return out


@router.post("", status_code=201, dependencies=[Depends(require_local)])
def create_team(body: NewTeam, scope: Scope = Depends(require("incident.admin"))) -> dict:
    caps = _caps(body.capabilities)
    unknown = [c for c in caps if c not in KEYS]
    if body.lead and not body.has_app:
        raise HTTPException(422, "A radio-only team has no app, so it has no sign-in")
    if body.lead and not body.lead.password and not get_settings().demo_mode:
        raise HTTPException(422, "Give the team lead a password (8 characters or more)")
    actor = Actor("user", str(scope.user_id), scope.role)
    with get_engine().begin() as conn:
        inc = conn.execute(text("SELECT id, status FROM incidents WHERE code = :c"), {"c": body.incident}).one_or_none()
        if inc is None:
            raise HTTPException(404, "No such incident")
        if inc.status == "closed":
            raise HTTPException(409, "This incident is closed")
        dist = conn.execute(text("SELECT id FROM districts WHERE incident_id = :i AND lower(name) = lower(:n)"),
                            {"i": inc.id, "n": body.district.strip()}).scalar()
        if dist is None:
            raise HTTPException(404, f"No district called {body.district} in {body.incident}")
        if conn.execute(text("SELECT 1 FROM teams WHERE incident_id = :i AND lower(name) = lower(:n)"),
                        {"i": inc.id, "n": body.name.strip()}).scalar():
            raise HTTPException(409, "A team with that name already exists in this incident")
        if body.lead and conn.execute(text("SELECT 1 FROM users WHERE username = :u"), {"u": body.lead.username}).scalar():
            raise HTTPException(409, "That username is taken")
        geom = "ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography" if body.lat is not None and body.lng is not None else "NULL"
        tid = conn.execute(text(
            "INSERT INTO teams (incident_id, district_id, name, agency, capabilities, has_app, radio_channel, base_geom,"
            f" last_geom, last_geom_at, max_active) VALUES (:i, :d, :n, :a, :c, :app, :r, {geom}, {geom},"
            f" CASE WHEN {geom} IS NULL THEN NULL ELSE now() END, :m) RETURNING id"),
            {"i": inc.id, "d": dist, "n": body.name.strip(), "a": body.agency.strip(), "c": caps, "app": body.has_app,
             "r": body.radio_channel, "lat": body.lat, "lng": body.lng, "m": body.max_active}).scalar_one()
        append_event(conn, actor=actor, action="team.created", entity_type="team", entity_id=tid, incident_id=inc.id,
                     district_id=dist, team_id=tid,
                     data={"name": body.name.strip(), "agency": body.agency.strip(), "capabilities": caps, "has_app": body.has_app})
        lead_name = None
        if body.lead:
            from app.seed import DEMO_PASSWORD  # the demo password, only ever used when DEMO_MODE is on
            pw = hash_password(body.lead.password or DEMO_PASSWORD)
            lead_name = body.lead.name or f"Lead, {body.name.strip()}"
            uid = conn.execute(text(
                "INSERT INTO users (username, name, role, incident_ids, district_ids, team_id, password_hash)"
                " VALUES (:u, :n, 'team_lead', :inc, :dist, :t, :pw) RETURNING id"),
                {"u": body.lead.username, "n": lead_name, "inc": [inc.id], "dist": [dist], "t": tid, "pw": pw}).scalar_one()
            append_event(conn, actor=actor, action="user.created", entity_type="user", entity_id=uid, team_id=tid,
                         data={"username": body.lead.username, "role": "team_lead"})
    return {"team_id": tid, "unknown_capabilities": unknown, "lead": body.lead.username if body.lead else None}


class TeamEdit(BaseModel):
    capabilities: list[str] | None = Field(default=None, max_length=30)
    agency: str | None = Field(default=None, min_length=2, max_length=60)
    max_active: int | None = Field(default=None, ge=1, le=20)
    radio_channel: str | None = Field(default=None, max_length=30)
    reason: str = Field(min_length=3, max_length=300)


@router.patch("/{team_id}", dependencies=[Depends(require_local)])
def edit_team(team_id: int, body: TeamEdit, scope: Scope = Depends(require("incident.admin"))) -> dict:
    sets, params, changed = [], {"t": team_id}, {}
    if body.capabilities is not None:
        params["c"] = _caps(body.capabilities)
        sets.append("capabilities = :c")
        changed["capabilities"] = params["c"]
    if body.agency is not None:
        params["a"] = body.agency.strip()
        sets.append("agency = :a")
        changed["agency"] = params["a"]
    if body.max_active is not None:
        params["m"] = body.max_active
        sets.append("max_active = :m")
        changed["max_active"] = body.max_active
    if body.radio_channel is not None:
        params["r"] = body.radio_channel
        sets.append("radio_channel = :r")
        changed["radio_channel"] = body.radio_channel
    if not sets:
        raise HTTPException(422, "Nothing to change")
    with get_engine().begin() as conn:
        t = conn.execute(text(f"UPDATE teams SET {', '.join(sets)} WHERE id = :t RETURNING incident_id, district_id"), params).one_or_none()
        if t is None:
            raise HTTPException(404, "No such team")
        append_event(conn, actor=Actor("user", str(scope.user_id), scope.role), action="team.updated", entity_type="team",
                     entity_id=team_id, incident_id=t.incident_id, district_id=t.district_id, team_id=team_id,
                     data=changed, reason=body.reason)
    return {"team_id": team_id, **changed}


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
def list_teams(incident: str | None = None, scope: Scope = Depends(require("queue.view"))) -> list[dict]:
    params = {"code": incident, "inc": list(scope.incident_ids), "dist": list(scope.district_ids)}
    where = "TRUE" if scope.role == "admin" else "t.incident_id = ANY(:inc) AND t.district_id = ANY(:dist)"
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT t.id, t.name, t.agency, t.capabilities, t.has_app, t.radio_channel, t.status, t.status_reason,"
            " t.max_active, t.last_contact_at, t.last_seen_at, d.name AS district, i.code AS incident,"
            " (SELECT count(*) FROM assignments a WHERE a.team_id = t.id AND a.state IN ('open', 'overdue')) AS active,"
            " (SELECT count(*) FROM assignments a WHERE a.team_id = t.id AND a.state = 'reassigned'"
            "    AND a.standdown_acked_at IS NULL) AS standdowns_owed"
            " FROM teams t JOIN incidents i ON i.id = t.incident_id JOIN districts d ON d.id = t.district_id"
            f" WHERE (CAST(:code AS text) IS NULL OR i.code = :code) AND {where} ORDER BY i.code, t.name"), params).all()
    out = []
    for r in rows:
        d = dict(r._mapping)
        for k in ("last_contact_at", "last_seen_at"):
            d[k] = d[k].isoformat() if d[k] else None
        out.append(d)
    return out


@router.get("/me/cases")
def my_cases(response: Response, scope: Scope = Depends(current_scope)) -> dict:
    """The responder app's "My cases": the team's live assignments with what the boat needs on one screen,
    including the straight-line distance from the team's last known position. `X-Event-Seq` (read before the
    list) is where the app's live updates start, so it misses nothing and replays nothing."""
    if scope.role != "team_lead" or not scope.team_id:
        raise HTTPException(403, "For a team lead's app")
    with get_engine().connect() as conn:
        response.headers["X-Event-Seq"] = str(head_seq(conn))
        team = conn.execute(text("SELECT id, name, has_app, radio_channel, last_contact_at, last_seen_at, incident_id,"
                                 " (SELECT code FROM incidents WHERE id = teams.incident_id) AS incident"
                                 " FROM teams WHERE id = :t"), {"t": scope.team_id}).one()
        rows = conn.execute(text(
            "SELECT c.id, c.public_id, c.priority, c.priority_reasons, c.summary, c.people_count, c.people_count_kind,"
            " c.needs, c.vulnerable, c.hazards, c.location_text, c.location_method, c.location_confidence, c.radius_m,"
            " ST_Y(c.geom::geometry) AS lat, ST_X(c.geom::geometry) AS lng, c.status, c.version,"
            " a.id AS assignment_id, a.phase, a.state, a.eta_minutes, a.next_contact_due, a.demo_clock, a.created_at,"
            " round((ST_Distance(c.geom, coalesce(t.last_geom, t.base_geom)) / 1000)::numeric, 1) AS distance_km"
            " FROM assignments a JOIN cases c ON c.id = a.case_id JOIN teams t ON t.id = a.team_id"
            " WHERE a.team_id = :t AND a.state IN ('open', 'overdue') ORDER BY a.created_at"), {"t": scope.team_id}).all()
    out = []
    for r in rows:
        d = dict(r._mapping)
        d["next_contact_due"] = d["next_contact_due"].isoformat()
        d["created_at"] = d["created_at"].isoformat()
        d["distance_km"] = float(d["distance_km"]) if d["distance_km"] is not None else None
        out.append(d)
    t = dict(team._mapping)
    for k in ("last_contact_at", "last_seen_at"):
        t[k] = t[k].isoformat() if t[k] else None
    return {"team": t, "cases": out}
