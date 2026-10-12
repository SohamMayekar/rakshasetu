"""WS /v1/ws?incident=&since= and GET /v1/events?since= (PRD §11.1, F-C10)."""

import asyncio
import contextlib

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import text

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


def _incident_filter(incident_id: int | None):
    # Events without an incident (chain.genesis, user.seeded) are system-wide and go to everyone.
    return lambda env: incident_id is None or env["incident_id"] in (None, incident_id)


@router.get("/v1/events")
def events_since(since: int = 0, incident: str | None = None, limit: int = Query(500, le=2000)) -> list[dict]:
    """Back-fill and polling fallback: the same envelopes the WebSocket sends."""
    allows = _incident_filter(_incident_id(incident))
    with get_engine().connect() as c:
        rows = c.execute(text(f"SELECT {EVENT_COLUMNS} FROM events WHERE seq > :s ORDER BY seq LIMIT :n"),
                         {"s": since, "n": limit}).all()
    return [e for e in map(envelope, rows) if allows(e)]


@router.websocket("/v1/ws")
async def ws(websocket: WebSocket, since: int = 0, incident: str | None = None) -> None:
    await websocket.accept()
    sub = Subscriber(send=websocket.send_json, allows=_incident_filter(_incident_id(incident)))

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
