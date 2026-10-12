"""Audit reads. The chain itself is written only by app.core.eventlog.append_event()."""

import json

from sqlalchemy import Connection, text

from app.core.eventlog import verify_chain


def head(conn: Connection) -> dict:
    r = conn.execute(text("SELECT seq, hash, at FROM events ORDER BY seq DESC LIMIT 1")).one_or_none()
    return {"seq": r.seq, "hash": r.hash, "at": r.at.isoformat()} if r else {"seq": 0, "hash": None, "at": None}


def verify(conn: Connection) -> dict:
    return verify_chain(conn)


def list_events(conn: Connection, *, where_sql: str = "TRUE", params: dict | None = None, case_id: int | None = None,
                entity_type: str | None = None, entity_id: str | None = None, actor_id: str | None = None,
                after_seq: int = 0, limit: int = 200) -> list[dict]:
    """Events filtered by entity/actor/case. `where_sql` carries the caller's Scope (rule R8)."""
    clauses = [where_sql, "seq > :after"]
    p = {"after": after_seq, "limit": min(limit, 1000), **(params or {})}
    if case_id is not None:
        clauses.append("case_id = :case_id")
        p["case_id"] = case_id
    if entity_type:
        clauses.append("entity_type = :etype")
        p["etype"] = entity_type
    if entity_id:
        clauses.append("entity_id = :eid")
        p["eid"] = entity_id
    if actor_id:
        clauses.append("actor_id = :aid")
        p["aid"] = actor_id
    rows = conn.execute(text(
        f"SELECT seq, at, actor_type, actor_id, actor_role, action, entity_type, entity_id, incident_id, case_id,"
        f" team_id, body, reason, hash FROM events WHERE {' AND '.join(clauses)} ORDER BY seq LIMIT :limit"), p).all()
    return [{"seq": r.seq, "at": r.at.isoformat(), "actor": {"type": r.actor_type, "id": r.actor_id, "role": r.actor_role},
             "action": r.action, "entity": {"type": r.entity_type, "id": r.entity_id}, "incident_id": r.incident_id,
             "case_id": r.case_id, "team_id": r.team_id, "data": json.loads(r.body).get("data", {}),
             "reason": r.reason, "hash": r.hash} for r in rows]
