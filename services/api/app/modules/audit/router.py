"""GET /v1/audit/verify, /v1/audit/head and /v1/audit (PRD §11.1, F-C8).

The head is public and read-only so a partner can countersign it. Verify and the event list are
desk-side (local listener) and need `audit.read` (officers see their own district's events; the admin all).
"""

from fastapi import APIRouter, Depends

from app.core.auth import Scope, require
from app.core.listener import require_local
from app.db import get_engine
from app.modules.audit import repo

router = APIRouter(prefix="/v1/audit", tags=["audit"])


@router.get("/head")
def audit_head() -> dict:
    with get_engine().connect() as c:
        return repo.head(c)


@router.get("/verify", dependencies=[Depends(require_local)])
def audit_verify(_: Scope = Depends(require("audit.read"))) -> dict:
    with get_engine().connect() as c:
        return repo.verify(c)


@router.get("", dependencies=[Depends(require_local)])
def audit_list(case_id: int | None = None, entity_type: str | None = None, entity_id: str | None = None,
               actor_id: str | None = None, after_seq: int = 0, limit: int = 200,
               scope: Scope = Depends(require("audit.read"))) -> list[dict]:
    where, params = scope.event_where("events")
    with get_engine().connect() as c:
        return repo.list_events(c, where_sql=where, params=params, case_id=case_id, entity_type=entity_type, entity_id=entity_id,
                                actor_id=actor_id, after_seq=after_seq, limit=limit)
