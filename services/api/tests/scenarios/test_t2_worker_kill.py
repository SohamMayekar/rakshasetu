"""T2 (PRD §13.6, E24): kill the worker mid-surge → integrity = 0, no duplicate cases.

A real worker process (`python -m app.worker`, 4 threads) works through 300 synthetic surge reports and is
SIGKILLed part-way. Its in-flight transactions roll back; the jobs it held are reclaimed once their lock is
60 s old (the test moves that time instead of waiting it out, as T6 moves deadlines); then every report has
exactly one case, no job is lost or dead, the integrity check is 0 and the chain verifies."""

import os
import random
import signal
import subprocess
import sys
import time

import pytest
from sqlalchemy import text

from app.channels.partner import to_canonical
from app.config import get_bundle
from app.contracts import CanonicalReport
from app.core.eventlog import Actor, verify_chain
from app.core.jobs import drain
from app.modules.intake.service import accept
from app.modules.metrics.service import integrity
from app.pipeline import register_handlers
from app.surge import household
from tests.conftest import needs_db, one

pytestmark = [needs_db, pytest.mark.scenario, pytest.mark.slow]
N = 300


def _queue_surge(app_db) -> list[int]:
    rng = random.Random(24)
    seen, ids = [], []
    partner = next(p for p in get_bundle().partners if p.id == "surge-generator")
    with app_db.begin() as c:
        for i in range(N):
            h = rng.choice(seen) if seen and rng.random() < 0.2 else household(rng, i)
            seen.append(h)
            body = {"schema_version": "1", "idempotency_key": f"t2-{i}", "channel": "partner", "incident_hint": h["incident"],
                    "reporter": {"phone": h["phone"], "relation": "unknown"}, "content": {"text": h["text"], "language": "hi"},
                    "structured": h["structured"], "source": {"system": "surge.py", "simulated": True}}
            report = to_canonical(CanonicalReport.model_validate(body), partner)
            ids.append(accept(c, report, source_ns="partner:surge-generator", actor=Actor("partner", partner.id, "partner"),
                              lane=partner.lane).report_id)
    return ids


def _done(app_db, ids) -> int:
    return one(app_db, "SELECT count(*) FROM reports WHERE id = ANY(:ids) AND case_id IS NOT NULL", ids=ids)


def test_t2_killing_the_worker_mid_surge_loses_nothing_and_doubles_nothing(seeded, app_db):
    register_handlers()
    ids = _queue_surge(app_db)
    worker = subprocess.Popen([sys.executable, "-m", "app.worker"], env={**os.environ, "WORKER_THREADS": "4"},
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 90
        while _done(app_db, ids) < N // 4 and time.monotonic() < deadline:
            time.sleep(0.1)
    finally:
        worker.send_signal(signal.SIGKILL)
        worker.wait(timeout=10)
    at_kill = _done(app_db, ids)
    assert N // 4 <= at_kill < N, at_kill                                   # it really died part-way

    held = one(app_db, "SELECT count(*) FROM jobs WHERE done_at IS NULL AND locked_at IS NOT NULL")
    with app_db.begin() as c:                                               # 60 s pass for the dead worker's locks
        c.execute(text("UPDATE jobs SET locked_at = now() - interval '61 seconds' WHERE done_at IS NULL AND locked_at IS NOT NULL"))
    drain(app_db)

    assert _done(app_db, ids) == N                                          # nothing lost
    assert one(app_db, "SELECT count(*) FROM jobs WHERE done_at IS NULL OR dead_at IS NOT NULL") == 0
    twice = one(app_db, "SELECT count(*) FROM (SELECT body::jsonb->'data'->>'report_id' FROM events WHERE action = 'case.created'"
                        " GROUP BY 1 HAVING count(*) > 1) x")
    assert twice == 0                                                       # no report made two cases
    assert one(app_db, "SELECT count(*) FROM cases c WHERE NOT EXISTS (SELECT 1 FROM reports r WHERE r.case_id = c.id)"
                       " AND c.status <> 'merged'") == 0
    with app_db.connect() as c:
        assert integrity(c)["problems"] == 0
        assert verify_chain(c)["ok"] is True
    print(f"\n  T2: {at_kill}/{N} reports in cases when the worker was killed, {held} jobs held by it; all {N} after reclaim")
