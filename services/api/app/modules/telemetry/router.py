"""Telemetry (the brief's "IoT supplies live telemetry"), kept as small as the rest of the platform.

POST /v1/ingest/telemetry   a partner's signed reading (same HMAC, replay window and rate cap as every partner call)
GET  /v1/telemetry          the desk's sensors: latest value, state, a short trend, scoped like cases (local)

A sensor is created by its first reading. State is `ok`, `warn` or `danger` against two thresholds the partner
sends. Only a CHANGE of state is written to the audit chain (a sensor reading every second must not bury the
timeline), and it is stamped with the sensor's incident so it reaches the right desks live. A reading never
changes a case's priority: it is context for a person, shown beside the cases it is near.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text

from app.channels import partner as signing
from app.core.auth import Scope, require
from app.core.eventlog import Actor, append_event
from app.core.listener import require_local
from app.db import get_engine

router = APIRouter(tags=["telemetry"])

Kind = Literal["water_level", "rainfall", "wind", "temperature", "other"]


class SensorSpec(BaseModel):
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=2, max_length=120)
    kind: Kind = "other"
    unit: str = Field(default="", max_length=16)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    warn_at: float | None = None
    danger_at: float | None = None
    district: str | None = Field(default=None, max_length=100)


class Reading(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)
    incident: str = Field(pattern=r"^[A-Z]{2,4}$")
    sensor: SensorSpec
    value: float
    read_at: datetime | None = None
    simulated: bool = False


def _state(value: float, warn_at: float | None, danger_at: float | None) -> str:
    if danger_at is not None and value >= danger_at:
        return "danger"
    if warn_at is not None and value >= warn_at:
        return "warn"
    return "ok"


def _store(partner_id: str, body: Reading) -> dict:
    read_at = body.read_at or datetime.now(UTC)
    if read_at.tzinfo is None:
        read_at = read_at.replace(tzinfo=UTC)
    if read_at > datetime.now(UTC) + timedelta(minutes=5):
        read_at = datetime.now(UTC)   # a clock running ahead is a label problem, not a reason to refuse a reading
    s = body.sensor
    actor = Actor("partner", partner_id, "partner")
    with get_engine().begin() as conn:
        inc = conn.execute(text("SELECT id, status FROM incidents WHERE code = :c"), {"c": body.incident}).one_or_none()
        if inc is None:
            raise HTTPException(404, "No such incident")
        district = None
        if s.district:
            district = conn.execute(text("SELECT id FROM districts WHERE incident_id = :i AND lower(name) = lower(:n)"),
                                    {"i": inc.id, "n": s.district}).scalar()
        row = conn.execute(text("SELECT id, state, warn_at, danger_at FROM sensors WHERE incident_id = :i AND code = :c"
                                " FOR UPDATE"), {"i": inc.id, "c": s.code}).one_or_none()
        if row is None:
            sid = conn.execute(text(
                "INSERT INTO sensors (incident_id, district_id, code, name, kind, unit, geom, warn_at, danger_at, partner, simulated)"
                " VALUES (:i, :d, :c, :n, :k, :u, CASE WHEN CAST(:lat AS float) IS NULL OR CAST(:lng AS float) IS NULL THEN NULL"
                "   ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS float), CAST(:lat AS float)), 4326)::geography END,"
                " :w, :dg, :p, :sim) RETURNING id"),
                {"i": inc.id, "d": district, "c": s.code, "n": s.name, "k": s.kind, "u": s.unit, "lat": s.lat, "lng": s.lng,
                 "w": s.warn_at, "dg": s.danger_at, "p": partner_id, "sim": body.simulated}).scalar_one()
            append_event(conn, actor=actor, action="sensor.registered", entity_type="sensor", entity_id=sid,
                         incident_id=inc.id, district_id=district,
                         data={"code": s.code, "name": s.name, "kind": s.kind, "simulated": body.simulated})
            old_state, warn_at, danger_at = "unknown", s.warn_at, s.danger_at
        else:
            sid, old_state = row.id, row.state
            # the partner may tune its thresholds; what it sent last is what applies
            warn_at = s.warn_at if s.warn_at is not None else row.warn_at
            danger_at = s.danger_at if s.danger_at is not None else row.danger_at
        stored = conn.execute(text(
            "INSERT INTO sensor_readings (sensor_id, value, read_at, idempotency_key) VALUES (:s, :v, :t, :k)"
            " ON CONFLICT (sensor_id, idempotency_key) DO NOTHING RETURNING id"),
            {"s": sid, "v": body.value, "t": read_at, "k": body.idempotency_key}).scalar()
        if stored is None:
            return {"sensor": s.code, "replay": True}
        new_state = _state(body.value, warn_at, danger_at)
        conn.execute(text(
            "UPDATE sensors SET last_value = :v, last_read_at = :t, state = :st, warn_at = :w, danger_at = :dg WHERE id = :id"
            " AND (last_read_at IS NULL OR last_read_at <= :t)"),
            {"v": body.value, "t": read_at, "st": new_state, "w": warn_at, "dg": danger_at, "id": sid})
        if new_state != old_state and not (old_state == "unknown" and new_state == "ok"):
            append_event(conn, actor=actor, action="sensor.state_changed", entity_type="sensor", entity_id=sid,
                         incident_id=inc.id, district_id=district,
                         data={"code": s.code, "name": s.name, "from": old_state, "to": new_state, "value": body.value,
                               "unit": s.unit, "simulated": body.simulated})
    return {"sensor": s.code, "state": new_state, "replay": False}


@router.post("/v1/ingest/telemetry", status_code=202)
async def ingest_telemetry(request: Request, response: Response) -> dict:
    raw = await request.body()
    # A partner allowed "telemetry.submit" sends readings under that scope; one that may only send reports may too.
    from app.config import get_bundle
    claimed = next((x for x in get_bundle().partners if x.id == request.headers.get("x-rakshasetu-partner", "")), None)
    needed = "telemetry.submit" if claimed and "telemetry.submit" in claimed.scopes else "report.submit"
    p = signing.verify_partner(request.headers, raw, needed)
    try:
        body = Reading.model_validate_json(raw)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from None
    if request.headers.get("idempotency-key") != body.idempotency_key:
        raise HTTPException(400, "Idempotency-Key header must equal the body's idempotency_key")
    if p.incidents and body.incident not in p.incidents:
        raise HTTPException(403, f"Partner {p.id} may not report into {body.incident}")
    out = await run_in_threadpool(_store, p.id, body)
    if out["replay"]:
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"
    return out


@router.get("/v1/telemetry", dependencies=[Depends(require_local)])
def list_sensors(incident: str | None = None, scope: Scope = Depends(require("totals.view"))) -> list[dict]:
    """Every sensor this person may see, worst state first, with its last 24 readings oldest → newest."""
    where = "(:admin OR (s.incident_id = ANY(:inc) AND (s.district_id IS NULL OR s.district_id = ANY(:dist))))"
    params = {"admin": scope.role == "admin", "inc": list(scope.incident_ids), "dist": list(scope.district_ids),
              "code": incident}
    with get_engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT s.id, s.code, s.name, s.kind, s.unit, s.state, s.last_value, s.last_read_at, s.warn_at, s.danger_at,"
            " s.simulated, s.partner, i.code AS incident, i.name AS incident_name, d.name AS district,"
            " ST_Y(s.geom::geometry) AS lat, ST_X(s.geom::geometry) AS lng,"
            " (SELECT coalesce(array_agg(r.value ORDER BY r.read_at), '{}') FROM (SELECT value, read_at FROM sensor_readings"
            "   WHERE sensor_id = s.id ORDER BY read_at DESC LIMIT 24) r) AS trend"
            " FROM sensors s JOIN incidents i ON i.id = s.incident_id LEFT JOIN districts d ON d.id = s.district_id"
            f" WHERE (CAST(:code AS text) IS NULL OR i.code = :code) AND {where}"), params).all()
    order = {"danger": 0, "warn": 1, "ok": 2, "unknown": 3}
    out = []
    for r in rows:
        d = dict(r._mapping)
        d["last_read_at"] = d["last_read_at"].isoformat() if d["last_read_at"] else None
        d["trend"] = list(d["trend"] or [])
        out.append(d)
    out.sort(key=lambda d: (order[d["state"]], d["incident"], d["name"]))
    return out
