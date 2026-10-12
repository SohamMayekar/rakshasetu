"""WS /v1/ws?incident=&since= and GET /v1/events?since= (PRD §11.1, F-C10)."""

import asyncio
import contextlib

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import text

from app.core.auth import Scope, current_scope, optional_scope
from app.db import get_engine
from app.modules.realtime.envelope import EVENT_COLUMNS, envelope
from app.modules.realtime.hub import Subscriber, hub

router = APIRouter(tags=["realtime"])
PING_SECONDS = 25


def _incident_id(code: str | None) -> int | None:
    if not code:
        return None
    with get_engine().connect() as c:
        return c.execute(text("SELECT id FROM incidents WHERE code = :c"), {"c": code}).scalar()


def _live_cases(team_id: int) -> set[int]:
    with get_engine().connect() as c:
        return {r[0] for r in c.execute(text("SELECT case_id FROM assignments WHERE team_id = :t"
                                             " AND state IN ('open', 'overdue')"), {"t": team_id})}


def _scoped_filter(scope: Scope, incident_id: int | None):
    """The caller's Scope as a predicate over envelopes, narrowed to one incident if asked.
    A team lead's live cases are re-read whenever one of its assignments changes."""
    if scope.role == "team_lead" and scope.team_id:
        scope.extras["live_case_ids"] = _live_cases(scope.team_id)

    def allows(env: dict) -> bool:
        if scope.role == "team_lead" and env["type"].startswith("assignment.") \
                and env["data"].get("team_id") == scope.team_id:
            scope.extras["live_case_ids"] = _live_cases(scope.team_id)
        if incident_id is not None and env["incident_id"] not in (None, incident_id):
            return False
        return scope.allows_envelope(env)
    return allows


@router.get("/v1/events")
def events_since(since: int = 0, incident: str | None = None, limit: int = Query(500, le=2000),
                 scope: Scope = Depends(current_scope)) -> list[dict]:
    """Back-fill and polling fallback: the same envelopes the WebSocket sends, scoped in SQL."""
    where, params = scope.event_where("events")
    inc = _incident_id(incident)
    if inc is not None:
        where += " AND (events.incident_id IS NULL OR events.incident_id = :inc)"
        params["inc"] = inc
    with get_engine().connect() as c:
        rows = c.execute(text(f"SELECT {EVENT_COLUMNS} FROM events WHERE seq > :s AND {where} ORDER BY seq LIMIT :n"),
                         {"s": since, "n": limit, **params}).all()
    return list(map(envelope, rows))


@router.websocket("/v1/ws")
async def ws(websocket: WebSocket, since: int = 0, incident: str | None = None) -> None:
    scope = optional_scope(websocket)
    if scope.kind == "public":
        await websocket.close(code=4401)   # sign in first
        return
    await websocket.accept()
    sub = Subscriber(send=websocket.send_json, allows=_scoped_filter(scope, _incident_id(incident)))

    async def ping() -> None:
        while True:
            await asyncio.sleep(PING_SECONDS)
            await websocket.send_json({"type": "ping", "seq": sub.cursor})

    pinger = asyncio.create_task(ping())
    try:
        await hub.subscribe(sub, since)
        await websocket.send_json({"type": "hello", "seq": sub.cursor})
        while True:   # we only read to notice the disconnect
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        pinger.cancel()
        hub.unsubscribe(sub)
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await pinger
