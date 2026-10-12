"""GET /v1/metrics/promises?incident= (the promise bar, polled every 2 s by the desk) · GET /v1/integrity."""

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import Scope, require
from app.core.listener import require_local
from app.db import get_engine
from app.modules.metrics.service import integrity, promises

router = APIRouter(tags=["metrics"], dependencies=[Depends(require_local)])


@router.get("/v1/metrics/promises")
def promise_bar(incident: str, scope: Scope = Depends(require("totals.view"))) -> dict:
    with get_engine().connect() as conn:
        out = promises(conn, scope, incident)
    if out is None:
        raise HTTPException(404, "No such incident")
    return out


@router.get("/v1/integrity")
def integrity_check(_: Scope = Depends(require("totals.view"))) -> dict:
    with get_engine().connect() as conn:
        return integrity(conn)
