"""Real-time fan-out (PRD F-C10). The API holds ONE `LISTEN ev` connection. Each NOTIFY carries only a seq;
the hub reads `events WHERE seq > cursor` and sends each event to every subscriber allowed to see it.

Subscribers resume with ?since=<seq>, so a dropped socket loses nothing: on (re)connect a subscriber is
registered first (not yet "ready"), back-filled from the table, then caught up again before going live.
`case.updated` is coalesced to at most one per case per second per subscriber (F-C5).
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import psycopg
from psycopg.rows import namedtuple_row

from app.migrate import to_conninfo
from app.modules.realtime.envelope import EVENT_COLUMNS, envelope
from app.settings import get_settings

log = logging.getLogger("rakshasetu.realtime")
COALESCE_SECONDS = 1.0


@dataclass(eq=False)
class Subscriber:
    send: Callable[[dict], Awaitable[None]]
    allows: Callable[[dict], bool]            # the subscriber's Scope, as a predicate over envelopes
    cursor: int = 0                           # last seq delivered
    ready: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)  # created inside the running loop
    last_case_update: dict = field(default_factory=dict)   # case_id -> monotonic time sent
    pending_case_update: dict = field(default_factory=dict)  # case_id -> envelope held back


class Hub:
    def __init__(self) -> None:
        self.subscribers: set[Subscriber] = set()
        self.cursor = 0
        self._task: asyncio.Task | None = None
        self._query_lock = asyncio.Lock()
        self._db: psycopg.AsyncConnection | None = None

    # --- lifecycle -------------------------------------------------------------------------------
    async def start(self) -> None:
        # asyncio primitives belong to the running loop, so they're (re)made here, not in __init__.
        self._query_lock = asyncio.Lock()
        self.subscribers = set()
        conninfo = to_conninfo(get_settings().database_url)
        self._db = await psycopg.AsyncConnection.connect(conninfo, autocommit=True, row_factory=namedtuple_row)
        row = await (await self._db.execute("SELECT coalesce(max(seq), 0) AS seq FROM events")).fetchone()
        self.cursor = row.seq
        self._task = asyncio.create_task(self._run(conninfo))

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(self._task, timeout=3)
        if self._db:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self._db.close(), timeout=3)

    async def _run(self, conninfo: str) -> None:
        """LISTEN forever; reconnect if Postgres goes away. A 1 s tick also flushes coalesced updates
        and catches anything a lost notification would have announced."""
        while True:
            try:
                async with await psycopg.AsyncConnection.connect(conninfo, autocommit=True) as listen:
                    await listen.execute("LISTEN ev")
                    while True:
                        # psycopg's own timeout: returns after one notification or a quiet second, without
                        # cancelling the generator (cancelling it can leave the connection stuck)
                        async for _ in listen.notifies(timeout=COALESCE_SECONDS, stop_after=1):
                            pass
                        await self.pump()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("listen loop failed; reconnecting in 1 s")
                await asyncio.sleep(1)

    # --- reading the table -----------------------------------------------------------------------
    async def fetch_since(self, seq: int, limit: int = 1000) -> list[dict]:
        async with self._query_lock:
            cur = await self._db.execute(
                f"SELECT {EVENT_COLUMNS} FROM events WHERE seq > %s ORDER BY seq LIMIT %s", (seq, limit))
            return [envelope(r) for r in await cur.fetchall()]

    async def pump(self) -> None:
        events = await self.fetch_since(self.cursor)
        if events:
            self.cursor = events[-1]["seq"]
        for sub in list(self.subscribers):
            if sub.ready:
                await self._deliver(sub, events)

    # --- subscribers -----------------------------------------------------------------------------
    async def subscribe(self, sub: Subscriber, since: int) -> None:
        sub.cursor = since
        async with sub.lock:
            self.subscribers.add(sub)
            while True:   # back-fill until we've caught up with the hub
                batch = await self.fetch_since(sub.cursor)
                if not batch:
                    break
                await self._send_filtered(sub, batch)
            sub.ready = True

    def unsubscribe(self, sub: Subscriber) -> None:
        self.subscribers.discard(sub)

    async def _deliver(self, sub: Subscriber, events: list[dict]) -> None:
        async with sub.lock:
            await self._send_filtered(sub, [e for e in events if e["seq"] > sub.cursor])
            now = time.monotonic()
            for case_id, env in list(sub.pending_case_update.items()):
                if now - sub.last_case_update.get(case_id, 0) >= COALESCE_SECONDS:
                    del sub.pending_case_update[case_id]
                    sub.last_case_update[case_id] = now
                    await self._safe_send(sub, env)

    async def _send_filtered(self, sub: Subscriber, events: list[dict]) -> None:
        now = time.monotonic()
        for env in events:
            sub.cursor = max(sub.cursor, env["seq"])
            if not sub.allows(env):
                continue
            case_id = env["data"].get("case_id")
            if env["type"] == "case.updated" and case_id is not None and sub.ready:
                if now - sub.last_case_update.get(case_id, 0) < COALESCE_SECONDS:
                    sub.pending_case_update[case_id] = env     # keep only the latest
                    continue
                sub.last_case_update[case_id] = now
            await self._safe_send(sub, env)

    async def _safe_send(self, sub: Subscriber, env: dict) -> None:
        try:
            await sub.send(env)
        except Exception:
            self.unsubscribe(sub)


hub = Hub()
