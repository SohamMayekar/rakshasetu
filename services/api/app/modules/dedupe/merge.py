"""Merging and undoing (PRD F-D2). The older case is canonical; the newer one is absorbed: its reports and
evidence move to the older case, its status becomes `merged` (its id redirects on the status page).
Fields are reconciled with provenance kept: needs = the union; headcount = the maximum, every source kept.

Every merge stores the EXACT before-state of both cases, their reports, evidence and suggestions, so an
undo ("split") restores them exactly, records a merge block, and is audited. Rule R1: events last.
"""

import json

from sqlalchemy import Connection, text

from app.core.eventlog import Actor, append_event
from app.modules.cases.service import Conflict, NotAllowed, retriage
from app.modules.evidence.service import JSON, add, record_bytes
from app.pipeline.fields import summary

OPEN = ("reported", "checked", "assigned", "acknowledged", "reached", "rescued")


def _case(conn: Connection, case_id: int):
    return conn.execute(text("SELECT *, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng FROM cases"
                             " WHERE id = :id FOR UPDATE"), {"id": case_id}).one()


def _union(a, b) -> list:
    return list(dict.fromkeys([*(a or []), *(b or [])]))


def _snapshot(conn: Connection, target_id: int, source_id: int) -> dict:
    j = lambda sql, **p: [dict(r._mapping) for r in conn.execute(text(sql), p)]  # noqa: E731
    return {
        "target": conn.execute(text("SELECT to_jsonb(c) FROM cases c WHERE id = :i"), {"i": target_id}).scalar_one(),
        "source": conn.execute(text("SELECT to_jsonb(c) FROM cases c WHERE id = :i"), {"i": source_id}).scalar_one(),
        "reports": j("SELECT id, case_id, status FROM reports WHERE case_id = :s", s=source_id),
        "evidence": j("SELECT id, case_id FROM evidence WHERE case_id = :s", s=source_id),
        "suggestions": j("SELECT id, status, decided_by, decided_at FROM merge_suggestions"
                         " WHERE (case_id = :s OR candidate_case_id = :s) AND status = 'open'", s=source_id),
    }


