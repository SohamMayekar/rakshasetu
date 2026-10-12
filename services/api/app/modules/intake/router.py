"""Ingestion endpoints (PRD §11.1). Every channel ends in intake.accept().

m15: POST /v1/ingest/reports for signed-in users (namespace `user:<id>`). m16 adds HMAC-signed partners
(namespace `partner:<id>`) to the same endpoint and the desk paste/type adapter.
"""

from fastapi import APIRouter, Depends, Response

from app.contracts import CanonicalReport
from app.core.auth import Scope, require
from app.core.eventlog import Actor
from app.db import get_engine
from app.modules.intake.service import accept

router = APIRouter(prefix="/v1/ingest", tags=["ingest"])


def _actor(scope: Scope) -> Actor:
    return Actor("user", str(scope.user_id), scope.role)


@router.post("/reports", status_code=202)
def ingest_report(report: CanonicalReport, response: Response,
                  scope: Scope = Depends(require("report.submit"))) -> dict:
    with get_engine().begin() as conn:
        res = accept(conn, report, source_ns=f"user:{scope.user_id}", actor=_actor(scope),
                     district_id=scope.district_ids[0] if scope.district_ids else None)
    if res.replay:
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"
    return {"report_id": res.report_id, "replay": res.replay}
