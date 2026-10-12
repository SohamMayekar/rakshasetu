"""Who could this be? (PRD F-D1) Candidates are open cases in the SAME incident that share the phone or
device, lie within 3 km, or have the same village; ranked before the cap of 50: same phone/device first,
then nearest, then same village. Each becomes a Household for scoring."""

from sqlalchemy import Connection, text

from app.config import get_config
from app.modules.dedupe.signals import Household

OPEN = "('reported', 'checked', 'assigned', 'acknowledged', 'reached', 'rescued')"


def landmark_keys(detail: dict | None, provenance: dict | None) -> dict[str, str]:
    keys: dict[str, str] = {}
    for lm in (detail or {}).get("landmarks", []):          # features the ladder matched on the map
        keys[f"osm:{lm['osm_id']}"] = lm.get("name") or lm["type"]
    matched_types = {lm["type"] for lm in (detail or {}).get("landmarks", [])}
    for p in (provenance or {}).get("landmarks", []):       # words with no mapped feature: the bare type
        t = (p.get("value") or {}).get("type")
        if t and t not in matched_types:
            keys[f"type:{t}"] = t
    return keys


def candidates(conn: Connection, incident_id: int, new: Household, exclude_case: int | None = None) -> list[Household]:
    cfg = get_config().dedupe
    rows = conn.execute(text(f"""
        WITH hits AS (
          SELECT c.id,
                 EXISTS (SELECT 1 FROM reports r WHERE r.case_id = c.id AND (
                           (r.reporter_phone_hash IS NOT NULL AND r.reporter_phone_hash = ANY(:phones))
                        OR (r.device_hash IS NOT NULL AND r.device_hash = ANY(:devices)))) AS phone_hit,
                 CASE WHEN c.geom IS NOT NULL AND CAST(:lat AS float8) IS NOT NULL
                      THEN ST_Distance(c.geom, ST_SetSRID(ST_MakePoint(CAST(:lng AS float8), CAST(:lat AS float8)), 4326)::geography)
                 END AS dist,
                 (c.location_text IS NOT NULL AND lower(c.location_text) = lower(CAST(:village AS text))) AS village_hit
          FROM cases c
          WHERE c.incident_id = :inc AND c.status IN {OPEN} AND c.id IS DISTINCT FROM :exclude)
        SELECT c.id, c.public_id, c.location_text, ST_Y(c.geom::geometry) AS lat, ST_X(c.geom::geometry) AS lng,
               c.radius_m, c.location_confidence, c.people_count, c.attributes, c.provenance, h.phone_hit
        FROM hits h JOIN cases c ON c.id = h.id
        WHERE h.phone_hit OR h.dist <= :radius OR h.village_hit
        ORDER BY h.phone_hit DESC, h.dist NULLS LAST, h.village_hit DESC, c.id
        LIMIT :cap"""),
        {"phones": list(new.phones), "devices": list(new.devices), "lat": new.lat, "lng": new.lng,
         "village": new.village, "inc": incident_id, "exclude": exclude_case,
         "radius": cfg.candidate_radius_km * 1000, "cap": cfg.candidate_cap}).all()
    if not rows:
        return []
    ids = [r.id for r in rows]
    reps = conn.execute(text("SELECT case_id, array_agg(DISTINCT reporter_phone_hash) FILTER (WHERE reporter_phone_hash IS NOT NULL) AS phones,"
                             " array_agg(DISTINCT device_hash) FILTER (WHERE device_hash IS NOT NULL) AS devices,"
                             " max(received_at) AS at FROM reports WHERE case_id = ANY(:ids) GROUP BY case_id"),
                        {"ids": ids}).all()
    by_case = {r.case_id: r for r in reps}
    out = []
    for r in rows:
        rep = by_case.get(r.id)
        attrs = r.attributes or {}
        out.append(Household(
            case_id=r.id, public_id=r.public_id, phones=set(rep.phones or []) if rep else set(),
            devices=set(rep.devices or []) if rep else set(), village=r.location_text, lat=r.lat, lng=r.lng,
            radius_m=r.radius_m, confidence=r.location_confidence,
            landmarks=landmark_keys(attrs.get("location_detail"), r.provenance), people=r.people_count,
            names=list(attrs.get("person_names") or []), at=rep.at if rep else None))
    return out
