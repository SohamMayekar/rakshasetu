"""The worker keeps trying when Postgres is away (starting up after a restart), instead of a thread dying silently
and leaving reports unread until someone restarts the worker."""

import threading

import psycopg

from app import worker
from tests.conftest import needs_db

pytestmark = needs_db


def test_a_worker_thread_connects_again_after_the_database_was_starting_up(monkeypatch):
    real_connect = psycopg.connect
    attempts, ran = [], threading.Event()

    def flaky_connect(*a, **kw):
        attempts.append(1)
        if len(attempts) == 1:
            raise psycopg.OperationalError("FATAL:  the database system is starting up")
        return real_connect(*a, **kw)

    def one_job(engine, worker_id):
        ran.set()
        worker.STOP.set()
        return False

    monkeypatch.setattr(worker.psycopg, "connect", flaky_connect)
    monkeypatch.setattr(worker, "run_one", one_job)
    monkeypatch.setattr(worker, "beat", lambda: None)
    worker.STOP.clear()
    t = threading.Thread(target=worker.worker_thread, args=(0,), daemon=True)
    t.start()
    try:
        assert ran.wait(10), "the thread never came back after the failed connection"
        assert len(attempts) >= 2
    finally:
        worker.STOP.set()
        t.join(5)
        worker.STOP.clear()
