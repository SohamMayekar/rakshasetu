"""Dispatch suggestions (PRD F-C4): standard practice (nearest suitable unit, as 112's CAD does), shown with
reasons; an OFFICER assigns. Deterministic: the same case and teams always give the same list.

Rank the teams already deployed in the case's district by
    1. capability match   boat for people trapped by water; heavy lift for a collapse; medical preferred for
                          an urgent medical need
    2. distance           straight line from the team's last known position, labelled as such, with its age
    3. current load       active assignments, never above the team's max_active
Overdue and out-of-service teams are greyed out with the reason, never suggested; so is a team that still owes a
stand-down (it went quiet, a case was moved off it, and nobody has heard from it since). (An overdue team is greyed
until it's heard from).

A team that does NOT have what this report needs (a collapse needs heavy lift: a boat team is not the answer) is
never a suggestion either: it is listed BELOW the line with the gap in its own words ("no heavy_lift for this
report"), still dispatchable — the officer may judge that rope is better than nothing, and the gap stays on the
screen. If no team matches, the suggestions come back empty and the screen says so.
"""

import math
from datetime import UTC, datetime

from sqlalchemy import Connection, text

from app.capabilities import helpful
from app.config import get_config

WATER = {"water_entering", "water_rising", "strong_current"}          # the water itself: a boat is needed
NOT_WATER = {"fire", "smoke_gas", "earthquake", "wind_damage", "structure_collapsed", "buried", "landslide", "road_accident"}
COLLAPSE = {"buried", "structure_collapsed", "landslide", "earthquake"}
FIRE = {"fire", "smoke_gas"}
FIRE_AGENCIES = {"Fire & Rescue", "Fire Brigade", "Fire"}               # a fire crew counts as "fire" without a listing


def needed(hazards: list[str], needs: list[str]) -> tuple[set[str], set[str]]:
    """(required capabilities, preferred capabilities) for a case."""
    h = set(hazards)
    required, preferred = set(), set()
    # A boat is for water. "Trapped" or "stranded" alone (a fire, a collapse, a stalled bus) never asks for one; a
    # roof does, unless something other than water explains why they are up there.
    if h & WATER or ("trapped_on_roof" in h and not h & NOT_WATER):
        required.add("boat")
    if h & COLLAPSE:
        required.add("heavy_lift")
    if h & FIRE:
        preferred.add("fire")
    if h & {"smoke_gas", "road_accident", "fire"} or "medical_urgent" in needs:
        preferred.add("medical")
    if "road_accident" in h:
        preferred.add("heavy_lift")   # cutting people out of a vehicle
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
        " (SELECT count(*) FROM assignments a WHERE a.team_id = t.id AND a.state IN ('open', 'overdue')) AS active,"
        " EXISTS (SELECT 1 FROM assignments a WHERE a.team_id = t.id AND a.state = 'reassigned'"
        "         AND a.standdown_acked_at IS NULL) AS standdown_owed"
        " FROM teams t WHERE t.incident_id = :i AND (CAST(:d AS bigint) IS NULL OR t.district_id = :d) ORDER BY t.id"),
        {"i": incident_id, "d": district_id}).all()


def rank(case: dict, teams: list, now: datetime | None = None) -> dict:
    """{suggestions: top_n [{team…, reasons, line}], more: the fit ones below top_n + the ones missing what this
    report needs, greyed: [{team, why}]} — pure over the rows given."""
    cfg = get_config().dispatch
    now = now or datetime.now(UTC)
    required, preferred = needed(case.get("hazards") or [], case.get("needs") or [])
    preferred = preferred | helpful(case.get("hazards"), case.get("needs"))   # catalog: a better fit, never a requirement
    excluded = set(cfg.get("exclude_team_status", ["overdue", "out_of_service"]))
    fit, unfit, greyed = [], [], []
    for t in teams:
        if t.status in excluded:
            why = t.status_reason or {"overdue": "contact overdue: greyed until heard from",
                                      "out_of_service": "out of service"}.get(t.status, t.status)
            greyed.append({"team_id": t.id, "name": t.name, "why": why})
            continue
        if getattr(t, "standdown_owed", False):   # it went quiet and a case was moved off it: not heard from since
            greyed.append({"team_id": t.id, "name": t.name, "why": "stand-down not acknowledged: greyed until heard from"})
            continue
        if t.active >= t.max_active:
            greyed.append({"team_id": t.id, "name": t.name, "why": f"at capacity ({t.active} of {t.max_active})"})
            continue
        caps = set(t.capabilities or [])
        if getattr(t, "agency", None) in FIRE_AGENCIES:
            caps.add("fire")
        missing = required - caps
        # Lead with what THIS report needs: a road accident with an urgent medical need reads "medical" first,
        # not "boat" (capabilities were sorted alphabetically once — every line shouted boat).
        first = sorted(required & caps)
        cover = sorted((preferred & caps) - required)
        ordered = first + cover + sorted(caps - required - preferred)
        if first:
            why = f"has {', '.join(first)} for this report"
        elif cover:
            why = f"{', '.join(cover)} cover for this report"
        else:
            why = "closest available unit"
        dist = (_km(case["lat"], case["lng"], t.lat, t.lng)
                if case.get("lat") is not None and t.lat is not None else None)
        age = (now - t.last_geom_at).total_seconds() / 60 if t.last_geom_at else None
        parts = [why, f"{dist:.1f} km straight-line" if dist is not None else "distance unknown (no pin)"]
        if age is not None:
            parts.append(f"position {_age(age)} old")
        parts.append(", ".join(ordered) or "no listed equipment")
        parts.append(f"{t.active} active")
        if missing:
            parts.append(f"no {', '.join(sorted(missing))} for this report")
        if not t.has_app:
            parts.append(f"radio only ({t.radio_channel or 'radio'})")
        row = {"team_id": t.id, "name": t.name, "agency": t.agency, "capabilities": ordered,
               "has_app": t.has_app, "distance_km": None if dist is None else round(dist, 1),
               "position_age_min": None if age is None else int(age), "active": t.active,
               "max_active": t.max_active, "missing": sorted(missing), "line": " · ".join(parts),
               "_key": (-len(preferred & caps), dist if dist is not None else 1e9, t.active, t.id)}   # more of what helps first, then nearest
        (unfit if missing else fit).append(row)
    fit.sort(key=lambda r: r.pop("_key"))
    unfit.sort(key=lambda r: r.pop("_key"))
    for i, r in enumerate(fit, start=1):
        r["rank"] = i
    top = cfg.get("top_n", 3)
    return {"suggestions": fit[:top], "more": fit[top:] + unfit, "greyed": greyed}
