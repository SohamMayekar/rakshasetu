"""Ingestion endpoints (PRD §11.1). Every channel ends in intake.accept() through its adapter.

POST /v1/ingest/reports  Canonical Report v1. Either an HMAC-signed partner (namespace `partner:<id>`)
                         or a signed-in user (namespace `user:<id>`).
POST /v1/ingest/desk     The call-taker's paste/type form (local listener; namespace `user:<id>`).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from app.channels import desk, partner
from app.contracts import CanonicalReport
from app.core.auth import Scope, optional_scope, require
from app.core.eventlog import Actor
from app.core.listener import require_local
from app.db import get_engine
from app.modules.intake.service import accept

router = APIRouter(prefix="/v1/ingest", tags=["ingest"])


def _respond(res, response: Response) -> dict:
    if res.replay:
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"
    return {"report_id": res.report_id, "replay": res.replay}


def _accept(report: CanonicalReport, source_ns: str, actor: Actor, district_id: int | None):
    with get_engine().begin() as conn:
        return accept(conn, report, source_ns=source_ns, actor=actor, district_id=district_id)


_REPORT_BODY = {"requestBody": {"required": True, "content": {"application/json": {
    "schema": CanonicalReport.model_json_schema(ref_template="#/components/schemas/{model}")}}}}


@router.post("/reports", status_code=202, openapi_extra=_REPORT_BODY)
async def ingest_report(request: Request, response: Response) -> dict:
    raw = await request.body()
    if "x-rakshasetu-signature" in request.headers:
        p = partner.verify_partner(request.headers, raw, "report.submit")
        report = _parse(raw)
        key = request.headers.get("idempotency-key")
        if not key:
            raise HTTPException(400, "Idempotency-Key header is required")
        if key != report.idempotency_key:
            raise HTTPException(400, "Idempotency-Key header must equal the body's idempotency_key")
        report = partner.to_canonical(report, p)
        res = await run_in_threadpool(_accept, report, f"partner:{p.id}", Actor("partner", p.id, "partner"), None)
        return _respond(res, response)
    scope = optional_scope(request)
    if scope.kind == "public":
        raise HTTPException(401, "Sign in, or sign the request as a partner")
    if not scope.can("report.submit"):
        raise HTTPException(403, f"Your role ({scope.role}) can't do this")
    report = _parse(raw)
    res = await run_in_threadpool(_accept, report, f"user:{scope.user_id}", Actor("user", str(scope.user_id), scope.role),
                                  scope.district_ids[0] if scope.district_ids else None)
    return _respond(res, response)


def _parse(raw: bytes) -> CanonicalReport:
    try:
        return CanonicalReport.model_validate_json(raw)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from None


@router.post("/desk", status_code=202, dependencies=[Depends(require_local)])
def ingest_desk(body: desk.DeskReport, response: Response, scope: Scope = Depends(require("report.submit"))) -> dict:
    report = desk.to_canonical(body)
    res = _accept(report, f"user:{scope.user_id}", Actor("user", str(scope.user_id), scope.role),
                  scope.district_ids[0] if scope.district_ids else None)
    return _respond(res, response)
