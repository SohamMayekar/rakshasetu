"""GET /v1/cases/{ref}/dispatch — the top teams for a case, with reasons (local listener, scoped)."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import Scope, require
from app.core.listener import require_local
from app.db import get_engine
from app.modules.cases import repo
from app.modules.dispatch.service import rank, teams_for

router = APIRouter(tags=["dispatch"], dependencies=[Depends(require_local)])


@router.get("/v1/cases/{ref}/dispatch")
def dispatch(ref: str, scope: Scope = Depends(require("queue.view"))) -> dict:
    with get_engine().connect() as conn:
        case = repo.get_case(conn, scope, ref)
        if case is None:
            raise HTTPException(404, "No such case")
        return rank(case, teams_for(conn, case["incident_id"], case["district_id"]))
