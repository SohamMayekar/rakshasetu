"""What the `ticker` process does every 5 s (PRD F-S2). Timers live in the database, so a restart loses
nothing; every change is one conditional UPDATE, so two tickers (or a ticker and an officer) can't both act.

1. Check-ins past their deadline: the assignment becomes `overdue` (one UPDATE … WHERE state = 'open' AND
   next_contact_due < now()). THE CASE STAYS WITH THE TEAM: boat teams lose network for hours while still
   working, and an automatic reassign sends two boats to one roof. The team turns overdue, so dispatch greys
   it out until it's heard from.
2. One escalation per TEAM, listing its cases, routed to the EOC Duty Officer role:
   "SDRF Boat 2 overdue · not heard from since 14:20 · 2 cases. Radio them; if they don't answer, send another team."
3. When P1s wait without an owner and no team has room: ONE capacity-gap header for the district, not one
   alarm per case: "P1 without owner · 41 · 0 boats free · ask SEOC for ≈ 6 boats". RakshaSetu never
   requisitions anyone; a person asks the SEOC.
4. An escalation nobody acknowledges within `ack_within` rises to the EOC In-charge.
5. An escalation whose cause is gone (the team was heard from; P1s got owners) resolves itself.
6. A rescued case closes after its review window unless something blocks it (PRD F-S3).
Heartbeats are never read here: "last seen" can't extend a deadline.
"""

import math

from sqlalchemy import Connection, Engine, text

from app.config import get_config, parse_duration
from app.core.clock import hhmm
from app.core.eventlog import SYSTEM, append_event
from app.modules.assignments.service import _team_status
from app.modules.rescues.service import close_reviewed


def tick(engine: Engine) -> dict:
    with engine.begin() as conn:
        # One ticker at a time (a second container or a test calling tick() just skips this round).
        if not conn.execute(text("SELECT pg_try_advisory_xact_lock(hashtext('ticker'))")).scalar():
            return {"skipped": True}
        overdue = mark_overdue(conn)
        teams = escalate_teams(conn)
        gaps = capacity_gaps(conn)
        risen = rise(conn)
        closed = close_reviewed(conn)
        return {"overdue": overdue, "team_escalations": teams, "capacity_gaps": gaps, "risen": risen, "closed": closed}


def mark_overdue(conn: Connection) -> int:
    rows = conn.execute(text(
        "UPDATE assignments a SET state = 'overdue' FROM cases c, teams t"
        " WHERE a.state = 'open' AND a.next_contact_due < now() AND c.id = a.case_id AND t.id = a.team_id"
        " RETURNING a.id, a.case_id, a.team_id, a.next_contact_due, c.incident_id, c.district_id, t.name AS team")).all()
    for r in rows:
        append_event(conn, actor=SYSTEM, action="assignment.overdue", entity_type="assignment", entity_id=r.id,
                     incident_id=r.incident_id, district_id=r.district_id, case_id=r.case_id, team_id=r.team_id,
                     data={"assignment_id": r.id, "team": r.team, "due_was": r.next_contact_due.isoformat()})
    for team_id in {r.team_id for r in rows}:
        _team_status(conn, team_id)
    return len(rows)


def _team_line(team: str, n: int, since) -> str:
    when = f"not heard from since {hhmm(since)}" if since else "not heard from yet"
    return f"{team} overdue · {when} · {n} {'case' if n == 1 else 'cases'}. Radio them; if they don't answer, send another team."


def escalate_teams(conn: Connection) -> int:
    """Open (or update) one escalation per overdue team; resolve those whose team is no longer overdue."""
    changed = 0
    teams = conn.execute(text(
        "SELECT t.id, t.name, t.incident_id, t.district_id, coalesce(t.last_contact_at, min(a.created_at)) AS since,"
        " array_agg(a.case_id ORDER BY a.case_id) AS case_ids FROM teams t JOIN assignments a ON a.team_id = t.id"
        " WHERE a.state = 'overdue' GROUP BY t.id")).all()
    for t in teams:
        line = _team_line(t.name, len(t.case_ids), t.since)
        open_ = conn.execute(text("SELECT id, case_ids FROM escalations WHERE kind = 'team_overdue' AND team_id = :t"
                                  " AND status <> 'resolved'"), {"t": t.id}).one_or_none()
        if open_ is None:
            eid = conn.execute(text(
                "INSERT INTO escalations (incident_id, district_id, kind, team_id, case_ids, line)"
                " VALUES (:i, :d, 'team_overdue', :t, :c, :l) RETURNING id"),
                {"i": t.incident_id, "d": t.district_id, "t": t.id, "c": list(t.case_ids), "l": line}).scalar_one()
            append_event(conn, actor=SYSTEM, action="escalation.raised", entity_type="escalation", entity_id=eid,
                         incident_id=t.incident_id, district_id=t.district_id, team_id=t.id,
                         data={"escalation_id": eid, "kind": "team_overdue", "team": t.name, "case_ids": list(t.case_ids),
                               "line": line, "level": 1, "role": "duty_officer"})
            changed += 1
        elif list(open_.case_ids) != list(t.case_ids):
            conn.execute(text("UPDATE escalations SET case_ids = :c, line = :l WHERE id = :e"),
                         {"c": list(t.case_ids), "l": line, "e": open_.id})
    still = [t.id for t in teams]
    for e in conn.execute(text(
            "UPDATE escalations SET status = 'resolved', resolved_at = now(), resolution = 'the team was heard from'"
            " WHERE kind = 'team_overdue' AND status <> 'resolved' AND NOT (team_id = ANY(:still))"
            " RETURNING id, incident_id, district_id, team_id"), {"still": still}).all():
        append_event(conn, actor=SYSTEM, action="escalation.resolved", entity_type="escalation", entity_id=e.id,
                     incident_id=e.incident_id, district_id=e.district_id, team_id=e.team_id,
                     data={"escalation_id": e.id, "resolution": "the team was heard from"})
        changed += 1
    return changed


