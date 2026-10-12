"""GET /v1/metrics/promises?incident= (the promise bar, polled every 2 s by the desk) · GET /v1/integrity."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.auth import Scope, require
from app.core.listener import require_local
from app.db import get_engine
from app.modules.metrics import surge
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


@router.get("/v1/metrics/surge")
def surge_metrics(_: Scope = Depends(require("totals.view"))) -> dict:
    """Ingest p95 over the last minute (this API process) and the queue behind it, per lane."""
    with get_engine().connect() as conn:
        lanes = {r.lane: {"waiting": r.waiting, "oldest_s": int(r.oldest or 0)} for r in conn.execute(text(
            "SELECT lane, count(*) AS waiting, extract(epoch FROM now() - min(created_at)) AS oldest FROM jobs"
            " WHERE done_at IS NULL AND dead_at IS NULL GROUP BY lane"))}
        minute = conn.execute(text(
            "SELECT count(*) FILTER (WHERE action = 'report.received') AS reports,"
            " count(*) FILTER (WHERE action = 'case.created') AS cases,"
            " count(*) FILTER (WHERE action = 'case.merged') AS merges"
            " FROM events WHERE at > now() - interval '60 seconds'")).one()
    return {"ingest": surge.window(60), "lanes": lanes, "last_minute": dict(minute._mapping)}
