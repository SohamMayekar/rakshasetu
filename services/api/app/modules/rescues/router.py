"""POST /v1/cases/{id}/rescues — the rescue sheet, from the team lead's app or an officer's radio record (the same
sheet, "via radio"). Takes Idempotency-Key. And the officer's decisions on a case: close · cancel · reopen, each
with a reason (case.decide)."""

import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.auth import Scope, require
from app.core.eventlog import Actor, append_event
from app.core.listener import require_local
from app.db import get_engine
from app.modules.cases.service import Conflict, NotAllowed, lock_case
from app.modules.rescues import service

router = APIRouter(tags=["rescues"])


class Rescue(BaseModel):
    people_taken: int | None = Field(default=None, ge=0, le=5000)
    anyone_left: Literal["yes", "no", "dont_know"] | None = None
    outcome: Literal["rescued", "nobody_here", "couldnt_reach", "other"] | None = None
    reason: str | None = Field(default=None, max_length=300)
    channel: str = "app"
    happened_at: datetime | None = None
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


@router.post("/v1/cases/{ref}/rescues")
def record(ref: str, body: Rescue, response: Response, idempotency_key: str | None = Header(default=None, max_length=100),
           scope: Scope = Depends(require("assignment.team_action"))) -> dict:
    try:
        with get_engine().begin() as conn:
            if idempotency_key:
                hit = conn.execute(text("SELECT response FROM action_keys WHERE scope = :s AND key = :k"),
                                   {"s": f"user:{scope.user_id}", "k": idempotency_key}).scalar()
                if hit is not None:
                    response.headers["Idempotent-Replay"] = "true"
                    return hit
            out = service.record(conn, scope, Actor("user", str(scope.user_id), scope.role), ref,
                                 people_taken=body.people_taken, anyone_left=body.anyone_left, outcome=body.outcome,
                                 reason=body.reason, channel=body.channel, happened_at=body.happened_at,
                                 lat=body.lat, lng=body.lng)
            if idempotency_key:
                conn.execute(text("INSERT INTO action_keys (scope, key, response) VALUES (:s, :k, CAST(:r AS jsonb))"),
                             {"s": f"user:{scope.user_id}", "k": idempotency_key, "r": json.dumps(out)})
            return out
    except LookupError:
        raise HTTPException(404, "No such case") from None
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except (Conflict, NotAllowed) as e:
        raise HTTPException(409, e.message) from None


class Decision(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


def _decide(kind: str):
    def endpoint(ref: str, body: Decision, scope: Scope = Depends(require("case.decide"))) -> dict:
        with get_engine().begin() as conn:
            case = lock_case(conn, scope, ref)
            if case is None:
                raise HTTPException(404, "No such case")
            live = conn.execute(text("SELECT 1 FROM assignments WHERE case_id = :c AND state IN ('open', 'overdue')"),
                                {"c": case.id}).first()
            if kind in ("close", "cancel"):
                if case.status in ("closed", "cancelled", "merged"):
                    raise HTTPException(409, f"This case is already {case.status}")
                if live:
                    raise HTTPException(409, "A team still holds this case: release or record its outcome first")
                status = "closed" if kind == "close" else "cancelled"
                flags = [f for f in case.flags if f not in service.BLOCKING]
                conn.execute(text("UPDATE cases SET status = :s, resolution = :r, flags = :f, version = version + 1,"
                                  " updated_at = now() WHERE id = :c"), {"s": status, "r": body.reason, "f": flags, "c": case.id})
            else:   # reopen
                if case.status not in ("closed", "cancelled", "rescued"):
                    raise HTTPException(409, f"Only a closed, cancelled or rescued case can be reopened (this one is {case.status})")
                status = "checked" if case.checked_at else "reported"
                conn.execute(text("UPDATE cases SET status = :s, flags = array_append(array_remove(flags, 'reopened'), 'reopened'),"
                                  " resolution = NULL, version = version + 1, updated_at = now() WHERE id = :c"),
                             {"s": status, "c": case.id})
            append_event(conn, actor=Actor("user", str(scope.user_id), scope.role), action={"close": "case.closed", "cancel": "case.cancelled", "reopen": "case.reopened"}[kind],
                         entity_type="case", entity_id=case.id, incident_id=case.incident_id, district_id=case.district_id,
                         case_id=case.id, reason=body.reason, data={"status": status, "by": scope.name})
        return {"case_id": case.id, "status": status}
    endpoint.__name__ = f"case_{kind}"
    return endpoint


for _kind in ("close", "cancel", "reopen"):
    router.post(f"/v1/cases/{{ref}}/{_kind}", dependencies=[Depends(require_local)])(_decide(_kind))
