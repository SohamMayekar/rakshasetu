"""GET /v1/cases and GET /v1/cases/{ref} (PRD §11.1). Scoped reads; edits arrive with their slices."""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import Scope, require
from app.core.listener import require_local
from app.db import get_engine
from app.modules.cases import repo, service

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


# --- desk corrections (local listener only) ---------------------------------------------------------------

class PinMove(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    reason: str = Field(min_length=3, max_length=300)


class Edit(BaseModel):
    changes: dict
    reason: str = Field(min_length=3, max_length=300)


def _write(fn, *args):
    try:
        with get_engine().begin() as c:
            return fn(c, *args)
    except LookupError:
        raise HTTPException(404, "No such case") from None
    except service.Conflict as e:
        raise HTTPException(409, e.message) from None
    except service.NotAllowed as e:
        raise HTTPException(409, e.message) from None


@router.patch("/{ref}/location", dependencies=[Depends(require_local)])
def move_pin(ref: str, body: PinMove, scope: Scope = Depends(require("case.move_pin"))) -> dict:
    return _write(service.move_pin, scope, ref, body.lat, body.lng, body.reason)


@router.post("/{ref}/check", dependencies=[Depends(require_local)])
def check(ref: str, scope: Scope = Depends(require("case.check"))) -> dict:
    return _write(service.check_case, scope, ref)


@router.patch("/{ref}", dependencies=[Depends(require_local)])
def edit(ref: str, body: Edit, if_match: int | None = Header(default=None),
         scope: Scope = Depends(require("case.edit"))) -> dict:
    return _write(service.edit_case, scope, ref, body.changes, body.reason, if_match)
