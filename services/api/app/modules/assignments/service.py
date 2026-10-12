"""Assignments with a check-in deadline (PRD F-S1; "lease" in code, "check-in due" on screen).

- An officer assigns a team: one live assignment per case, enforced by the database (rule R7); a second one
  gets a 409 naming who assigned whom, and when.
- Deadlines use the DATABASE clock (rule R6): acknowledge within (P1: 5 min) → after Acknowledge, ETA + grace →
  after Reached, the on-scene window (30 min, or 120 min for a long operation).
- Only DELIBERATE contact resets a deadline: a team action, or an officer's radio log. The app's "last seen"
  heartbeat is display only.
- The demo profile runs the clock ×60 for live demo cases only (cases made after the reset, in DEMO_MODE); seeded
  cases keep realistic timers, so nothing seeded escalates mid-pitch (PRD E22).
"""

from datetime import datetime

from sqlalchemy import Connection, text

from app.config import get_config, parse_duration
from app.core.clock import hhmmss
from app.core.eventlog import Actor, append_event
from app.modules.cases.service import Conflict, NotAllowed
from app.settings import get_settings

LIVE = ("open", "overdue")
CHANNELS = ("app", "VHF", "HAM", "satellite", "phone")


def seconds(key: str, priority: str | None = None) -> float:
    v = getattr(get_config().contact, key)
    if isinstance(v, dict):
        v = v[priority or "P4"]
    return parse_duration(v).total_seconds()


def is_demo_case(conn: Connection, case_id: int) -> bool:
    """Short timers only for live demo cases: DEMO_MODE, and the case wasn't loaded by the seed."""
    if not get_settings().demo_mode:
        return False
    return not conn.execute(text("SELECT EXISTS (SELECT 1 FROM reports WHERE case_id = :c AND source_ns = 'seed')"),
                            {"c": case_id}).scalar()


def _scaled(s: float, demo: bool) -> float:
    return s / get_config().contact.demo_clock_multiplier if demo else s


def _actor(scope) -> Actor:
    return Actor("user", str(scope.user_id), scope.role)


def _team_status(conn: Connection, team_id: int) -> None:
    """A team is overdue while any of its assignments is; assigned while it holds one; else available."""
    conn.execute(text(
        "UPDATE teams SET status = CASE"
        "   WHEN status = 'out_of_service' THEN status"
        "   WHEN EXISTS (SELECT 1 FROM assignments WHERE team_id = :t AND state = 'overdue') THEN 'overdue'"
        "   WHEN EXISTS (SELECT 1 FROM assignments WHERE team_id = :t AND state = 'open') THEN 'assigned'"
        "   ELSE 'available' END WHERE id = :t"), {"t": team_id})


def live_assignment(conn: Connection, case_id: int):
    return conn.execute(text(
        "SELECT a.*, t.name AS team, t.has_app FROM assignments a JOIN teams t ON t.id = a.team_id"
        " WHERE a.case_id = :c AND a.state IN ('open', 'overdue')"), {"c": case_id}).one_or_none()


def create(conn: Connection, *, case, team, actor: Actor, suggested_rank: int | None = None,
           phase: str = "offered", eta_minutes: int | None = None, due_s: float | None = None) -> dict:
    """Insert the assignment (the DB refuses a second live one) and move the case and team on."""
    existing = live_assignment(conn, case.id)
    if existing:
        who = conn.execute(text("SELECT coalesce(u.name, 'the system') FROM assignments a LEFT JOIN users u"
                                " ON u.id = a.assigned_by WHERE a.id = :a"), {"a": existing.id}).scalar()
        raise Conflict(f"Already assigned to {existing.team} by {who} at {hhmmss(existing.created_at)}")
    if team.district_id != case.district_id or team.incident_id != case.incident_id:
        raise NotAllowed("That team isn't deployed in this case's district")
    if team.status == "out_of_service":
        raise NotAllowed(f"{team.name} is out of service")
    demo = is_demo_case(conn, case.id)
    if due_s is None:
        due_s = _scaled(seconds("acknowledge_within", case.priority), demo)
    aid = conn.execute(text(
        "INSERT INTO assignments (case_id, team_id, assigned_by, suggested_rank, phase, eta_minutes, next_contact_due,"
        " demo_clock) VALUES (:c, :t, :by, :rank, :phase, :eta, now() + make_interval(secs => :due), :demo) RETURNING id"),
        {"c": case.id, "t": team.id, "by": int(actor.id) if actor.type == "user" else None, "rank": suggested_rank,
         "phase": phase, "eta": eta_minutes, "due": due_s, "demo": demo}).scalar_one()
    status = {"offered": "assigned", "acknowledged": "acknowledged", "reached": "reached"}[phase]
    conn.execute(text("UPDATE cases SET status = :s, version = version + 1, updated_at = now() WHERE id = :c"),
                 {"s": status, "c": case.id})
    _team_status(conn, team.id)
    due = conn.execute(text("SELECT next_contact_due FROM assignments WHERE id = :a"), {"a": aid}).scalar()
    append_event(conn, actor=actor, action="assignment.created", entity_type="assignment", entity_id=aid,
                 incident_id=case.incident_id, district_id=case.district_id, case_id=case.id, team_id=team.id,
                 data={"assignment_id": aid, "team": team.name, "team_id": team.id, "phase": phase,
                       "next_contact_due": due.isoformat(), "demo_clock": demo, "suggested_rank": suggested_rank})
    return {"assignment_id": aid, "team": team.name, "next_contact_due": due.isoformat(), "demo_clock": demo}


