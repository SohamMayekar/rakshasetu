"""Case reads. Every function takes the caller's Scope and puts it in the SQL WHERE (rule R8)."""

from sqlalchemy import Connection, text

from app.core.auth import Scope

CASE_COLUMNS = """
  c.id, c.public_id, c.incident_id, i.code AS incident_code, c.district_id, d.name AS district, c.status,
  c.priority, c.priority_reasons, c.priority_override, c.people_count, c.people_count_kind, c.people_remaining,
  c.needs, c.vulnerable, c.hazards, ST_Y(c.geom::geometry) AS lat, ST_X(c.geom::geometry) AS lng, c.radius_m,
  c.location_confidence, c.location_method, c.location_source, c.location_text, c.provenance, c.summary,
  c.checked_by, c.checked_at, c.last_confirmed_at, c.parent_case_id, c.queue_since, c.flags, c.attributes,
  c.escalation_level, c.resolution, c.version, c.created_at, c.updated_at
"""
FROM = "FROM cases c JOIN incidents i ON i.id = c.incident_id LEFT JOIN districts d ON d.id = c.district_id"


def _row(r) -> dict:
    d = dict(r._mapping)
    for k in ("queue_since", "checked_at", "last_confirmed_at", "created_at", "updated_at"):
        if d.get(k) is not None:
            d[k] = d[k].isoformat()
    return d


def list_cases(conn: Connection, scope: Scope, incident_code: str | None = None, limit: int = 500) -> list[dict]:
    where, params = scope.case_where("c")
    clauses = [where]
    if incident_code:
        clauses.append("i.code = :code")
        params["code"] = incident_code
    rows = conn.execute(text(f"SELECT {CASE_COLUMNS} {FROM} WHERE {' AND '.join(clauses)}"
                             " ORDER BY c.queue_since LIMIT :limit"), {**params, "limit": limit}).all()
    return [_row(r) for r in rows]


def get_case(conn: Connection, scope: Scope, ref: str) -> dict | None:
    """`ref` is a public id (BR-214) or a numeric id."""
    where, params = scope.case_where("c")
    key = "c.public_id = :ref" if not ref.isdigit() else "c.id = :ref_id"
    params.update(ref=ref, ref_id=int(ref) if ref.isdigit() else None)
    r = conn.execute(text(f"SELECT {CASE_COLUMNS} {FROM} WHERE {key} AND {where}"), params).one_or_none()
    return _row(r) if r else None


def case_exists(conn: Connection, ref: str) -> bool:
    """Unscoped existence check, used only to choose 403 over 404 for a team lead (the PRD's visible denial)."""
    key = "public_id = :ref" if not ref.isdigit() else "id = :ref_id"
    return conn.execute(text(f"SELECT 1 FROM cases WHERE {key}"),
                        {"ref": ref, "ref_id": int(ref) if ref.isdigit() else None}).first() is not None


def reports_for_case(conn: Connection, scope: Scope, case_id: int) -> list[dict]:
    where, params = scope.case_where("c")
    rows = conn.execute(text(
        "SELECT r.id, r.channel, r.received_at, r.reporter_phone_masked, r.reporter_relation, r.is_forward,"
        " r.language, r.text, r.transcript, r.extraction_method, r.receipt, r.status, r.source"
        f" FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.case_id = :case AND {where}"
        " ORDER BY r.received_at"), {**params, "case": case_id}).all()
    out = []
    for r in rows:
        d = dict(r._mapping)
        d["received_at"] = d["received_at"].isoformat()
        out.append(d)
    return out
