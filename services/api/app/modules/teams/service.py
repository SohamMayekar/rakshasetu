"""Deliberate contact with a team (PRD F-S1, F-S2).

"Heard from SDRF Boat 2" is TEAM-LEVEL: one radio log refreshes every live assignment that team holds, clears
its overdue state, resolves its escalation, and acknowledges any stand-down it owed. It is logged with the
channel (VHF · HAM · satellite · phone) and an optional new ETA. This is the only way, besides a team's own
action in the app, that a check-in deadline moves; a heartbeat never does.
"""

from sqlalchemy import Connection, text

from app.core.eventlog import Actor, append_event
from app.modules.assignments.service import _scaled, _team_status, seconds
from app.modules.cases.service import NotAllowed

CHANNELS = ("VHF", "HAM", "satellite", "phone")


def heard_from(conn: Connection, *, team, actor: Actor, by: str, channel: str, new_eta: int | None = None,
               note: str | None = None) -> dict:
    if channel not in CHANNELS:
        raise NotAllowed(f"Say how you heard from them: {', '.join(CHANNELS)}")
    if new_eta is not None and new_eta not in (15, 30, 60):
        raise NotAllowed("A new ETA is 15, 30 or 60 minutes")
    live = conn.execute(text(
        "SELECT a.*, c.priority, c.incident_id, c.district_id FROM assignments a JOIN cases c ON c.id = a.case_id"
        " WHERE a.team_id = :t AND a.state IN ('open', 'overdue') FOR UPDATE OF a"), {"t": team.id}).all()
    refreshed = []
    for a in live:
        phase = a.phase
        if phase == "offered" and new_eta:      # they told us their ETA: that is an acknowledgement, by radio
            phase = "acknowledged"
        if phase == "offered":
            due = seconds("acknowledge_within", a.priority)
        elif phase == "acknowledged":
            due = (new_eta or a.eta_minutes or 30) * 60 + seconds("eta_grace")
        else:
            due = seconds("long_operation_window" if a.long_operation else "onscene_window")
        conn.execute(text("UPDATE assignments SET state = 'open', phase = :phase, eta_minutes = CASE WHEN :phase = 'acknowledged'"
                          " THEN coalesce(:eta, eta_minutes) ELSE eta_minutes END,"
                          " next_contact_due = now() + make_interval(secs => :due) WHERE id = :a"),
                     {"phase": phase, "eta": new_eta, "due": _scaled(due, a.demo_clock), "a": a.id})
        if phase != a.phase:
            conn.execute(text("UPDATE cases SET status = 'acknowledged', version = version + 1, updated_at = now()"
                              " WHERE id = :c AND status = 'assigned'"), {"c": a.case_id})
        append_event(conn, actor=actor, action="assignment.contact", entity_type="assignment", entity_id=a.id,
                     incident_id=a.incident_id, district_id=a.district_id, case_id=a.case_id, team_id=team.id,
                     data={"assignment_id": a.id, "team": team.name, "channel": channel, "new_eta": new_eta,
                           "was_overdue": a.state == "overdue", "by": by, "note": note})
        refreshed.append(a.case_id)
    standdowns = conn.execute(text(
        "UPDATE assignments SET standdown_acked_at = now() WHERE team_id = :t AND state = 'reassigned'"
        " AND standdown_acked_at IS NULL RETURNING id"), {"t": team.id}).all()
    conn.execute(text("UPDATE teams SET last_contact_at = now() WHERE id = :t"), {"t": team.id})
    _team_status(conn, team.id)
    resolution = f"heard on {channel} by {by}"
    for e in conn.execute(text(
            "UPDATE escalations SET status = 'resolved', resolved_at = now(), resolution = :r WHERE kind = 'team_overdue'"
            " AND team_id = :t AND status <> 'resolved' RETURNING id, incident_id, district_id"),
            {"r": resolution, "t": team.id}).all():
        append_event(conn, actor=actor, action="escalation.resolved", entity_type="escalation", entity_id=e.id,
                     incident_id=e.incident_id, district_id=e.district_id, team_id=team.id,
                     data={"escalation_id": e.id, "resolution": resolution})
    append_event(conn, actor=actor, action="team.contact", entity_type="team", entity_id=team.id,
                 incident_id=team.incident_id, district_id=team.district_id, team_id=team.id,
                 data={"team": team.name, "channel": channel, "new_eta": new_eta, "case_ids": refreshed,
                       "standdowns_acknowledged": len(standdowns), "by": by, "note": note})
    return {"team_id": team.id, "refreshed": len(refreshed), "case_ids": refreshed,
            "standdowns_acknowledged": len(standdowns)}
