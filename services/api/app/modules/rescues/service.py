"""Rescue records (PRD F-S3): the family is never asked to remember, type or show anything. The rescuers record
what happened; their phone's location at that moment is kept (the team's, not the victim's).

    nobody left                      → rescued; closes after the review window unless someone disputes it
    someone still there / don't know with fewer taken than reported
                                     → PARTIAL: the case stays open for the rest, keeps its priority, and goes back
                                       to the queue with its ORIGINAL waiting time ("2 of 6 still there")
    nobody here                      → back to the queue as P1 ("search the circle", then ask for a new place)
    couldn't reach (why)             → stays open, keeps its priority, and the next team sees why
    other: tell officer              → an officer task; every automated family message is suppressed
One record per assignment: an officer's radio record and the team's later app sync make one record plus a
corroboration, never two rescues.
"""

import json
import math

from sqlalchemy import Connection, text

from app.config import get_config
from app.core.eventlog import Actor, append_event
from app.modules.assignments.service import _team_status
from app.modules.cases.service import Conflict, NotAllowed

REASONS = {"water_current": "water or current", "road_bridge": "road or bridge", "night": "night", "other": "other"}


def _metres(lat1, lng1, lat2, lng2) -> float:
    dy = (lat1 - lat2) * 111_320
    dx = (lng1 - lng2) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def classify(reported: int | None, taken: int | None, anyone_left: str | None, outcome: str | None) -> str:
    if outcome in ("nobody_here", "couldnt_reach", "other"):
        return outcome
    if anyone_left == "yes":
        return "partial"
    if anyone_left == "dont_know" and reported and taken is not None and taken < reported:
        return "partial"
    return "rescued"


def record(conn: Connection, scope, actor: Actor, case_ref: str, *, people_taken: int | None, anyone_left: str | None,
           outcome: str | None, reason: str | None, channel: str, happened_at, lat: float | None, lng: float | None) -> dict:
    # A team lead may record for the case its team held last, even once that assignment has ended: the app's
    # later sync of a trip an officer already logged by radio must still land (as corroboration).
    where, params = (("c.id IN (SELECT a.case_id FROM assignments a WHERE a.team_id = :scope_team)", {"scope_team": scope.team_id})
                     if scope.role == "team_lead" else scope.case_where("c"))
    key = "c.id = :ref_id" if case_ref.isdigit() else "c.public_id = :ref"
    case = conn.execute(text(
        f"SELECT c.*, ST_Y(c.geom::geometry) AS clat, ST_X(c.geom::geometry) AS clng FROM cases c WHERE {key} AND {where}"
        f" FOR UPDATE"), {**params, "ref": case_ref, "ref_id": int(case_ref) if case_ref.isdigit() else None}).one_or_none()
    if case is None:
        raise LookupError(case_ref)
    a = conn.execute(text("SELECT a.*, t.name AS team FROM assignments a JOIN teams t ON t.id = a.team_id"
                          " WHERE a.case_id = :c ORDER BY (a.state IN ('open', 'overdue')) DESC, a.id DESC LIMIT 1"),
                     {"c": case.id}).one_or_none()
    if a is None:
        raise NotAllowed("No team was assigned to this case")
    if scope.role == "team_lead" and scope.team_id != a.team_id:
        raise PermissionError("This case isn't your team's")
    if scope.role != "team_lead" and channel == "app":
        raise NotAllowed("An officer records a rescue on the team's behalf: say the channel it came on (VHF, HAM, satellite, phone)")
    if outcome == "couldnt_reach" and reason not in REASONS:
        raise NotAllowed(f"Why couldn't you reach them? {', '.join(REASONS)}")
    if outcome == "other" and not (reason and len(reason.strip()) >= 3):
        raise NotAllowed("Tell the officer what happened")
    if people_taken is not None and people_taken < 0:
        raise NotAllowed("People taken can't be negative")

    first = conn.execute(text("SELECT id, outcome, people_taken FROM rescues WHERE assignment_id = :a AND corroborates IS NULL"),
                         {"a": a.id}).one_or_none()
    kind = classify(case.people_count, people_taken, anyone_left, outcome)
    away = False
    if lat is not None and lng is not None and case.clat is not None:
        away = _metres(lat, lng, case.clat, case.clng) > (case.radius_m or 0) + get_config().rescue.get("location_check_extra_m", 1000)
    rid = conn.execute(text(
        "INSERT INTO rescues (case_id, assignment_id, team_id, recorded_by, channel, outcome, people_taken, anyone_left,"
        " reason, happened_at, geom, away_from_pin, corroborates) VALUES (:c, :a, :t, :by, :ch, :o, :n, :left, :why, :at,"
        " CASE WHEN CAST(:lat AS float8) IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(CAST(:lng AS float8),"
        " CAST(:lat AS float8)), 4326)::geography END, :away, :corr) RETURNING id"),
        {"c": case.id, "a": a.id, "t": a.team_id, "by": scope.user_id, "ch": channel, "o": kind, "n": people_taken,
         "left": anyone_left, "why": reason, "at": happened_at, "lat": lat, "lng": lng, "away": away,
         "corr": first.id if first else None}).scalar_one()
    if first is not None:   # a second record of the same trip: corroboration, never a second rescue
        append_event(conn, actor=actor, action="rescue.corroborated", entity_type="rescue", entity_id=rid,
                     incident_id=case.incident_id, district_id=case.district_id, case_id=case.id, team_id=a.team_id,
                     data={"rescue_id": rid, "corroborates": first.id, "channel": channel, "people_taken": people_taken,
                           "agrees": first.people_taken == people_taken})
        return {"rescue_id": rid, "corroborates": first.id, "outcome": first.outcome}
    if a.state not in ("open", "overdue"):
        raise Conflict(f"This assignment was already {a.state}")

    conn.execute(text("UPDATE assignments SET state = 'completed', ended_at = now(), end_reason = :r WHERE id = :a"),
                 {"r": kind, "a": a.id})
    _team_status(conn, a.team_id)
    conn.execute(text("UPDATE teams SET last_contact_at = now() WHERE id = :t"), {"t": a.team_id})
    remaining = None
    flags = [f for f in (case.flags or []) if f not in ("partial_rescue", "nobody_here", "couldnt_reach", "other_tell_officer")]
    if kind == "rescued":
        status, remaining = "rescued", 0
        if away:
            flags.append("recorded_away_from_pin")
    elif kind == "partial":
        status = "checked" if case.checked_at else "reported"
        remaining = (case.people_count - people_taken) if (case.people_count and people_taken is not None
                                                           and anyone_left != "dont_know") else None
        flags.append("partial_rescue")
    elif kind == "nobody_here":
        status = "checked" if case.checked_at else "reported"
        flags.append("nobody_here")
    elif kind == "couldnt_reach":
        status = "checked" if case.checked_at else "reported"
        flags.append("couldnt_reach")
    else:
        status = "checked" if case.checked_at else "reported"
        flags.append("other_tell_officer")
    priority = "P1" if kind == "nobody_here" else case.priority          # partial / couldn't reach keep their priority
    attrs_patch = {"last_rescue": {"rescue_id": rid, "outcome": kind, "team": a.team, "people_taken": people_taken,
                                   "anyone_left": anyone_left, "reason": REASONS.get(reason, reason) if reason else None,
                                   "channel": channel, "away_from_pin": away}}
    conn.execute(text(
        "UPDATE cases SET status = :s, priority = :p, people_remaining = coalesce(CAST(:rem AS integer), people_remaining),"
        " flags = :f, rescued_at = CASE WHEN :s = 'rescued' THEN now() ELSE rescued_at END,"
        " attributes = attributes || CAST(:attrs AS jsonb), version = version + 1, updated_at = now() WHERE id = :c"),
        {"s": status, "p": priority, "rem": remaining, "f": flags, "attrs": json.dumps(attrs_patch), "c": case.id})
    action = {"rescued": "rescue.recorded", "partial": "rescue.partial"}.get(kind, f"rescue.{kind}")
    append_event(conn, actor=actor, action=action, entity_type="rescue", entity_id=rid, incident_id=case.incident_id,
                 district_id=case.district_id, case_id=case.id, team_id=a.team_id,
                 data={"rescue_id": rid, "team": a.team, "outcome": kind, "people_taken": people_taken,
                       "people_reported": case.people_count, "anyone_left": anyone_left, "remaining": remaining,
                       "reason": REASONS.get(reason, reason) if reason else None, "channel": channel,
                       "away_from_pin": away, "suppress_family_messages": kind == "other",
                       "happened_at": happened_at.isoformat() if happened_at else None})
    return {"rescue_id": rid, "outcome": kind, "status": status, "remaining": remaining, "away_from_pin": away}


