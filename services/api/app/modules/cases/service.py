"""Case writes. Every change ends with append_event() (rule R1)."""

import json

from sqlalchemy import Connection, text

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
