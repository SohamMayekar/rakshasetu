"""Assignments (PRD §11.1).

POST /v1/assignments                     an officer assigns a team (local)            assignment.create
POST /v1/assignments/{id}/acknowledge    {eta_minutes: 15|30|60}                        assignment.team_action
POST /v1/assignments/{id}/reached        {long_operation}                               (team lead in the app,
POST /v1/assignments/{id}/release        {reason}                                        or an officer on the
                                                                                         team's behalf, with the
                                                                                         channel it was heard on)
Team actions take Idempotency-Key: a retried tap returns the first answer instead of acting twice.
"""

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.auth import Scope, require
from app.core.listener import require_local
from app.db import get_engine
from app.modules.assignments import service
from app.modules.cases.service import Conflict, NotAllowed, lock_case

router = APIRouter(tags=["assignments"])


class Assign(BaseModel):
    case: str = Field(min_length=1, max_length=20)          # BR-214 or an id
    team_id: int
    suggested_rank: int | None = Field(default=None, ge=1, le=10)


class TeamStep(BaseModel):
    eta_minutes: int | None = None
    long_operation: bool = False
    reason: str | None = Field(default=None, max_length=300)
    channel: str | None = None                              # an officer's: VHF · HAM · satellite · phone
    happened_at: datetime | None = None                     # the phone's own time: shown, never used for deadlines


def _run(fn):
    try:
        with get_engine().begin() as conn:
            return fn(conn)
    except LookupError:
        raise HTTPException(404, "Not found") from None
    except PermissionError as e:
        raise HTTPException(403, str(e)) from None
    except (Conflict, NotAllowed) as e:
        raise HTTPException(409, e.message) from None


@router.post("/v1/assignments", status_code=201, dependencies=[Depends(require_local)])
def assign(body: Assign, scope: Scope = Depends(require("assignment.create"))) -> dict:
    def go(conn):
        case = lock_case(conn, scope, body.case)
        if case is None:
            raise LookupError(body.case)
        team = conn.execute(text("SELECT * FROM teams WHERE id = :t FOR UPDATE"), {"t": body.team_id}).one_or_none()
        if team is None:
            raise LookupError(body.team_id)
        return service.create(conn, case=case, team=team, actor=service._actor(scope), suggested_rank=body.suggested_rank)
    return _run(go)


def _step(action: str):
    def endpoint(assignment_id: int, body: TeamStep, response: Response,
                 idempotency_key: str | None = Header(default=None, max_length=100),
                 scope: Scope = Depends(require("assignment.team_action"))) -> dict:
        def go(conn):
            if idempotency_key:
                hit = conn.execute(text("SELECT response FROM action_keys WHERE scope = :s AND key = :k"),
                                   {"s": f"user:{scope.user_id}", "k": idempotency_key}).scalar()
                if hit is not None:
                    response.headers["Idempotent-Replay"] = "true"
                    return hit
            out = service.act(conn, scope, assignment_id, action, eta_minutes=body.eta_minutes,
                              long_operation=body.long_operation, reason=body.reason, channel=body.channel,
                              happened_at=body.happened_at)
            if idempotency_key:
                conn.execute(text("INSERT INTO action_keys (scope, key, response) VALUES (:s, :k, CAST(:r AS jsonb))"),
                             {"s": f"user:{scope.user_id}", "k": idempotency_key, "r": json.dumps(out)})
            return out
        return _run(go)
    endpoint.__name__ = f"assignment_{action}"
    return endpoint


for _action in ("acknowledge", "reached", "release"):
    router.post(f"/v1/assignments/{{assignment_id}}/{_action}")(_step(_action))
