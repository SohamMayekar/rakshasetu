"""Turn an `events` row into the wire envelope {seq, type, incident_id, at, data} (PRD §11.3)."""

import json


def envelope(row) -> dict:
    body = json.loads(row.body)
    data = dict(body.get("data") or {})
    data.setdefault("entity", body.get("entity"))
    if row.case_id is not None:
        data.setdefault("case_id", row.case_id)
    if row.team_id is not None:
        data.setdefault("team_id", row.team_id)
    if row.reason:
        data.setdefault("reason", row.reason)
    data.setdefault("actor", body.get("actor"))
    return {"seq": row.seq, "type": row.action, "incident_id": row.incident_id, "district_id": row.district_id,
            "at": row.at.isoformat(), "data": data}


EVENT_COLUMNS = "seq, at, action, incident_id, district_id, case_id, team_id, body, reason"