def capacity_gaps(conn: Connection) -> int:
    """One header per district when P1s wait past the threshold and no team has room."""
    after = parse_duration(get_config().escalation.get("p1_unowned_after", "5m")).total_seconds()
    rows = conn.execute(text(
        "SELECT c.incident_id, c.district_id, count(*) AS waiting, array_agg(c.id ORDER BY c.id) AS case_ids,"
        " (SELECT count(*) FROM teams t WHERE t.district_id = c.district_id AND t.status IN ('available', 'assigned')"
        "   AND (SELECT count(*) FROM assignments a WHERE a.team_id = t.id AND a.state IN ('open', 'overdue')) < t.max_active) AS free"
        " FROM cases c WHERE c.priority = 'P1' AND c.status IN ('reported', 'checked') AND c.geom IS NOT NULL"
        " AND c.queue_since < now() - make_interval(secs => :after)"
        " AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.case_id = c.id AND a.state IN ('open', 'overdue'))"
        " GROUP BY c.incident_id, c.district_id"), {"after": after}).all()
    changed, gapped = 0, []
    for r in rows:
        if r.free > 0:
            continue
        gapped.append(r.district_id)
        line = (f"Urgent families without a team · {r.waiting} · 0 teams free · ask the state control room for"
                f" ≈ {math.ceil(r.waiting / 2)} boats (assuming 2 cases a boat)")
        cur = conn.execute(text("SELECT id FROM escalations WHERE kind = 'capacity_gap' AND district_id = :d"
                                " AND status <> 'resolved'"), {"d": r.district_id}).scalar()
        if cur is None:
            eid = conn.execute(text("INSERT INTO escalations (incident_id, district_id, kind, case_ids, line)"
                                    " VALUES (:i, :d, 'capacity_gap', :c, :l) RETURNING id"),
                               {"i": r.incident_id, "d": r.district_id, "c": list(r.case_ids), "l": line}).scalar_one()
            append_event(conn, actor=SYSTEM, action="escalation.raised", entity_type="escalation", entity_id=eid,
                         incident_id=r.incident_id, district_id=r.district_id,
                         data={"escalation_id": eid, "kind": "capacity_gap", "case_ids": list(r.case_ids), "line": line,
                               "level": 1, "role": "duty_officer"})
            changed += 1
        else:
            conn.execute(text("UPDATE escalations SET case_ids = :c, line = :l WHERE id = :e"),
                         {"c": list(r.case_ids), "l": line, "e": cur})
    for e in conn.execute(text(
            "UPDATE escalations SET status = 'resolved', resolved_at = now(), resolution = 'teams free or P1s owned'"
            " WHERE kind = 'capacity_gap' AND status <> 'resolved' AND NOT (district_id = ANY(:g))"
            " RETURNING id, incident_id, district_id"), {"g": gapped}).all():
        append_event(conn, actor=SYSTEM, action="escalation.resolved", entity_type="escalation", entity_id=e.id,
                     incident_id=e.incident_id, district_id=e.district_id,
                     data={"escalation_id": e.id, "resolution": "teams free or P1s owned"})
        changed += 1
    return changed


def rise(conn: Connection) -> int:
    """An open escalation nobody acknowledged within ack_within rises one level (Duty Officer → In-charge)."""
    cfg = get_config().escalation
    chain = cfg.get("chain", ["duty_officer", "incharge"])
    ack_s = parse_duration(cfg.get("ack_within", "10m")).total_seconds()
    rows = conn.execute(text(
        "UPDATE escalations SET level = level + 1, role = :next WHERE status = 'open' AND level < :top"
        " AND opened_at < now() - make_interval(secs => :ack * level)"
        " RETURNING id, incident_id, district_id, team_id, line, level"),
        {"next": chain[-1], "top": len(chain), "ack": ack_s}).all()
    for r in rows:
        append_event(conn, actor=SYSTEM, action="escalation.raised", entity_type="escalation", entity_id=r.id,
                     incident_id=r.incident_id, district_id=r.district_id, team_id=r.team_id,
                     data={"escalation_id": r.id, "line": r.line, "level": r.level, "role": chain[r.level - 1],
                           "why": "not acknowledged in time"})
    return len(rows)