def merge_cases(conn: Connection, *, target_id: int, source_id: int, actor: Actor, decided_by: str, score=None,
                signals=None, reasons=None, line: str = "", reason: str | None = None,
                suggestion_id: int | None = None) -> int:
    """Fold `source` into `target`. Locks both in id order (no deadlocks). Returns the merge id."""
    if target_id == source_id:
        raise NotAllowed("A case can't be merged into itself")
    first, second = sorted((target_id, source_id))
    rows = {first: _case(conn, first), second: _case(conn, second)}
    target, source = rows[target_id], rows[source_id]
    if target.incident_id != source.incident_id:
        raise NotAllowed("Cases from different incidents are never merged")
    for c in (target, source):
        if c.status not in OPEN:
            raise Conflict(f"{c.public_id} is {c.status}; reload to see it")
    live = conn.execute(text("SELECT count(DISTINCT case_id) FROM assignments WHERE case_id IN (:a, :b)"
                             " AND state IN ('open', 'overdue')"), {"a": target_id, "b": source_id}).scalar()
    if live == 2:   # P1 #12 merge guard: two live owners is a person's call, never automatic
        raise Conflict("Both cases have a team on them: pick the keeper and stand the other team down")
    snap = _snapshot(conn, target_id, source_id)

    prov = dict(target.provenance or {})
    sprov = source.provenance or {}
    for key in ("hazards", "needs", "vulnerable", "landmarks", "names"):
        prov[key] = [*(prov.get(key) or []), *(sprov.get(key) or [])]
    sources = [*(prov.get("people_count_sources") or ([prov["people_count"]] if prov.get("people_count") else [])),
               *(sprov.get("people_count_sources") or ([sprov["people_count"]] if sprov.get("people_count") else []))]
    if sources:
        prov["people_count_sources"] = sources
        prov["people_count"] = max(sources, key=lambda p: p.get("value") or 0)
    people = max([target.people_count or 0, source.people_count or 0]) or None
    hazards, needs = _union(target.hazards, source.hazards), _union(target.needs, source.needs)
    vulnerable = _union(target.vulnerable, source.vulnerable)
    attrs = {**(source.attributes or {}), **(target.attributes or {}),
             "person_names": _union((target.attributes or {}).get("person_names"),
                                    (source.attributes or {}).get("person_names"))}
    take_location = target.geom is None and source.geom is not None
    flags = [f for f in _union(target.flags, source.flags)
             if f not in ("possible_duplicate",) and not (f == "needs_location" and (target.geom or source.geom))]
    conn.execute(text(
        "UPDATE cases SET people_count = :people, hazards = :hz, needs = :nd, vulnerable = :vu,"
        " provenance = CAST(:prov AS jsonb), attributes = CAST(:attrs AS jsonb), summary = :summary, flags = :flags,"
        " queue_since = least(queue_since, :src_since), last_confirmed_at = now(), version = version + 1, updated_at = now()"
        + (", geom = (SELECT geom FROM cases WHERE id = :sid), radius_m = :radius, location_confidence = :conf,"
           " location_method = :method, location_source = :lsrc, location_text = :ltext" if take_location else "")
        + " WHERE id = :tid"),
        {"people": people, "hz": hazards, "nd": needs, "vu": vulnerable, "prov": json.dumps(prov, ensure_ascii=False),
         "attrs": json.dumps(attrs, ensure_ascii=False, default=str),
         "summary": summary(people, target.people_count_kind, hazards, needs, vulnerable), "flags": flags,
         "src_since": source.queue_since, "sid": source_id, "tid": target_id, "radius": source.radius_m,
         "conf": source.location_confidence, "method": source.location_method, "lsrc": source.location_source,
         "ltext": source.location_text})
    conn.execute(text("UPDATE cases SET status = 'merged', parent_case_id = :t, flags = array_remove(flags, 'possible_duplicate'),"
                      " version = version + 1, updated_at = now() WHERE id = :s"), {"t": target_id, "s": source_id})
    conn.execute(text("UPDATE reports SET case_id = :t, status = 'merged' WHERE case_id = :s"), {"t": target_id, "s": source_id})
    conn.execute(text("UPDATE evidence SET case_id = :t WHERE case_id = :s"), {"t": target_id, "s": source_id})
    conn.execute(text("UPDATE merge_suggestions SET status = CASE WHEN id = :sug THEN 'accepted' ELSE 'superseded' END,"
                      " decided_at = now(), decided_by = :uid WHERE (case_id = :s OR candidate_case_id = :s) AND status = 'open'"),
                 {"sug": suggestion_id, "s": source_id, "uid": int(actor.id) if actor.type == "user" else None})
    merge_id = conn.execute(text(
        "INSERT INTO merges (incident_id, target_case_id, source_case_id, score, signals, reasons, decided_by, snapshot)"
        " VALUES (:i, :t, :s, :score, CAST(:sig AS jsonb), :rs, :by, CAST(:snap AS jsonb)) RETURNING id"),
        {"i": target.incident_id, "t": target_id, "s": source_id, "score": score, "sig": json.dumps(signals or {}),
         "rs": reasons or [], "by": decided_by, "snap": json.dumps(snap, default=str)}).scalar_one()
    # the merge record as evidence: what was decided and why
    meta = {"merge_id": merge_id, "source": source.public_id, "target": target.public_id, "score": score,
            "reasons": reasons or [], "line": line}
    add(conn, type="merge", content=record_bytes({**meta, "signals": signals or {}, "decided_by": decided_by, "reason": reason}),
        mime=JSON, actor=actor, added_by=decided_by, case_id=target_id, incident_id=target.incident_id,
        district_id=target.district_id, meta=meta)
    retriage(conn, target_id, actor, why=f"merged with {source.public_id}")
    data = {"merge_id": merge_id, "target": target.public_id, "source": source.public_id, "source_case_id": source_id,
            "score": score, "reasons": reasons or [], "line": line, "kind": "auto" if decided_by == "rule" else "person"}
    append_event(conn, actor=actor, action="case.merged", entity_type="case", entity_id=target_id,
                 incident_id=target.incident_id, district_id=target.district_id, case_id=target_id, reason=reason, data=data)
    append_event(conn, actor=actor, action="case.absorbed", entity_type="case", entity_id=source_id,
                 incident_id=source.incident_id, district_id=source.district_id, case_id=source_id, reason=reason, data=data)
    return merge_id


def _restore_case(conn: Connection, snap: dict) -> None:
    cols = [r[0] for r in conn.execute(text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'cases'"
        " AND column_name <> 'id' ORDER BY ordinal_position"))]
    collist = ", ".join(cols)
    conn.execute(text(f"UPDATE cases SET ({collist}) = (SELECT {collist} FROM jsonb_populate_record(NULL::cases,"
                      " CAST(:snap AS jsonb))) WHERE id = :id"), {"snap": json.dumps(snap), "id": snap["id"]})