BLOCKING = ("disputed", "recorded_away_from_pin", "other_tell_officer")


def close_reviewed(conn: Connection) -> int:
    """The ticker's job: a rescued case closes after its review window, unless something blocks it (a dispute,
    a record made away from the pin, an officer task). Silence from the family never blocks a closure."""
    from app.config import parse_duration
    from app.core.clock import hhmm
    from app.core.eventlog import SYSTEM
    contact = get_config().contact
    real = parse_duration(contact.rescue_review_window).total_seconds()
    demo = parse_duration(contact.demo_rescue_review_window).total_seconds()
    rows = conn.execute(text(
        "SELECT c.id, c.public_id, c.incident_id, c.district_id, c.people_count, c.flags, c.rescued_at, r.people_taken,"
        " t.name AS team, a.demo_clock FROM cases c JOIN rescues r ON r.case_id = c.id AND r.corroborates IS NULL"
        " AND r.outcome = 'rescued' JOIN assignments a ON a.id = r.assignment_id JOIN teams t ON t.id = r.team_id"
        " WHERE c.status = 'rescued' AND NOT (c.flags && CAST(:blocking AS text[]))"
        " AND c.rescued_at < now() - make_interval(secs => CASE WHEN a.demo_clock THEN :demo ELSE :real END)"
        " FOR UPDATE OF c"), {"blocking": list(BLOCKING), "demo": demo, "real": real}).all()
    for r in rows:
        line = (f"Rescued {r.people_taken} of {r.people_count or r.people_taken} · {r.team} · {hhmm(r.rescued_at)}"
                + (" · confirmed by family" if "family_confirmed" in (r.flags or []) else ""))
        conn.execute(text("UPDATE cases SET status = 'closed', resolution = :l, version = version + 1, updated_at = now()"
                          " WHERE id = :c"), {"l": line, "c": r.id})
        append_event(conn, actor=SYSTEM, action="case.closed", entity_type="case", entity_id=r.id,
                     incident_id=r.incident_id, district_id=r.district_id, case_id=r.id,
                     data={"resolution": line, "why": "the review window passed with nothing blocking it"})
    return len(rows)
