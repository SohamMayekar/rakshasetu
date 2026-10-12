""""Needs you now" (PRD F-C2): the desk shows only what needs a person; healthy cases leave the screen.

A case is an ATTENTION row when it has no live owner, its owner's contact is overdue, it is disputed or reopened,
it needs a location, it may be a duplicate, or it is a P1 nobody has checked. Everything else is "On it",
"rescued, closing" or "closed", shown only as counts.

ONE ordering rule: priority first; within a priority, broken promises before new work; then the P1 order
(rules' p1_rank: infant or urgent medical → water rising → vulnerable → time waiting); then the longest wait.
Each row carries at most ONE chip (ranked) and ONE suggested action, chosen for the viewer's role.
"""

from datetime import UTC, datetime

from sqlalchemy import Connection, text

from app.config import get_config, parse_duration
from app.core.auth import Scope

OPEN = ("reported", "checked", "assigned", "acknowledged", "reached")
PRIORITY_RANK = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}


def _mmss(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60}:{s % 60:02d}" if s < 3600 else f"{s // 3600} h {s % 3600 // 60} min"


def _minutes(seconds: float) -> str:
    m = int(seconds // 60)
    return f"{m} min" if m < 120 else f"{m // 60} h {m % 60} min"


def classify(c, now: datetime, unowned_after_s: float) -> dict:
    """What, if anything, this case needs from a person. Pure: everything comes from the row."""
    owned = c.assignment_state in ("open", "overdue")
    overdue_s = (now - c.next_contact_due).total_seconds() if owned and c.next_contact_due else 0
    overdue = owned and (c.assignment_state == "overdue" or overdue_s > 0)
    waited_s = (now - c.queue_since).total_seconds()
    flags = set(c.flags or [])
    p1_late = c.priority == "P1" and not owned and waited_s > unowned_after_s
    needs_location = "needs_location" in flags or c.lat is None
    duplicate = bool(c.open_match)
    unchecked = c.status == "reported"
    disputed, reopened = "disputed" in flags, "reopened" in flags
    reasons = []
    if overdue:
        reasons.append(("contact overdue " + _mmss(max(overdue_s, 0)), True))
    if disputed:
        reasons.append(("disputed", True))
    if reopened:
        reasons.append(("reopened", True))
    if p1_late:
        reasons.append((f"no owner {_minutes(waited_s)}", True))
    if needs_location:
        reasons.append(("needs location", False))
    if unchecked and c.priority == "P1":
        reasons.append(("unchecked P1", False))
    if duplicate:
        reasons.append(("possible duplicate", False))
    attention = bool(reasons) or not owned or unchecked
    return {"attention": attention, "broken": any(b for _, b in reasons), "chip": reasons[0][0] if reasons else None,
            "owned": owned, "overdue": overdue, "needs_location": needs_location, "duplicate": duplicate,
            "unchecked": unchecked, "waited_s": waited_s}


def action_for(c, k: dict, scope: Scope) -> dict:
    """The one suggested action, for this viewer's role. The desk renders it as the row's button."""
    can = scope.can
    if k["overdue"] and can("team.radio_contact"):
        return {"kind": "radio", "label": "Heard on radio"}
    if k["needs_location"] and can("case.move_pin"):
        return {"kind": "pin", "label": "Fix pin"}
    if k["duplicate"] and can("merge.decide"):
        return {"kind": "match", "label": f"Review match → {c.open_match}", "target": c.open_match}
    # Nobody on a roof waits for paperwork (dispatch.p1_before_check): an officer assigns an unchecked P1 first.
    if (c.priority == "P1" and not k["owned"] and can("assignment.create")
            and get_config().dispatch.get("p1_before_check", True)):
        return {"kind": "assign", "label": "Assign a team"}
    if k["unchecked"] and can("case.check"):
        return {"kind": "check", "label": "Check"}
    if not k["owned"] and can("assignment.create"):
        return {"kind": "assign", "label": "Assign a team"}
    return {"kind": "open", "label": "Open"}


def queue(conn: Connection, scope: Scope, incident_code: str) -> dict:
    where, params = scope.case_where("c")
    rows = conn.execute(text(f"""
        SELECT c.id, c.public_id, c.status, c.priority, c.priority_reasons, c.p1_rank, c.summary, c.location_text,
               c.location_confidence, ST_Y(c.geom::geometry) AS lat, c.flags, c.queue_since, c.people_count,
               c.version, a.state AS assignment_state, a.next_contact_due, a.phase, t.name AS team,
               (SELECT k.public_id FROM merge_suggestions s JOIN cases k ON k.id = s.candidate_case_id
                 WHERE s.case_id = c.id AND s.status = 'open' AND s.strength <> 'refused'
                 ORDER BY s.score DESC LIMIT 1) AS open_match
          FROM cases c JOIN incidents i ON i.id = c.incident_id
          LEFT JOIN assignments a ON a.case_id = c.id AND a.state IN ('open', 'overdue')
          LEFT JOIN teams t ON t.id = a.team_id
         WHERE i.code = :code AND c.status IN {OPEN} AND {where}"""), {**params, "code": incident_code}).all()
    counts = conn.execute(text(f"""
        SELECT count(*) FILTER (WHERE c.status = 'rescued') AS rescued_closing,
               count(*) FILTER (WHERE c.status = 'closed') AS closed
          FROM cases c JOIN incidents i ON i.id = c.incident_id WHERE i.code = :code AND {where}"""),
        {**params, "code": incident_code}).one()
    now = datetime.now(UTC)
    unowned_after = parse_duration(get_config().escalation.get("p1_unowned_after", "5m")).total_seconds()
    out, on_it = [], 0
    for c in rows:
        k = classify(c, now, unowned_after)
        if not k["attention"]:
            on_it += 1
            continue
        where_line = c.location_text or "no location yet"
        owner = f" · {c.team}" if k["owned"] else ""
        out.append({
            "id": c.id, "public_id": c.public_id, "priority": c.priority, "status": c.status, "version": c.version,
            "line1": c.summary, "line2": f"{where_line}{owner} · waiting {_minutes(k['waited_s'])}",
            "because": " · ".join(c.priority_reasons or []), "chip": k["chip"], "broken": k["broken"],
            "action": action_for(c, k, scope),
            "sort": [PRIORITY_RANK[c.priority], 0 if k["broken"] else 1,
                     (c.p1_rank or 0) if c.priority == "P1" else 0, c.queue_since.isoformat()],
        })
    out.sort(key=lambda r: r["sort"])
    return {"rows": out, "on_it": on_it, "rescued_closing": counts.rescued_closing, "closed": counts.closed,
            "open": len(rows)}