def lock_assignment(conn: Connection, assignment_id: int):
    return conn.execute(text(
        "SELECT a.*, t.name AS team, t.has_app, c.incident_id, c.district_id, c.priority, c.public_id, c.checked_at"
        " FROM assignments a JOIN teams t ON t.id = a.team_id JOIN cases c ON c.id = a.case_id"
        " WHERE a.id = :a FOR UPDATE OF a"), {"a": assignment_id}).one_or_none()


def act(conn: Connection, scope, assignment_id: int, action: str, *, eta_minutes: int | None = None,
        long_operation: bool = False, reason: str | None = None, channel: str | None = None,
        happened_at: datetime | None = None) -> dict:
    """A team's step (acknowledge · reached · release), by its team lead in the app, or by an officer on its
    behalf with the channel it was heard on. Every one is deliberate contact: it resets the deadline."""
    a = lock_assignment(conn, assignment_id)
    if a is None:
        raise LookupError(assignment_id)
    on_behalf = scope.role != "team_lead"
    if not on_behalf and scope.team_id != a.team_id:
        raise PermissionError("This assignment belongs to another team")
    if on_behalf:
        where, params = scope.case_where("c")
        if conn.execute(text(f"SELECT 1 FROM cases c WHERE c.id = :id AND {where}"), {**params, "id": a.case_id}).first() is None:
            raise LookupError(assignment_id)
        if channel not in CHANNELS or channel == "app":
            raise NotAllowed("Say how you heard from the team: VHF, HAM, satellite or phone")
    if a.state not in LIVE:
        raise Conflict(f"This assignment was already {a.state}")
    demo = a.demo_clock
    if action == "acknowledge":
        if eta_minutes not in (15, 30, 60):
            raise NotAllowed("Pick an ETA: 15, 30 or 60 minutes")
        due_s = _scaled(eta_minutes * 60 + seconds("eta_grace"), demo)
        phase, case_status = "acknowledged", "acknowledged"
    elif action == "reached":
        due_s = _scaled(seconds("long_operation_window" if long_operation else "onscene_window"), demo)
        phase, case_status = "reached", "reached"
    elif action == "release":
        if not reason or len(reason.strip()) < 3:
            raise NotAllowed("Say why the case is being released")
        conn.execute(text("UPDATE assignments SET state = 'released', ended_at = now(), end_reason = :r WHERE id = :a"),
                     {"r": reason, "a": a.id})
        conn.execute(text("UPDATE cases SET status = CASE WHEN checked_at IS NULL THEN 'reported' ELSE 'checked' END,"
                          " version = version + 1, updated_at = now() WHERE id = :c"), {"c": a.case_id})
        conn.execute(text("UPDATE teams SET last_contact_at = now() WHERE id = :t"), {"t": a.team_id})
        _team_status(conn, a.team_id)
        append_event(conn, actor=_actor(scope), action="assignment.released", entity_type="assignment", entity_id=a.id,
                     incident_id=a.incident_id, district_id=a.district_id, case_id=a.case_id, team_id=a.team_id,
                     reason=reason, data={"assignment_id": a.id, "team": a.team, "channel": channel or "app",
                                          "happened_at": happened_at.isoformat() if happened_at else None})
        return {"assignment_id": a.id, "state": "released"}
    else:
        raise NotAllowed(f"Unknown action {action}")
    conn.execute(text(
        "UPDATE assignments SET phase = :phase, state = 'open', eta_minutes = coalesce(:eta, eta_minutes),"
        " long_operation = long_operation OR :long, next_contact_due = now() + make_interval(secs => :due) WHERE id = :a"),
        {"phase": phase, "eta": eta_minutes, "long": long_operation, "due": due_s, "a": a.id})
    conn.execute(text("UPDATE cases SET status = :s, version = version + 1, updated_at = now() WHERE id = :c"),
                 {"s": case_status, "c": a.case_id})
    conn.execute(text("UPDATE teams SET last_contact_at = now() WHERE id = :t"), {"t": a.team_id})
    _team_status(conn, a.team_id)
    due = conn.execute(text("SELECT next_contact_due FROM assignments WHERE id = :a"), {"a": a.id}).scalar()
    append_event(conn, actor=_actor(scope), action=f"assignment.{'acknowledged' if action == 'acknowledge' else action}",
                 entity_type="assignment", entity_id=a.id, incident_id=a.incident_id, district_id=a.district_id,
                 case_id=a.case_id, team_id=a.team_id,
                 data={"assignment_id": a.id, "team": a.team, "phase": phase, "eta_minutes": eta_minutes,
                       "long_operation": long_operation, "next_contact_due": due.isoformat(), "channel": channel or "app",
                       "happened_at": happened_at.isoformat() if happened_at else None})
    return {"assignment_id": a.id, "phase": phase, "next_contact_due": due.isoformat()}
