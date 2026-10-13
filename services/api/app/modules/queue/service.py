""""Needs you now" (PRD F-C2): the desk shows only what needs a person; healthy cases leave the screen.

A case is an ATTENTION row when it has no live owner, its owner's contact is overdue, it is disputed or reopened,
it needs a location, it may be a duplicate, or it is a P1 nobody has checked. Everything else is "On it",
"rescued, closing" or "closed", shown only as counts.

ONE ordering rule: priority first; within a priority, broken promises before new work; then the P1 order
(rules' p1_rank: infant or urgent medical → water rising → vulnerable → time waiting); then the longest wait.
Each row carries at most ONE chip (ranked) and ONE suggested action, chosen for the viewer's role.

A spreadsheet's new cases that only wait for a team (no other reason) arrive as ONE row per import, "188 new
cases from relief.csv need a team (34 P1)", opening the list; its to-check rows (a likely duplicate, no place,
an old report, "done" in the sheet but matched an open case) come in one by one (PRD F-D3 step 7, D13).
"""

from datetime import UTC, datetime

from sqlalchemy import Connection, text

from app.config import get_config, parse_duration
from app.core.auth import Scope
from app.modules.dispatch.service import rank, teams_for

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
    unchecked = c.checked_at is None      # the check outlives the status: an owned P1 can still be unchecked
    disputed, reopened = "disputed" in flags, "reopened" in flags
    reasons = []
    if overdue:
        reasons.append(("contact overdue " + _mmss(max(overdue_s, 0)), True))
    if disputed:
        reasons.append(("disputed: radio the team", True))
    if reopened:
        reasons.append(("reopened", True))
    if "other_tell_officer" in flags:
        reasons.append(("tell officer", True))
    if "partial_rescue" in flags and not owned:
        left = f"{c.people_remaining} of {c.people_count}" if c.people_remaining is not None and c.people_count else "some"
        reasons.append((f"{left} still there", True))
    if "nobody_here" in flags and not owned:
        reasons.append(("nobody here: search", True))
    if "couldnt_reach" in flags and not owned:
        reasons.append(("couldn't reach", True))
    if p1_late:
        reasons.append((f"no owner {_minutes(waited_s)}", True))
    if needs_location:
        reasons.append(("needs location", False))
    if "old_report" in flags:
        reasons.append(("old report: confirm", False))
    if "sheet_says_done" in flags:
        reasons.append(("sheet says done", False))
    if unchecked and c.priority == "P1":
        reasons.append(("unchecked P1", False))
    if duplicate:
        reasons.append(("possible duplicate", False))
    attention = bool(reasons) or (not owned and c.status != "rescued") or unchecked
    # "Waiting for a team" only: nothing about it needs a person except assigning (and checking) it.
    only_waiting = attention and all(r.startswith("no owner") or r == "unchecked P1" for r, _ in reasons)
    return {"attention": attention, "broken": any(b for _, b in reasons), "chip": reasons[0][0] if reasons else None,
            "only_waiting": only_waiting,
            "owned": owned, "overdue": overdue, "needs_location": needs_location, "duplicate": duplicate,
            "unchecked": unchecked, "waited_s": waited_s}


def _assign(k: dict) -> dict:
    """"Assign → SDRF Boat 2 · 2.1 km · boat": the top dispatch suggestion as the row's button."""
    best = k.get("best_team")
    if not best:
        return {"kind": "assign", "label": "Assign a team"}
    where = f"{best['distance_km']} km" if best["distance_km"] is not None else "no pin"
    kit = ", ".join(best["capabilities"][:2]) or best["agency"]
    label = f"Assign → {best['name']} · {where} · {kit}"
    if len(label) > 46:   # a long team name: keep the name and the distance
        label = f"Assign → {best['name']} · {where}"
    return {"kind": "assign", "label": label, "target": str(best["team_id"])}


def action_for(c, k: dict, scope: Scope) -> dict:
    """The one suggested action, for this viewer's role. The desk renders it as the row's button."""
    can = scope.can
    if "disputed" in (c.flags or []):
        return {"kind": "open", "label": "Radio the team, then decide"}
    if k["overdue"] and can("team.radio_contact"):
        return {"kind": "radio", "label": "Heard on radio"}
    if k["needs_location"] and can("case.move_pin"):
        return {"kind": "pin", "label": "Fix pin"}
    if k["duplicate"] and can("merge.decide"):
        return {"kind": "match", "label": f"Review match → {c.open_match}", "target": c.open_match}
    # Nobody on a roof waits for paperwork (dispatch.p1_before_check): an officer assigns an unchecked P1 first.
    if (c.priority == "P1" and not k["owned"] and can("assignment.create")
            and get_config().dispatch.get("p1_before_check", True)):
        return _assign(k)
    if k["unchecked"] and can("case.check"):
        return {"kind": "check", "label": "Check"}
    if not k["owned"] and can("assignment.create"):
        return _assign(k)
    return {"kind": "open", "label": "Open"}


def _because(c) -> str:
    """The rules' reasons, or a person's call with its reason and what the rules said (P1 #2)."""
    o = c.priority_override
    if o:
        way = "raised" if o["level"] < o["from"] else "lowered" if o["level"] != o["from"] else "kept"
        return f"{way} by {o['by']}: “{o['reason']}” · the rules said {o['rules_said']}"
    return " · ".join(c.priority_reasons or [])


