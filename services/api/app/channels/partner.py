"""Partner systems (PRD §11.4, rule R19). Requests are signed:

    X-RakshaSetu-Partner:   <partner id from config/partners.yaml>
    X-RakshaSetu-Timestamp: <unix seconds>
    X-RakshaSetu-Signature: v1=<hex HMAC-SHA256(secret, timestamp + "." + raw_body)>
    Idempotency-Key:        <required; equals the body's idempotency_key>

The HMAC covers the RAW bytes (never re-serialised JSON), is compared in constant time, and a timestamp
more than 300 s away is rejected, so a captured request can't be replayed later. Each partner has its own
secret, scopes, incidents, a rate cap and an `enabled` kill switch.
"""

import hashlib
import hmac
import os
import threading
import time
from dataclasses import dataclass

from fastapi import HTTPException

from app.channels.registry import adapter
from app.config import Partner, get_bundle
from app.contracts import CanonicalReport

WINDOW_SECONDS = 300


def sign(secret: str, timestamp: str, raw_body: bytes) -> str:
    return "v1=" + hmac.new(secret.encode(), timestamp.encode() + b"." + raw_body, hashlib.sha256).hexdigest()


@dataclass
class _Bucket:
    tokens: float
    at: float


_buckets: dict[str, _Bucket] = {}
_lock = threading.Lock()


def _rate_ok(p: Partner) -> bool:
    """A token bucket per partner, refilled at rate_per_min (per API process)."""
    now = time.monotonic()
    with _lock:
        b = _buckets.setdefault(p.id, _Bucket(tokens=p.rate_per_min, at=now))
        b.tokens = min(p.rate_per_min, b.tokens + (now - b.at) * p.rate_per_min / 60)
        b.at = now
        if b.tokens < 1:
            return False
        b.tokens -= 1
        return True


def _refuse(status: int, why: str, signature_ok: bool | None) -> HTTPException:
    """Refuse, and say in the partner log whether the signature held (None: never checked)."""
    from app.modules.partners.log import note
    note(note=f"{status} · {why}", signature_ok=signature_ok)
    return HTTPException(status, why)


def verify_partner(headers, raw_body: bytes, scope_needed: str) -> Partner:
    from app.modules.partners.log import body_hash, note
    note(body_sha256=body_hash(raw_body))
    pid = headers.get("x-rakshasetu-partner", "")
    ts = headers.get("x-rakshasetu-timestamp", "")
    sig = headers.get("x-rakshasetu-signature", "")
    p = next((x for x in get_bundle().partners if x.id == pid), None)
    if p is None or not p.enabled:
        raise _refuse(401, "Unknown or disabled partner", None)
    secret = os.environ.get(p.secret_env, "")
    if not secret:
        raise _refuse(401, "Partner secret not configured", None)
    try:
        skew = abs(time.time() - int(ts))
    except ValueError:
        raise _refuse(401, "Missing or malformed timestamp", None) from None
    if skew > WINDOW_SECONDS:
        # a replay is usually a request that WAS correctly signed, just too long ago: the log says which
        raise _refuse(401, "Stale timestamp: replay rejected", hmac.compare_digest(sig, sign(secret, ts, raw_body)))
    if not hmac.compare_digest(sig, sign(secret, ts, raw_body)):
        raise _refuse(401, "Bad signature", False)
    if scope_needed not in p.scopes:
        raise _refuse(403, f"Partner not allowed: {scope_needed}", True)
    if not _rate_ok(p):
        raise _refuse(429, "Rate cap reached", True)
    return p


@adapter("partner")
def to_canonical(report: CanonicalReport, partner: Partner) -> CanonicalReport:
    if report.incident_hint and partner.incidents and report.incident_hint not in partner.incidents:
        raise HTTPException(403, f"Partner {partner.id} may not report into {report.incident_hint}")
    src = report.source.model_copy(update={"partner": partner.id, "system": report.source.system or partner.id})
    return report.model_copy(update={"source": src})
