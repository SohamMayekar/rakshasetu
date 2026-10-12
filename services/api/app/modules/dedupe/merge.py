"""Merging (PRD F-D2). The older case is canonical; the absorbed report becomes evidence on it. Fields are
reconciled with provenance kept: needs = the union; headcount = the maximum (with every source kept).
Every merge stores the EXACT before-state, so an undo (m28) restores it exactly. Rule R1: events last."""

import json

from sqlalchemy import Connection, text

from app.core.eventlog import Actor, append_event
from app.modules.cases.service import link_report_evidence, retriage
from app.pipeline.fields import summary


def snapshot_case(conn: Connection, case_id: int) -> dict:
    return conn.execute(text("SELECT to_jsonb(c) FROM cases c WHERE id = :id"), {"id": case_id}).scalar_one()


def _union(a: list, b: list) -> list:
    return list(dict.fromkeys([*(a or []), *(b or [])]))


def reconcile(target, fields: dict, report_id: int) -> dict:
    """The merged values for `target` (a case row) after adding `fields` from a new report."""
    prov = dict(target.provenance or {})
    newp = fields.get("provenance", {})
    for key in ("hazards", "needs", "vulnerable", "landmarks", "names"):
        prov[key] = [*(prov.get(key) or []), *(newp.get(key) or [])]
    sources = list(prov.get("people_count_sources") or ([prov["people_count"]] if prov.get("people_count") else []))
    if newp.get("people_count"):
        sources.append(newp["people_count"])
    if sources:
        prov["people_count_sources"] = sources
        prov["people_count"] = max(sources, key=lambda p: p.get("value") or 0)   # dispatch plans for the most
    people = max([p.get("value") or 0 for p in sources], default=0) or target.people_count
    out = {
        "people_count": people, "hazards": _union(target.hazards, fields.get("hazards")),
        "needs": _union(target.needs, fields.get("needs")), "vulnerable": _union(target.vulnerable, fields.get("vulnerable")),
        "provenance": prov,
        "attributes": {**(target.attributes or {}),
                       "person_names": _union((target.attributes or {}).get("person_names"),
                                              (fields.get("attributes") or {}).get("person_names"))},
    }
    if target.geom is None and fields.get("lat") is not None:     # the household had no pin; this report has one
        out.update({k: fields.get(k) for k in ("lat", "lng", "radius_m", "location_confidence", "location_method",
                                               "location_source", "location_text")})
        out["attributes"]["location_detail"] = (fields.get("attributes") or {}).get("location_detail")
    out["summary"] = summary(out["people_count"], target.people_count_kind, out["hazards"], out["needs"], out["vulnerable"])
    return out


def attach_report(conn: Connection, *, target_id: int, report_id: int, fields: dict, score: float, signals: dict,
                  reasons: list[str], reason_line: str, actor: Actor, decided_by: str = "rule") -> int:
    """Auto-merge: link a new report straight to the existing case. Returns the merge id."""
    target = conn.execute(text("SELECT *, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng FROM cases"
                               " WHERE id = :id FOR UPDATE"), {"id": target_id}).one()
    snap = {"target": snapshot_case(conn, target_id),
            "report": conn.execute(text("SELECT case_id, status FROM reports WHERE id = :r"), {"r": report_id}).one()._asdict()}
    m = reconcile(target, fields, report_id)
    flags = list(target.flags)
    sets = ("people_count = :people, hazards = :hazards, needs = :needs, vulnerable = :vulnerable,"
            " provenance = CAST(:prov AS jsonb), attributes = CAST(:attrs AS jsonb), summary = :summary,"
            " last_confirmed_at = now(), version = version + 1, updated_at = now()")
    params = {"people": m["people_count"], "hazards": m["hazards"], "needs": m["needs"], "vulnerable": m["vulnerable"],
              "prov": json.dumps(m["provenance"], ensure_ascii=False), "attrs": json.dumps(m["attributes"], ensure_ascii=False),
              "summary": m["summary"], "id": target_id}
    if "lat" in m:
        sets += (", geom = ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, radius_m = :radius,"
                 " location_confidence = :conf, location_method = :method, location_source = :src, location_text = :ltext,"
                 " flags = :flags")
        params.update(lat=m["lat"], lng=m["lng"], radius=m["radius_m"], conf=m["location_confidence"],
                      method=m["location_method"], src=m["location_source"], ltext=m["location_text"],
                      flags=[f for f in flags if f != "needs_location"])
    conn.execute(text(f"UPDATE cases SET {sets} WHERE id = :id"), params)
    conn.execute(text("UPDATE reports SET case_id = :c, status = 'merged' WHERE id = :r"), {"c": target_id, "r": report_id})
    merge_id = conn.execute(text(
        "INSERT INTO merges (incident_id, target_case_id, source_report_id, score, signals, reasons, decided_by, snapshot)"
        " VALUES (:i, :t, :r, :s, CAST(:sig AS jsonb), :rs, :by, CAST(:snap AS jsonb)) RETURNING id"),
        {"i": target.incident_id, "t": target_id, "r": report_id, "s": score, "sig": json.dumps(signals), "rs": reasons,
         "by": decided_by, "snap": json.dumps(snap, default=str)}).scalar_one()
    conn.execute(text("INSERT INTO evidence (case_id, report_id, type, added_by, meta)"
                      " VALUES (:c, :r, 'merge', :by, CAST(:meta AS jsonb))"),
                 {"c": target_id, "r": report_id, "by": decided_by,
                  "meta": json.dumps({"merge_id": merge_id, "score": score, "reasons": reasons})})
    link_report_evidence(conn, report_id=report_id, case_id=target_id, incident_id=target.incident_id,
                         district_id=target.district_id, actor=actor)
    retriage(conn, target_id, actor, why="a merged report added facts")
    append_event(conn, actor=actor, action="case.merged", entity_type="case", entity_id=target_id,
                 incident_id=target.incident_id, district_id=target.district_id, case_id=target_id,
                 data={"merge_id": merge_id, "report_id": report_id, "public_id": target.public_id, "score": score,
                       "reasons": reasons, "line": reason_line, "kind": "auto" if decided_by == "rule" else "person"})
    return merge_id


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
