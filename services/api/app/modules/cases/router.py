"""GET /v1/cases and GET /v1/cases/{ref} (PRD §11.1). Scoped reads; edits arrive with their slices."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import Scope, require
from app.db import get_engine
from app.modules.cases import repo

router = APIRouter(prefix="/v1/cases", tags=["cases"])


@router.get("")
def list_cases(incident: str | None = None, scope: Scope = Depends(require("queue.view"))) -> list[dict]:
    with get_engine().connect() as c:
        return repo.list_cases(c, scope, incident)


@router.get("/{ref}")
def get_case(ref: str, scope: Scope = Depends(require("queue.view"))) -> dict:
    with get_engine().connect() as c:
        case = repo.get_case(c, scope, ref)
        if case is None:
            if scope.role == "team_lead" and repo.case_exists(c, ref):
                raise HTTPException(status_code=403, detail="Not assigned to your team")
            raise HTTPException(status_code=404, detail="No such case")
        case["reports"] = repo.reports_for_case(c, scope, case["id"])
    return case
