"""Case writes. Every change ends with append_event() (rule R1)."""

import json

from sqlalchemy import Connection, text

from app.config import get_config
from app.core.clock import hhmmss
from app.core.eventlog import Actor, append_event


def next_public_id(conn: Connection, incident_id: int) -> str:
    r = conn.execute(text("UPDATE incidents SET next_case_number = next_case_number + 1 WHERE id = :i"
                          " RETURNING code, next_case_number - 1 AS n"), {"i": incident_id}).one()
    return f"{r.code}-{r.n}"


def default_district(conn: Connection, incident_id: int) -> int | None:
    """When nothing says where a report belongs, it goes to the incident's first district's desk, so it
    always has a home (Never lost). The case carries `district_guessed` so the desk can see why."""
    return conn.execute(text("SELECT min(id) FROM districts WHERE incident_id = :i"), {"i": incident_id}).scalar()


def create_case(conn: Connection, *, incident_id: int, district_id: int | None, report_id: int, fields: dict,
                actor: Actor, queue_since=None) -> dict:
    """Insert a case built from one report; link the report; append case.created."""
    flags = list(fields.get("flags", []))
    if district_id is None:
        district_id = default_district(conn, incident_id)
        flags.append("district_guessed")
    if fields.get("lat") is None and "needs_location" not in flags:
        flags.append("needs_location")
    public_id = next_public_id(conn, incident_id)
    case_id = conn.execute(text(
        "INSERT INTO cases (public_id, incident_id, district_id, status, priority, priority_reasons, people_count,"
        " people_count_kind, needs, vulnerable, hazards, geom, radius_m, location_confidence, location_method,"
        " location_source, location_text, provenance, summary, flags, queue_since, last_confirmed_at, attributes)"
        " VALUES (:pid, :inc, :dist, 'reported', :priority, :reasons, :people, :kind, :needs, :vuln, :haz,"
        "         CASE WHEN CAST(:lat AS float8) IS NULL THEN NULL"
        "              ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS float8), CAST(:lat AS float8)), 4326)::geography END,"
        "         :radius, :conf, :method, :src, :ltext, CAST(:prov AS jsonb), :summary, :flags,"
        "         coalesce(CAST(:queue_since AS timestamptz), now()), now(), CAST(:attrs AS jsonb))"
        " RETURNING id"),
        dict(pid=public_id, inc=incident_id, dist=district_id, priority=fields.get("priority", "P4"),
             reasons=fields.get("priority_reasons", []), people=fields.get("people_count"),
             kind=fields.get("people_count_kind"), needs=fields.get("needs", []), vuln=fields.get("vulnerable", []),
             haz=fields.get("hazards", []), lat=fields.get("lat"), lng=fields.get("lng"),
             radius=fields.get("radius_m"), conf=fields.get("location_confidence"),
             method=fields.get("location_method"), src=fields.get("location_source"),
             ltext=fields.get("location_text"), prov=json.dumps(fields.get("provenance", {}), ensure_ascii=False),
             summary=fields.get("summary"), flags=flags, queue_since=queue_since,
             attrs=json.dumps(fields.get("attributes", {}), ensure_ascii=False))).scalar_one()
    conn.execute(text("UPDATE reports SET case_id = :c, status = 'processed' WHERE id = :r"), {"c": case_id, "r": report_id})
    link_report_evidence(conn, report_id=report_id, case_id=case_id, incident_id=incident_id, district_id=district_id,
                         actor=actor)
    append_event(conn, actor=actor, action="case.created", entity_type="case", entity_id=case_id,
                 incident_id=incident_id, district_id=district_id, case_id=case_id,
                 data={"public_id": public_id, "report_id": report_id, "priority": fields.get("priority", "P4"),
                       "priority_reasons": fields.get("priority_reasons", []), "flags": flags})
    return {"case_id": case_id, "public_id": public_id, "district_id": district_id}


def link_report_evidence(conn: Connection, *, report_id: int, case_id: int, incident_id: int, district_id: int | None,
                         actor: Actor) -> None:
    """Attach a report's files to its case. Each file's sha256 goes into the audit chain (rule R16), so a file
    swapped on disk later no longer matches what history recorded."""
    rows = conn.execute(text("UPDATE evidence SET case_id = :c WHERE report_id = :r AND case_id IS NULL"
                             " RETURNING id, type, sha256, uri"), {"c": case_id, "r": report_id}).all()
    for ev in rows:
        append_event(conn, actor=actor, action="evidence.added", entity_type="evidence", entity_id=ev.id,
                     incident_id=incident_id, district_id=district_id, case_id=case_id,
                     data={"evidence_id": ev.id, "type": ev.type, "sha256": ev.sha256, "uri": ev.uri, "report_id": report_id})


# --- desk corrections (PRD F-L4 pin drag, §5.2 check, PATCH with If-Match) ---------------------------------

class Conflict(Exception):
    """409: someone else changed the case first. Carries who and when."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotAllowed(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def lock_case(conn: Connection, scope, ref: str):
    """SELECT … FOR UPDATE inside the caller's Scope (rule R8). None if not visible."""
    where, params = scope.case_where("c")
    key = "c.id = :ref_id" if ref.isdigit() else "c.public_id = :ref"
    return conn.execute(text(
        f"SELECT c.*, ST_Y(c.geom::geometry) AS lat, ST_X(c.geom::geometry) AS lng FROM cases c"
        f" WHERE {key} AND {where} FOR UPDATE"),
        {**params, "ref": ref, "ref_id": int(ref) if ref.isdigit() else None}).one_or_none()


