"""The partner log (PRD P1 #13): every partner call, in or out, with its signature result, latency and body hash.
A middleware times each partner request; the endpoint (or the signature check) fills in the body hash and why
it was refused, through a per-request record. The surge generator's synthetic load is not logged (thousands
of rows a minute would bury the calls a person wants to see)."""

import contextvars
import hashlib

from sqlalchemy import text

from app.db import get_engine

CALL: contextvars.ContextVar[dict | None] = contextvars.ContextVar("partner_call", default=None)


def note(**kw) -> None:
    """Add what the endpoint knows (body_sha256, why it refused, signature_ok: None = never checked) to the call
    being logged, if any."""
    c = CALL.get()
    if c is not None:
        c.update(kw)


def body_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(partner: str | None, direction: str, method: str, endpoint: str, status: int, latency_ms: int, call: dict) -> None:
    signature_ok = call.get("signature_ok", False if status == 401 else True if status < 500 else None)
    with get_engine().begin() as c:
        c.execute(text("INSERT INTO partner_calls (partner, direction, method, endpoint, status, signature_ok, latency_ms,"
                       " body_sha256, note) VALUES (:p, :d, :m, :e, :s, :ok, :ms, :sha, :n)"),
                  {"p": partner, "d": direction, "m": method, "e": endpoint, "s": status, "ok": signature_ok,
                   "ms": latency_ms, "sha": call.get("body_sha256"), "n": call.get("note")})
