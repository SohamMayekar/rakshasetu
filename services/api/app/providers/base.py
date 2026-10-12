"""Shared provider plumbing: modes, keys, errors, and the primary→fallback chain."""

import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field

log = logging.getLogger("rakshasetu.providers")

KEYS = {"sarvam_saaras": "SARVAM_API_KEY", "groq_whisper_large_v3": "GROQ_API_KEY",
        "groq_gpt_oss_120b": "GROQ_API_KEY", "gemini_flash": "GEMINI_API_KEY"}


class ProviderUnavailable(Exception):
    """No key, fixture miss, cap reached, switched off: try the next provider (not an error)."""


class ProviderFailed(Exception):
    """The call was made and failed (HTTP error, timeout, invalid output)."""


class AllProvidersFailed(Exception):
    def __init__(self, attempts: list[dict]):
        super().__init__("; ".join(f"{a['provider']}: {a['outcome']}" for a in attempts))
        self.attempts = attempts


def mode() -> str:
    return os.environ.get("PROVIDER_MODE", "auto").lower()


def api_key(name: str) -> str | None:
    if mode() == "fixture":
        return None
    key = (os.environ.get(KEYS[name]) or "").strip()
    return key if key and not key.startswith("#") else None   # "#…" = a comment Compose read as a value


@dataclass
class ChainResult:
    value: object
    provider: str
    model: str
    latency_ms: int
    attempts: list[dict] = field(default_factory=list)


def run_chain(names: list[str], call: Callable[[str], tuple[object, str]]) -> ChainResult:
    """Try each provider in order. `call(name)` returns (value, model) or raises Unavailable/Failed."""
    attempts: list[dict] = []
    for name in names:
        started = time.monotonic()
        try:
            value, model = call(name)
        except ProviderUnavailable as e:
            attempts.append({"provider": name, "outcome": f"skipped: {e}"})
            continue
        except ProviderFailed as e:
            log.warning("provider %s failed: %s", name, e)
            attempts.append({"provider": name, "outcome": f"failed: {e}"})
            continue
        ms = int((time.monotonic() - started) * 1000)
        attempts.append({"provider": name, "outcome": "ok", "ms": ms})
        return ChainResult(value=value, provider=name, model=model, latency_ms=ms, attempts=attempts)
    raise AllProvidersFailed(attempts)
