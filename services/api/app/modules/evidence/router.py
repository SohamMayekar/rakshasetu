"""GET /v1/evidence/{id}/file — an evidence file (an audio clip, a spreadsheet), only if its case is in the
caller's scope (rule R8; the scope is in the SQL). Served from the content-addressed store, never modified."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.auth import Scope, require
from app.core.storage import path_for
from app.db import get_engine
from app.modules.cases.timeline import evidence_file

router = APIRouter(tags=["evidence"])


@router.get("/v1/evidence/{evidence_id}/file")
def get_file(evidence_id: int, scope: Scope = Depends(require("queue.view"))) -> FileResponse:
    with get_engine().connect() as c:
        e = evidence_file(c, scope, evidence_id)
    if e is None or not path_for(e.sha256).exists():
        raise HTTPException(404, "No such evidence")
    return FileResponse(path_for(e.sha256), media_type=e.mime or "application/octet-stream",
                        headers={"X-Content-SHA256": e.sha256, "Cache-Control": "private, max-age=3600",
                                 "X-Content-Type-Options": "nosniff"})
