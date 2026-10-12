"""A case's history and evidence for the drawer (PRD F-C2 "Timeline & evidence", F-C11).

Every line comes from a template over the event's own data (never from a model). Evidence items carry two hash
checks computed when asked: the stored file still hashes to its name, and that hash is the one the audit
chain recorded when the item was added (rule R16). A case shows the events of the cases folded into it too.
"""

import json

from sqlalchemy import Connection, text

from app.core.auth import Scope
from app.core.storage import rehash

LABEL = {"trapped_on_roof": "on the roof", "trapped_inside": "trapped inside", "water_entering": "water inside",
         "water_rising": "water rising", "medical_urgent": "urgent medical", "drinking_water": "drinking water",
         "baby_supplies": "baby milk", "people_count": "people"}


EVIDENCE = {"audio": "the voice clip", "transcript": "the transcript", "message": "the message as received",
            "sheet_row": "the spreadsheet row", "merge": "the merge record", "rescue": "the rescue record",
            "radio": "the radio log", "partner_annotation": "a partner's note"}


def _fmt(v) -> str:
    if isinstance(v, list):
        return ", ".join(LABEL.get(x, x) for x in v) or "none"
    return "?" if v is None else str(LABEL.get(v, v))


def line(action: str, d: dict, who: str | None) -> str:
    by = f" by {who}" if who else ""
    match action:
        case "report.received":
            return f"Report received ({d.get('channel', '?').replace('web_form', 'desk')})" + (" · a forward" if d.get("is_forward") else "")
        case "case.created":
            return f"Case {d.get('public_id', '')} created · {d.get('priority', '')}"
        case "case.checked":
            return f"Checked{by}"
        case "case.updated":
            if d.get("changed"):
                return "Facts corrected" + by + ": " + " · ".join(
                    f"{LABEL.get(k, k)} {_fmt(v.get('from'))} → {_fmt(v.get('to'))}" for k, v in d["changed"].items())
            return d.get("why") or "Case updated"
        case "case.priority_changed":
            return f"Priority {d.get('from')} → {d.get('to')}" + (f" · because {' · '.join(d['reasons'])}" if d.get("reasons") else "")
        case "case.location_moved":
            return f"Pin moved{by}"
        case "case.merged":
            return d.get("line") or f"{d.get('source')} folded into {d.get('target')}"
        case "case.absorbed":
            return f"Folded into {d.get('target')}"
        case "case.unmerged":
            return f"Merge undone{by}"
        case "merge.suggested" | "merge.refused":
            return d.get("line") or action
        case "merge.rejected":
            return f"Not the same household (decided{by})"
        case "evidence.added":
            kind = EVIDENCE.get(d.get("type"), str(d.get("type", "?")).replace("_", " "))
            return f"Evidence kept: {kind}" + (f" · sha256 {d['sha256'][:12]}…" if d.get("sha256") else "")
        case "assignment.created":
            return f"Assigned to {d.get('team')}{by}"
        case "assignment.acknowledged":
            via = f" · via {d['channel']}" if d.get("channel") not in (None, "app") else ""
            return f"{d.get('team')} acknowledged · ETA {d.get('eta_minutes')} min{via}{by if via else ''}"
        case "assignment.reached":
            via = f" · via {d['channel']}" if d.get("channel") not in (None, "app") else ""
            return f"{d.get('team')} reached the place" + (" · long operation" if d.get("long_operation") else "") + via
        case "assignment.contact":
            eta = f" · new ETA {d['new_eta']} min" if d.get("new_eta") else ""
            return f"Heard from {d.get('team')} on {d.get('channel')}{by}{eta}"
        case "assignment.reassigned":
            return f"Reassigned from {d.get('from_team')} to {d.get('to_team')}{by} (stand-down owed by {d.get('from_team')})"
        case "assignment.overdue":
            return f"Contact overdue: no check-in from {d.get('team')} (the case stays with the team)"
        case "assignment.released":
            return f"{d.get('team')} released the case{by}"
        case "rescue.recorded":
            via = f" · via {d['channel']}{by}" if d.get("channel") not in (None, "app") else ""
            took = (f"{d.get('people_taken')} more rescued, {d['total_taken']} of {d.get('people_reported') or '?'} in all"
                    if d.get("earlier_trips_taken") else f"{d.get('people_taken')} of {d.get('people_reported') or '?'} rescued")
            return (f"{d.get('team')}: {took}, nobody left"
                    + (" · recorded away from the pin" if d.get("away_from_pin") else "") + via)
        case "rescue.partial":
            left = f"{d['remaining']} still there" if d.get("remaining") is not None else "someone may still be there"
            return f"{d.get('team')}: took {d.get('people_taken')}, {left} · back to the queue with its original time"
        case "rescue.nobody_here":
            return f"{d.get('team')}: nobody here · back to the queue as P1 (search the circle, ask for a new place)"
        case "rescue.couldnt_reach":
            return f"{d.get('team')}: couldn't reach ({d.get('reason')}) · the next team will see why"
        case "rescue.other":
            return f"{d.get('team')}: other, tell the officer · family messages paused"
        case "rescue.corroborated":
            return f"The same trip confirmed again via {d.get('channel')}" + ("" if d.get("agrees") else " · the counts differ")
        case "case.closed":
            return f"Closed: {d.get('resolution')}" if d.get("resolution") else f"Closed{by}"
        case "case.cancelled":
            return f"Cancelled{by}"
        case "case.reopened":
            return f"Reopened{by}" if who else f"Reopened as P1: {d.get('by', 'the family')} says No"
        case "rescue.confirmed":
            return f"The family confirmed: {d.get('people_taken')} rescued" + (" (on site)" if d.get("on_site") else "")
        case "rescue.disputed":
            return d.get("line") or "Disputed by the family"
        case "contact.revealed":
            return f"Phone number shown to {d.get('by') or who}{'' if not d.get('masked') else ' (' + d['masked'] + ')'}"
        case "report.callback_added":
            return "A callback number was added"
        case "case.location_tightened":
            return f"The circle tightened with {d.get('with')}'s report: {d.get('from_radius_m')} m → {d.get('to_radius_m')} m · {d.get('method')}"
        case "case.location_proposed":
            return (f"{d.get('from')}'s report places them {d.get('metres_away')} m away, outside the circle: a proposed move,"
                    " for a person to accept (the pin stays)")
        case "case.location_changed":
            return f"Took the pin a person set: {d.get('why')}"
        case "case.priority_overridden":
            way = "raised" if d.get("to", "P4") < d.get("from", "P4") else "lowered" if d.get("to") != d.get("from") else "kept"
            return f"{d.get('to')}: {way} from {d.get('from')}{by} (the rules said {d.get('rules_said')})"
        case "case.priority_released":
            return f"Back to the rules: {d.get('to')}{by}"
        case "demo.clip_played":
            voice = "a synthetic voice" if d.get("synthetic_voice") else "a recording"
            return f"Played by the demo control from {d.get('clip')} ({voice}), through the same voice pipeline"
        case "demo.clock_real":
            return f"Demo reset: {d.get('team')}'s timer runs on the real clock until the presenter acts"
        case "demo.clock_advanced":
            return f"Demo reset: {d.get('why', 'a deadline was moved to now')} (moved to now instead of waiting)"
        case _:
            return action.replace(".", " ").replace("_", " ")


