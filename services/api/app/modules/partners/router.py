"""Partners (PRD §11.4).

    POST /v1/partners/annotations            a partner system, signed like every partner POST (public listener)
    GET  /v1/cases/{ref}/annotations         the desk: what partners said about this case
    POST /v1/partner-annotations/{id}/accept the officer takes a partner's priority suggestion (with its reason)
    POST /v1/partner-annotations/{id}/ignore … or doesn't; both audited
    GET  /v1/partners/log                    the partner log: every call, signature ✓/✗, latency, body hash
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text

from app.channels import partner as signing
from app.core.auth import Scope, require
from app.core.listener import require_local
from app.db import get_engine
from app.modules.cases.service import NotAllowed, lock_case
from app.modules.partners import service

router = APIRouter(tags=["partners"])


class Annotation(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=100)
    kind: Literal["credibility", "priority", "identity", "anchor_receipt"]
    target: dict
    value: str = Field(min_length=1, max_length=100)
    confidence: float | None = Field(default=None, ge=0, le=1)
    explanation: str | None = Field(default=None, max_length=300)


@router.post("/v1/partners/annotations", status_code=201)
async def annotate(request: Request, response: Response) -> dict:
    raw = await request.body()
    p = signing.verify_partner(request.headers, raw, "partner.annotate")
    try:
        body = Annotation.model_validate_json(raw)
    except ValidationError as e:
        raise HTTPException(422, e.errors(include_url=False, include_context=False)) from None
    if request.headers.get("idempotency-key") != body.idempotency_key:
        raise HTTPException(400, "Idempotency-Key header must equal the body's idempotency_key")
    try:
        with get_engine().begin() as conn:
            out, replay = service.receive(conn, p, body.model_dump())
    except service.Refused as e:
        raise HTTPException(e.status, e.message) from None
    if replay:
        response.status_code = 200
        response.headers["Idempotent-Replay"] = "true"
    return out


@router.get("/v1/cases/{ref}/annotations", dependencies=[Depends(require_local)])
def case_annotations(ref: str, scope: Scope = Depends(require("queue.view"))) -> list[dict]:
    with get_engine().begin() as conn:
        c = lock_case(conn, scope, ref)
        if c is None:
            raise HTTPException(404, "No such case")
        return service.for_case(conn, c.id)


def _decide(annotation_id: int, scope: Scope, accept: bool) -> dict:
    try:
        with get_engine().begin() as conn:
            return service.decide(conn, scope, annotation_id, accept)
    except LookupError as e:
        if type(e) is not LookupError:
            raise
        raise HTTPException(404, "No such suggestion") from None
    except NotAllowed as e:
        raise HTTPException(409, e.message) from None


@router.post("/v1/partner-annotations/{annotation_id}/accept", dependencies=[Depends(require_local)])
def accept(annotation_id: int, scope: Scope = Depends(require("priority.override"))) -> dict:
    return _decide(annotation_id, scope, True)


@router.post("/v1/partner-annotations/{annotation_id}/ignore", dependencies=[Depends(require_local)])
def ignore(annotation_id: int, scope: Scope = Depends(require("priority.override"))) -> dict:
    return _decide(annotation_id, scope, False)


@router.get("/v1/partners/log", dependencies=[Depends(require_local)])
def partner_log(limit: int = 100, _: Scope = Depends(require("audit.read"))) -> dict:
    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT * FROM partner_calls ORDER BY id DESC LIMIT :n"), {"n": min(limit, 500)}).all()
        anchors = service.anchors(conn)
    from app.config import get_bundle
    teams = {p.id: p.team for p in get_bundle().partners}
    return {"calls": [{**dict(r._mapping), "at": r.at.isoformat(), "team": teams.get(r.partner)} for r in rows],
            "anchors": anchors}
