"""The `worker` process: runs the intake pipeline and the importer from the Postgres job queue (rule R20).

Several threads claim jobs with SKIP LOCKED, so they never take the same job. Between bursts each thread
waits on `LISTEN jobs` (with a 1 s timeout), so a new report starts processing at once instead of on the
next poll. Kill it at any moment: an unfinished job is reclaimed after 60 s and handlers are idempotent.
"""

import logging
import os
import signal
import socket
import threading

import psycopg

from app.core.jobs import run_one
from app.db import get_engine
from app.migrate import to_conninfo
from app.pipeline import register_handlers
from app.settings import get_settings

log = logging.getLogger("rakshasetu.worker")
STOP = threading.Event()


def worker_thread(n: int) -> None:
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{n}"
    engine = get_engine()
    with psycopg.connect(to_conninfo(get_settings().database_url), autocommit=True) as listen:
        listen.execute("LISTEN jobs")
        while not STOP.is_set():
            try:
                while not STOP.is_set() and run_one(engine, worker_id):
                    pass
                open("/tmp/worker.heartbeat", "a").close()
                os.utime("/tmp/worker.heartbeat")
                for _ in listen.notifies(timeout=1.0, stop_after=1):
                    pass
            except Exception:
                log.exception("worker loop error")
                STOP.wait(1.0)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s worker %(levelname)s %(message)s")
    register_handlers()
    threads = int(os.environ.get("WORKER_THREADS", "4"))
    signal.signal(signal.SIGTERM, lambda *_: STOP.set())
    log.info("started with %d threads", threads)
    ts = [threading.Thread(target=worker_thread, args=(i,), daemon=True) for i in range(threads)]
    [t.start() for t in ts]
    while not STOP.wait(1.0):
        pass
    log.info("stopping")


if __name__ == "__main__":
    main()