def undo_merge(conn: Connection, merge_id: int, actor: Actor, reason: str) -> dict:
    """Split: put both cases, their reports, evidence and suggestions back EXACTLY as they were, and block the
    pair so it's never suggested again."""
    m = conn.execute(text("SELECT * FROM merges WHERE id = :id FOR UPDATE"), {"id": merge_id}).one_or_none()
    if m is None:
        raise LookupError(merge_id)
    if m.undone_at:
        who = conn.execute(text("SELECT name FROM users WHERE id = :u"), {"u": m.undone_by}).scalar() or "someone"
        from app.core.clock import hhmmss
        raise Conflict(f"Already undone by {who} at {hhmmss(m.undone_at)}")
    snap = m.snapshot
    _case(conn, m.target_case_id), _case(conn, m.source_case_id)
    _restore_case(conn, snap["target"])
    _restore_case(conn, snap["source"])
    for r in snap["reports"]:
        conn.execute(text("UPDATE reports SET case_id = :c, status = :s WHERE id = :id"),
                     {"c": r["case_id"], "s": r["status"], "id": r["id"]})
    for e in snap["evidence"]:
        conn.execute(text("UPDATE evidence SET case_id = :c WHERE id = :id"), {"c": e["case_id"], "id": e["id"]})
    for s in snap["suggestions"]:
        conn.execute(text("UPDATE merge_suggestions SET status = 'rejected', decided_by = :u, decided_at = now()"
                          " WHERE id = :id"), {"id": s["id"], "u": int(actor.id) if actor.type == "user" else None})
    conn.execute(text("DELETE FROM evidence WHERE type = 'merge' AND case_id = :t AND (meta->>'merge_id')::bigint = :m"),
                 {"t": m.target_case_id, "m": merge_id})
    lo, hi = sorted((m.target_case_id, m.source_case_id))
    conn.execute(text("INSERT INTO merge_blocks (case_a, case_b, created_by, reason) VALUES (:a, :b, :u, :r)"
                      " ON CONFLICT DO NOTHING"), {"a": lo, "b": hi, "r": reason,
                                                    "u": int(actor.id) if actor.type == "user" else None})
    conn.execute(text("UPDATE merges SET undone_by = :u, undone_at = now(), undo_reason = :r WHERE id = :id"),
                 {"u": int(actor.id) if actor.type == "user" else None, "r": reason, "id": merge_id})
    data = {"merge_id": merge_id, "target_case_id": m.target_case_id, "source_case_id": m.source_case_id}
    for cid in (m.target_case_id, m.source_case_id):
        c = conn.execute(text("SELECT incident_id, district_id FROM cases WHERE id = :i"), {"i": cid}).one()
        append_event(conn, actor=actor, action="case.unmerged", entity_type="case", entity_id=cid,
                     incident_id=c.incident_id, district_id=c.district_id, case_id=cid, reason=reason, data=data)
    return data


def record_suggestion(conn: Connection, *, incident_id: int, district_id: int | None, case_id: int, match,
                      line: str, actor: Actor) -> int:
    sid = conn.execute(text(
        "INSERT INTO merge_suggestions (incident_id, case_id, candidate_case_id, score, strength, signals, reasons, conflicts)"
        " VALUES (:i, :c, :cand, :s, :st, CAST(:sig AS jsonb), :rs, :cf) RETURNING id"),
        {"i": incident_id, "c": case_id, "cand": match.candidate.case_id, "s": match.score.total, "st": match.strength,
         "sig": json.dumps(match.score.signals), "rs": match.reasons, "cf": match.conflicts}).scalar_one()
    if match.outcome != "refused":
        conn.execute(text("UPDATE cases SET flags = array_append(flags, 'possible_duplicate')"
                          " WHERE id = :c AND NOT ('possible_duplicate' = ANY(flags))"), {"c": case_id})
    append_event(conn, actor=actor, action="merge.refused" if match.outcome == "refused" else "merge.suggested",
                 entity_type="merge_suggestion", entity_id=sid, incident_id=incident_id, district_id=district_id,
                 case_id=case_id, data={"suggestion_id": sid, "candidate_case_id": match.candidate.case_id,
                                        "candidate": match.candidate.public_id, "score": match.score.total,
                                        "strength": match.strength, "line": line, "conflicts": match.conflicts})
    return sid