def last_change(conn: Connection, case_id: int) -> str:
    r = conn.execute(text("SELECT e.at, coalesce(u.name, e.actor_id) AS who FROM events e"
                          " LEFT JOIN users u ON e.actor_type = 'user' AND u.id::text = e.actor_id"
                          " WHERE e.case_id = :c ORDER BY e.seq DESC LIMIT 1"), {"c": case_id}).one_or_none()
    return f"{r.who} at {hhmmss(r.at)}" if r else "someone"


def _actor(scope) -> Actor:
    return Actor("user", str(scope.user_id), scope.role)


def move_pin(conn: Connection, scope, ref: str, lat: float, lng: float, reason: str) -> dict:
    """A call-taker drags the pin: method = human, radius 50 m, audited with a reason. The case moves to
    the desk of the district the new pin is in."""
    case = lock_case(conn, scope, ref)
    if case is None:
        raise LookupError(ref)
    radius = get_config().location.radius_m.human
    district = conn.execute(text("SELECT id FROM districts WHERE incident_id = :i AND"
                                 " ST_Covers(boundary, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography)"),
                            {"i": case.incident_id, "lat": lat, "lng": lng}).scalar() or case.district_id
    method = f"Human · {radius} m · pin placed by {scope.name}: {reason}"
    flags = [f for f in case.flags if f not in ("needs_location", "district_guessed")]
    conn.execute(text(
        "UPDATE cases SET geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, radius_m = :r,"
        " location_confidence = 'high', location_method = :m, location_source = 'human', district_id = :d,"
        " flags = :f, version = version + 1, updated_at = now() WHERE id = :id"),
        {"lng": lng, "lat": lat, "r": radius, "m": method, "d": district, "f": flags, "id": case.id})
    append_event(conn, actor=_actor(scope), action="case.location_moved", entity_type="case", entity_id=case.id,
                 incident_id=case.incident_id, district_id=district, case_id=case.id, reason=reason,
                 data={"from": None if case.lat is None else {"lat": case.lat, "lng": case.lng, "radius_m": case.radius_m,
                                                                "method": case.location_method},
                       "to": {"lat": lat, "lng": lng, "radius_m": radius}, "district_changed": district != case.district_id})
    return {"case_id": case.id, "district_id": district, "location_method": method}


CHECKABLE = ("people_count", "hazards", "needs", "vulnerable", "place")


def check_case(conn: Connection, scope, ref: str) -> dict:
    """A person confirms the key fields: reported → checked ("Checked by Priya 02:05"). Guard: at least a
    coarse location exists (PRD §5.2)."""
    case = lock_case(conn, scope, ref)
    if case is None:
        raise LookupError(ref)
    if case.geom is None:
        raise NotAllowed("Needs at least a coarse location before it can be checked: place the pin first")
    prov = dict(case.provenance or {})
    for key in CHECKABLE:
        items = prov.get(key)
        for p in items if isinstance(items, list) else [items] if items else []:
            p.update(checked=True, checked_by=scope.name)
    status = "checked" if case.status == "reported" else case.status
    flags = [f for f in case.flags if f != "unchecked"]
    conn.execute(text("UPDATE cases SET status = :s, provenance = CAST(:p AS jsonb), checked_by = :u, checked_at = now(),"
                      " last_confirmed_at = now(), flags = :f, version = version + 1, updated_at = now() WHERE id = :id"),
                 {"s": status, "p": json.dumps(prov, ensure_ascii=False), "u": scope.user_id, "f": flags, "id": case.id})
    append_event(conn, actor=_actor(scope), action="case.checked", entity_type="case", entity_id=case.id,
                 incident_id=case.incident_id, district_id=case.district_id, case_id=case.id,
                 data={"status": status, "checked_by": scope.name})
    return {"case_id": case.id, "status": status}


EDITABLE = {"people_count", "needs", "vulnerable", "hazards"}


def edit_case(conn: Connection, scope, ref: str, changes: dict, reason: str, if_match: int | None) -> dict:
    """Field edits by a person, with a reason, under optimistic locking (If-Match: version). A stale
    version gets a 409 naming who changed the case and when."""
    case = lock_case(conn, scope, ref)
    if case is None:
        raise LookupError(ref)
    if if_match is None:
        raise NotAllowed("Send If-Match with the version you are editing")
    if if_match != case.version:
        raise Conflict(f"Changed by {last_change(conn, case.id)} while you were editing. Reload to see it.")
    unknown = set(changes) - EDITABLE
    if unknown:
        raise NotAllowed(f"Not editable here: {sorted(unknown)}")
    prov = dict(case.provenance or {})
    before = {k: getattr(case, k) for k in changes}
    for k, v in changes.items():
        entry = {"value": v, "method": "human", "quote": None, "report_id": None, "checked": True,
                 "checked_by": scope.name, "reason": reason}
        prov[k] = entry if k == "people_count" else [{**entry, "value": x} for x in v]
    sets = ", ".join(f"{k} = :{k}" for k in changes)
    conn.execute(text(f"UPDATE cases SET {sets}, provenance = CAST(:prov AS jsonb), version = version + 1,"
                      " updated_at = now() WHERE id = :id"),
                 {**changes, "prov": json.dumps(prov, ensure_ascii=False), "id": case.id})
    append_event(conn, actor=_actor(scope), action="case.updated", entity_type="case", entity_id=case.id,
                 incident_id=case.incident_id, district_id=case.district_id, case_id=case.id, reason=reason,
                 data={"changed": {k: {"from": before[k], "to": v} for k, v in changes.items()}})
    return {"case_id": case.id, "version": case.version + 1}
