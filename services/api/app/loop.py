"""Shared plumbing for the long-running worker and ticker processes."""

import logging
import signal
import time
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("rakshasetu")


def run_forever(name: str, every_s: float, step: Callable[[], None]) -> None:
    """Call `step` every `every_s` seconds until SIGTERM. Touch a heartbeat file for the container healthcheck."""
    logging.basicConfig(level=logging.INFO, format=f"%(asctime)s {name} %(levelname)s %(message)s")
    stop = {"now": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(now=True))
    heartbeat = Path(f"/tmp/{name}.heartbeat")
    log.info("started (every %.1fs)", every_s)
    while not stop["now"]:
        started = time.monotonic()
        try:
            step()
            heartbeat.touch()
        except Exception:  # keep the loop alive; the error is logged with its traceback
            log.exception("step failed")
        time.sleep(max(0.0, every_s - (time.monotonic() - started)))
    log.info("stopped")
