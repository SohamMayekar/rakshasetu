"""The Postgres job queue (rule R20). No Redis: a row per job, claimed with SKIP LOCKED.

- enqueue() is called INSIDE the transaction that created the work (rule R3: report + job together),
  and is idempotent through `dedupe_key`.
- claim() takes the most urgent runnable job: lane order first, then run_at. A job whose worker died
  (locked for more than `job_reclaim_after`, 60 s) becomes claimable again.
- Handlers must be idempotent: a job can run twice (at-least-once), so each handler checks state first.
"""

import json
import logging
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import Connection, Engine, text

from app.config import get_config, parse_duration

log = logging.getLogger("rakshasetu.jobs")
HANDLERS: dict[str, Callable[[Engine, dict], None]] = {}


def handler(kind: str):
    """Register an idempotent job handler: @handler("report.process")."""
    def wrap(fn):
        HANDLERS[kind] = fn
        return fn
    return wrap


def lane_rank(lane: str) -> int:
    lanes = get_config().lanes
    if lane not in lanes:
        raise ValueError(f"unknown lane {lane!r}; lanes are {lanes}")
    return lanes.index(lane)


def enqueue(conn: Connection, kind: str, payload: dict, lane: str, *, dedupe_key: str | None = None,
            delay_s: float = 0, max_attempts: int = 5) -> int | None:
    """Add a job in the caller's transaction. Returns the new id, or None if `dedupe_key` already exists."""
    job_id = conn.execute(text(
        "INSERT INTO jobs (kind, lane, lane_rank, payload, dedupe_key, run_at, max_attempts)"
        " VALUES (:kind, :lane, :rank, CAST(:payload AS jsonb), :key, now() + make_interval(secs => :delay), :max)"
        " ON CONFLICT (dedupe_key) DO NOTHING RETURNING id"),
        dict(kind=kind, lane=lane, rank=lane_rank(lane), payload=json.dumps(payload), key=dedupe_key,
             delay=delay_s, max=max_attempts)).scalar()
    if job_id is not None:
        conn.execute(text("SELECT pg_notify('jobs', :lane)"), {"lane": lane})
    return job_id


def reclaim_after() -> timedelta:
    return parse_duration(get_config().scheduler.get("job_reclaim_after", "60s"))


def claim(conn: Connection, worker_id: str, kinds: list[str] | None = None):
    """Lock and return the most urgent runnable job, or None."""
    kind_filter = "AND kind = ANY(:kinds)" if kinds else ""
    return conn.execute(text(
        "UPDATE jobs SET locked_by = :w, locked_at = now(), attempts = attempts + 1"
        " WHERE id = (SELECT id FROM jobs"
        "             WHERE done_at IS NULL AND dead_at IS NULL AND run_at <= now()"
        "               AND (locked_at IS NULL OR locked_at < now() - make_interval(secs => :reclaim))"
        f"              {kind_filter}"
        "             ORDER BY lane_rank, run_at, id"
        "             FOR UPDATE SKIP LOCKED LIMIT 1)"
        " RETURNING id, kind, lane, payload, attempts, max_attempts"),
        dict(w=worker_id, kinds=kinds, reclaim=reclaim_after().total_seconds())).one_or_none()


def complete(conn: Connection, job_id: int, worker_id: str) -> bool:
    return conn.execute(text("UPDATE jobs SET done_at = now(), error = NULL WHERE id = :id AND locked_by = :w"
                             " AND done_at IS NULL"), {"id": job_id, "w": worker_id}).rowcount == 1


def fail(conn: Connection, job, worker_id: str, error: str) -> None:
    """Release the job for a retry with backoff, or mark it dead after max_attempts."""
    if job.attempts >= job.max_attempts:
        conn.execute(text("UPDATE jobs SET dead_at = now(), locked_by = NULL, locked_at = NULL, error = :e"
                          " WHERE id = :id AND locked_by = :w"), {"id": job.id, "w": worker_id, "e": error[:2000]})
        log.error("job %s (%s) dead after %s attempts: %s", job.id, job.kind, job.attempts, error)
        return
    backoff = min(2 ** job.attempts, 60)
    conn.execute(text("UPDATE jobs SET locked_by = NULL, locked_at = NULL, error = :e,"
                      " run_at = now() + make_interval(secs => :b) WHERE id = :id AND locked_by = :w"),
                 {"id": job.id, "w": worker_id, "e": error[:2000], "b": backoff})


def run_one(engine: Engine, worker_id: str, kinds: list[str] | None = None) -> bool:
    """Claim and run one job. Returns False when there was nothing to do."""
    with engine.begin() as conn:
        job = claim(conn, worker_id, kinds)
    if job is None:
        return False
    fn = HANDLERS.get(job.kind)
    try:
        if fn is None:
            raise RuntimeError(f"no handler registered for {job.kind!r}")
        fn(engine, dict(job.payload))
    except Exception as e:  # the job is retried (or marked dead); the worker keeps going
        log.exception("job %s (%s) failed", job.id, job.kind)
        with engine.begin() as conn:
            fail(conn, job, worker_id, f"{type(e).__name__}: {e}")
        return True
    with engine.begin() as conn:
        complete(conn, job.id, worker_id)
    return True


def drain(engine: Engine, worker_id: str = "inline", kinds: list[str] | None = None, limit: int = 10_000) -> int:
    """Run jobs until none are runnable (tests and the seed use this to process synchronously)."""
    n = 0
    while n < limit and run_one(engine, worker_id, kinds):
        n += 1
    return n