def queue(conn: Connection, scope: Scope, incident_code: str) -> dict:
    where, params = scope.case_where("c")
    rows = conn.execute(text(f"""
        SELECT c.id, c.public_id, c.status, c.priority, c.priority_reasons, c.priority_override, c.p1_rank, c.summary, c.location_text,
               c.location_confidence, ST_Y(c.geom::geometry) AS lat, ST_X(c.geom::geometry) AS lng, c.flags,
               c.queue_since, c.people_count, c.people_remaining, c.hazards, c.needs, c.incident_id, c.district_id,
               c.checked_at, c.attributes,
               c.version, a.state AS assignment_state, a.next_contact_due, a.phase, t.name AS team,
               (SELECT k.public_id FROM merge_suggestions s JOIN cases k ON k.id = s.candidate_case_id
                 WHERE s.case_id = c.id AND s.status = 'open' AND s.strength <> 'refused'
                 ORDER BY s.score DESC LIMIT 1) AS open_match,
               (SELECT CASE WHEN bool_and(r.channel = 'spreadsheet') THEN min(r.source->>'ref') END
                  FROM reports r WHERE r.case_id = c.id) AS sheet_ref
          FROM cases c JOIN incidents i ON i.id = c.incident_id
          LEFT JOIN assignments a ON a.case_id = c.id AND a.state IN ('open', 'overdue')
          LEFT JOIN teams t ON t.id = a.team_id
         WHERE i.code = :code AND (c.status IN {OPEN} OR (c.status = 'rescued' AND 'disputed' = ANY(c.flags)))
           AND {where}"""), {**params, "code": incident_code}).all()
    counts = conn.execute(text(f"""
        SELECT count(*) FILTER (WHERE c.status = 'rescued') AS rescued_closing,
               count(*) FILTER (WHERE c.status = 'closed') AS closed
          FROM cases c JOIN incidents i ON i.id = c.incident_id WHERE i.code = :code AND {where}"""),
        {**params, "code": incident_code}).one()
    now = datetime.now(UTC)
    unowned_after = parse_duration(get_config().escalation.get("p1_unowned_after", "5m")).total_seconds()
    out, on_it, groups, teams = [], 0, {}, {}
    officer = scope.can("assignment.create")
    for c in rows:
        k = classify(c, now, unowned_after)
        if officer and k["attention"] and not k["owned"]:
            if c.district_id not in teams:
                teams[c.district_id] = teams_for(conn, c.incident_id, c.district_id)
            top = rank(dict(c._mapping), teams[c.district_id], now)["suggestions"]
            k["best_team"] = top[0] if top else None
        if not k["attention"]:
            on_it += 1
            continue
        if k["only_waiting"] and c.sheet_ref and c.sheet_ref.startswith("import:"):
            groups.setdefault(int(c.sheet_ref.split(":", 1)[1]), []).append((c, k))
            continue
        where_line = c.location_text or "no location yet"
        owner = f" · {c.team}" if k["owned"] else ""
        last = (c.attributes or {}).get("last_rescue") or {}
        if last.get("outcome") == "couldnt_reach" and not k["owned"]:
            owner = f" · {last.get('team')} couldn't reach ({last.get('reason')})"
        out.append({
            "id": c.id, "kind": "case", "public_id": c.public_id, "priority": c.priority, "status": c.status, "version": c.version,
            "line1": c.summary, "line2": f"{where_line}{owner} · waiting {_minutes(k['waited_s'])}",
            "because": _because(c), "chip": k["chip"], "broken": k["broken"],
            "owned": k["owned"], "needs_location": k["needs_location"], "checked": not k["unchecked"],
            "action": action_for(c, k, scope),
            "sort": [PRIORITY_RANK[c.priority], 0 if k["broken"] else 1,
                     (c.p1_rank or 0) if c.priority == "P1" else 0, c.queue_since.isoformat()],
        })
    out += _group_rows(conn, groups, now)
    out.sort(key=lambda r: r["sort"])
    return {"rows": out, "on_it": on_it, "rescued_closing": counts.rescued_closing, "closed": counts.closed,
            "open": len(rows)}


def _group_rows(conn: Connection, groups: dict, now: datetime) -> list[dict]:
    """One row per import for its cases that only wait for a team."""
    if not groups:
        return []
    names = {r.id: r.file_name for r in conn.execute(text("SELECT id, file_name FROM imports WHERE id = ANY(:ids)"),
                                                       {"ids": list(groups)})}
    out = []
    for iid, members in groups.items():
        by = {p: sum(1 for c, _ in members if c.priority == p) for p in PRIORITY_RANK}
        top = min((c.priority for c, _ in members), key=PRIORITY_RANK.get)
        broken = any(k["broken"] for _, k in members)
        oldest = min(c.queue_since for c, _ in members)
        n = len(members)
        out.append({
            "id": -iid, "kind": "group", "public_id": names.get(iid, f"import {iid}"), "priority": top, "status": "group",
            "version": 0, "members": [c.id for c, _ in members],
            "line1": f"{n} new {'case' if n == 1 else 'cases'} from this sheet need a team",
            "line2": " · ".join(f"{v} {p}" for p, v in by.items() if v) + f" · waiting {_minutes((now - oldest).total_seconds())}",
            "because": "rows the import created; each has its own priority and reasons", "broken": broken,
            "chip": f"{by['P1']} P1 without an owner" if broken and by["P1"] else None,
            "owned": False, "needs_location": False, "checked": True,
            "action": {"kind": "import", "label": "Open the list", "target": str(iid)},
            "sort": [PRIORITY_RANK[top], 0 if broken else 1, 0, oldest.isoformat()],
        })
    return out