def _family(conn: Connection, case_id: int) -> list[int]:
    """This case and every case folded into it (transitively, through the merge links)."""
    return [r[0] for r in conn.execute(text(
        "WITH RECURSIVE f(id) AS (SELECT CAST(:c AS bigint) UNION SELECT c.id FROM cases c JOIN f ON c.parent_case_id = f.id"
        " AND c.status = 'merged') SELECT id FROM f"), {"c": case_id})]


def timeline(conn: Connection, scope: Scope, case_id: int) -> list[dict]:
    where, params = scope.event_where("e")
    ids = _family(conn, case_id)
    # A report's "received" event is written before its case exists, so it is found by the report's id.
    report_ids = [str(r[0]) for r in conn.execute(text("SELECT id FROM reports WHERE case_id = ANY(:ids)"), {"ids": ids})]
    rows = conn.execute(text(
        f"SELECT e.seq, e.at, e.action, e.case_id, e.body, e.reason FROM events e"
        f" WHERE (e.case_id = ANY(:ids) OR (e.entity_type = 'report' AND e.entity_id = ANY(:reports))) AND {where}"
        f" ORDER BY e.seq"), {**params, "ids": ids, "reports": report_ids}).all()
    users = {str(r.id): r.name for r in conn.execute(text("SELECT id, name FROM users"))}
    out = []
    for r in rows:
        body = json.loads(r.body)
        actor = body.get("actor") or {}
        who = users.get(str(actor.get("id"))) if actor.get("type") == "user" else None
        d = body.get("data") or {}
        out.append({"seq": r.seq, "at": r.at.isoformat(), "type": r.action, "line": line(r.action, d, who),
                    "who": who or {"system": "RakshaSetu", "partner": actor.get("id"), "reporter": "reporter"}.get(actor.get("type")),
                    "role": actor.get("role"), "reason": r.reason, "case_id": r.case_id,
                    "report_id": d.get("report_id"), "evidence_id": d.get("evidence_id"), "merge_id": d.get("merge_id"),
                    "undone": False})
    undone = {json.loads(r.body).get("data", {}).get("merge_id") for r in rows if r.action == "case.unmerged"}
    for e in out:   # a merge that was undone can't be undone again
        if e["type"] == "case.merged" and e["merge_id"] in undone:
            e["undone"] = True
    return out


def evidence(conn: Connection, case_id: int) -> list[dict]:
    """Evidence on this case (its own and its folded-in cases'), each with its two hash checks."""
    ids = _family(conn, case_id)
    recorded = {}
    for r in conn.execute(text("SELECT body FROM events WHERE action = 'evidence.added' AND case_id = ANY(:ids)"), {"ids": ids}):
        d = json.loads(r.body).get("data") or {}
        recorded[d.get("evidence_id")] = d.get("sha256")
    out = []
    for e in conn.execute(text(
            "SELECT e.id, e.case_id, e.report_id, e.type, e.uri, e.sha256, e.mime, e.bytes, e.captured_at, e.added_by, e.meta,"
            " r.channel FROM evidence e LEFT JOIN reports r ON r.id = e.report_id"
            " WHERE e.case_id = ANY(:ids) ORDER BY e.captured_at, e.id"), {"ids": ids}):
        item = {k: getattr(e, k) for k in ("id", "case_id", "report_id", "type", "uri", "sha256", "mime", "bytes",
                                            "added_by", "meta", "channel")}
        item["captured_at"] = e.captured_at.isoformat()
        if e.sha256:
            item["file_ok"] = rehash(e.sha256) if e.uri else None
            item["chain_ok"] = recorded.get(e.id) == e.sha256
        out.append(item)
    return out


def evidence_file(conn: Connection, scope: Scope, evidence_id: int):
    """The evidence row, only if its case is in the caller's scope (IDOR: the case scope is in the SQL)."""
    where, params = scope.case_where("c")
    return conn.execute(text(
        f"SELECT e.id, e.sha256, e.mime, e.uri FROM evidence e JOIN cases c ON c.id = e.case_id"
        f" WHERE e.id = :id AND e.uri IS NOT NULL AND {where}"), {**params, "id": evidence_id}).one_or_none()
