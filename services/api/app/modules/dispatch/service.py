"""Dispatch suggestions (PRD F-C4): standard practice (nearest suitable unit, as 112's CAD does), shown with
reasons; an OFFICER assigns. Deterministic: the same case and teams always give the same list.

Rank the teams already deployed in the case's district by
    1. capability match   boat for people trapped by water; heavy lift for a collapse; medical preferred for
                          an urgent medical need
    2. distance           straight line from the team's last known position, labelled as such, with its age
    3. current load       active assignments, never above the team's max_active
Overdue and out-of-service teams are greyed out with the reason, never suggested (an overdue team is greyed
until it's heard from).
"""

import math
from datetime import UTC, datetime

from sqlalchemy import Connection, text

from app.config import get_config

WATER = {"trapped_on_roof", "trapped_inside", "water_entering", "water_rising", "strong_current", "cut_off"}
COLLAPSE = {"buried", "structure_collapsed", "landslide"}


def needed(hazards: list[str], needs: list[str]) -> tuple[set[str], set[str]]:
    """(required capabilities, preferred capabilities) for a case."""
    required, preferred = set(), set()
    if set(hazards) & WATER:
        required.add("boat")
    if set(hazards) & COLLAPSE:
        required.add("heavy_lift")
    if "medical_urgent" in needs:
        preferred.add("medical")
    return required, preferred


def _km(lat1, lng1, lat2, lng2) -> float:
    dy = (lat1 - lat2) * 111.32
    dx = (lng1 - lng2) * 111.32 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _age(minutes: float) -> str:
    m = int(minutes)
    return f"{m} min" if m < 120 else f"{m // 60} h"


def teams_for(conn: Connection, incident_id: int, district_id: int | None) -> list:
    return conn.execute(text(
        "SELECT t.id, t.name, t.agency, t.capabilities, t.has_app, t.radio_channel, t.status, t.status_reason,"
        " t.max_active, t.last_geom_at,"
        " ST_Y(coalesce(t.last_geom, t.base_geom)::geometry) AS lat, ST_X(coalesce(t.last_geom, t.base_geom)::geometry) AS lng,"
        " (SELECT count(*) FROM assignments a WHERE a.team_id = t.id AND a.state IN ('open', 'overdue')) AS active"
        " FROM teams t WHERE t.incident_id = :i AND (CAST(:d AS bigint) IS NULL OR t.district_id = :d) ORDER BY t.id"),
        {"i": incident_id, "d": district_id}).all()


def rank(case: dict, teams: list, now: datetime | None = None) -> dict:
    """{suggestions: top_n [{team…, reasons, line}], greyed: [{team, why}]} — pure over the rows given."""
    cfg = get_config().dispatch
    now = now or datetime.now(UTC)
    required, preferred = needed(case.get("hazards") or [], case.get("needs") or [])
    excluded = set(cfg.get("exclude_team_status", ["overdue", "out_of_service"]))
    ranked, greyed = [], []
    for t in teams:
        if t.status in excluded:
            why = t.status_reason or {"overdue": "contact overdue: greyed until heard from",
                                      "out_of_service": "out of service"}.get(t.status, t.status)
            greyed.append({"team_id": t.id, "name": t.name, "why": why})
            continue
        if t.active >= t.max_active:
            greyed.append({"team_id": t.id, "name": t.name, "why": f"at capacity ({t.active} of {t.max_active})"})
            continue
        caps = set(t.capabilities or [])
        missing = required - caps
        cap_score = (0 if missing else 2) + (1 if preferred & caps else 0)
        dist = (_km(case["lat"], case["lng"], t.lat, t.lng)
                if case.get("lat") is not None and t.lat is not None else None)
        age = (now - t.last_geom_at).total_seconds() / 60 if t.last_geom_at else None
        parts = [f"{dist:.1f} km straight-line" if dist is not None else "distance unknown (no pin)"]
        if age is not None:
            parts.append(f"position {_age(age)} old")
        parts.append(", ".join(sorted(caps)) or "no listed equipment")
        parts.append(f"{t.active} active")
        if missing:
            parts.append(f"no {', '.join(sorted(missing))}")
        if not t.has_app:
            parts.append(f"radio only ({t.radio_channel or 'radio'})")
        ranked.append({"team_id": t.id, "name": t.name, "agency": t.agency, "capabilities": sorted(caps),
                       "has_app": t.has_app, "distance_km": None if dist is None else round(dist, 1),
                       "position_age_min": None if age is None else int(age), "active": t.active,
                       "max_active": t.max_active, "missing": sorted(missing), "line": " · ".join(parts),
                       "_key": (-cap_score, dist if dist is not None else 1e9, t.active, t.id)})
    ranked.sort(key=lambda r: r.pop("_key"))
    for i, r in enumerate(ranked, start=1):
        r["rank"] = i
    top = cfg.get("top_n", 3)
    return {"suggestions": ranked[:top], "more": ranked[top:], "greyed": greyed}
