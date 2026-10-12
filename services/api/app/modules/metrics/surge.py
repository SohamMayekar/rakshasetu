"""Ingest timing for the surge screen (PRD F-C5: "the surge screen shows ingest p95").

The API process keeps the durations of its last ingest requests in memory (one uvicorn process serves the API;
nothing here is evidence or history, so nothing goes to the database). GET /v1/metrics/surge reads the last
60 s: requests per second, p50 / p95 / p99, errors, and the job backlog per lane from the database.
"""

import threading
import time
from collections import deque

_samples: deque = deque(maxlen=20_000)        # (monotonic time, ms, status)
_lock = threading.Lock()


def record(ms: float, status: int) -> None:
    with _lock:
        _samples.append((time.monotonic(), ms, status))


def window(seconds: float = 60) -> dict:
    now = time.monotonic()
    with _lock:
        recent = [s for s in _samples if now - s[0] <= seconds]
    ok = sorted(ms for _, ms, st in recent if st < 400)

    def pct(p: float) -> float | None:
        if not ok:
            return None
        return round(ok[min(len(ok) - 1, int(round(p / 100 * (len(ok) - 1))))], 1)
    span = (now - recent[0][0]) if recent else 0
    return {"window_s": seconds, "requests": len(recent), "accepted": len(ok), "errors": len(recent) - len(ok),
            "per_second": round(len(recent) / span, 1) if span > 1 else float(len(recent)),
            "p50_ms": pct(50), "p95_ms": pct(95), "p99_ms": pct(99)}
