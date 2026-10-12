"""Rule R20: lanes, SKIP LOCKED, reclaim after 60 s, retries with backoff, idempotent enqueue."""

import pytest
from sqlalchemy import text

from app.core import jobs
from tests.conftest import needs_db, one

pytestmark = needs_db


@pytest.fixture
def clean_jobs(seeded, owner_db):
    with owner_db.begin() as c:
        c.execute(text("TRUNCATE jobs RESTART IDENTITY"))


def test_a_rolled_back_transaction_leaves_no_job(clean_jobs, app_db):
    with app_db.connect() as c:
        tx = c.begin()
        jobs.enqueue(c, "test.x", {}, "surge")
        tx.rollback()
    assert one(app_db, "SELECT count(*) FROM jobs") == 0


def test_enqueue_is_idempotent_by_dedupe_key(clean_jobs, app_db):
    with app_db.begin() as c:
        first = jobs.enqueue(c, "test.x", {}, "surge", dedupe_key="report:1")
        again = jobs.enqueue(c, "test.x", {}, "surge", dedupe_key="report:1")
    assert first is not None and again is None


def test_lanes_decide_claim_order(clean_jobs, app_db):
    with app_db.begin() as c:
        jobs.enqueue(c, "test.x", {"n": "surge"}, "surge")
        jobs.enqueue(c, "test.x", {"n": "import"}, "import")
        jobs.enqueue(c, "test.x", {"n": "voice"}, "live_voice")
    order = []
    for _ in range(3):
        with app_db.begin() as c:
            order.append(jobs.claim(c, "w").payload["n"])
    assert order == ["voice", "import", "surge"]


def test_unknown_lane_is_refused(clean_jobs, app_db):
    with app_db.begin() as c, pytest.raises(ValueError):
        jobs.enqueue(c, "test.x", {}, "vip")


def test_two_workers_never_claim_the_same_job(clean_jobs, app_db):
    with app_db.begin() as c:
        jobs.enqueue(c, "test.x", {}, "surge")
        jobs.enqueue(c, "test.x", {}, "surge")
    with app_db.connect() as a, app_db.connect() as b:
        ta, tb = a.begin(), b.begin()
        ja, jb = jobs.claim(a, "A"), jobs.claim(b, "B")   # A still holds its row lock
        assert ja.id != jb.id
        ta.commit()
        tb.commit()


def test_a_dead_workers_job_is_reclaimed_after_60_seconds_and_runs_once(clean_jobs, app_db):
    ran = []
    jobs.handler("test.count")(lambda engine, payload: ran.append(payload["k"]))
    with app_db.begin() as c:
        jobs.enqueue(c, "test.count", {"k": 1}, "live_voice")
    with app_db.begin() as c:
        assert jobs.claim(c, "worker-that-dies") is not None     # claimed, then the worker is killed
    assert jobs.run_one(app_db, "survivor") is False              # still locked: not yet reclaimable
    with app_db.begin() as c:
        c.execute(text("UPDATE jobs SET locked_at = now() - interval '61 seconds'"))
    assert jobs.run_one(app_db, "survivor") is True
    assert jobs.run_one(app_db, "survivor") is False
    assert ran == [1]
    assert one(app_db, "SELECT attempts FROM jobs") == 2 and one(app_db, "SELECT done_at IS NOT NULL FROM jobs")


def test_a_failing_job_retries_with_backoff_then_goes_dead(clean_jobs, app_db):
    def boom(engine, payload):
        raise RuntimeError("provider down")
    jobs.handler("test.boom")(boom)
    with app_db.begin() as c:
        jobs.enqueue(c, "test.boom", {}, "surge", max_attempts=2)
    assert jobs.run_one(app_db, "w") is True
    assert one(app_db, "SELECT run_at > now() FROM jobs")         # backed off
    with app_db.begin() as c:
        c.execute(text("UPDATE jobs SET run_at = now()"))
    jobs.run_one(app_db, "w")
    assert one(app_db, "SELECT dead_at IS NOT NULL FROM jobs")
    assert "provider down" in one(app_db, "SELECT error FROM jobs")


def test_a_reset_pauses_waiting_jobs_but_not_the_one_a_worker_holds(clean_jobs, app_db, owner_db):
    """The seed's wipe must not race a surge backlog (m49: TRUNCATE deadlocked with reports being filed)."""
    from app.seed import pause_jobs
    with app_db.begin() as c:
        for n in range(3):
            jobs.enqueue(c, "test.x", {"n": n}, "surge")
    held = owner_db.connect()
    tx = held.begin()
    busy = held.execute(text("SELECT id FROM jobs ORDER BY id LIMIT 1 FOR UPDATE")).scalar_one()   # a worker's job
    try:
        with owner_db.begin() as c:
            assert pause_jobs(c) == 2                       # the held row is skipped, never waited on
    finally:
        tx.rollback()
        held.close()
    assert one(app_db, "SELECT count(*) FROM jobs WHERE run_at > now() + interval '50 minutes'") == 2
    with app_db.begin() as c:                               # only the held one is still runnable
        assert jobs.claim(c, "w1").id == busy
        assert jobs.claim(c, "w2") is None
