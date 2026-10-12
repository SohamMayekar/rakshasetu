"""Free-tier caps (PRD §8.4): calls stop at 80% of a cap, tracked in `provider_usage`, then the next
provider in the chain takes over (for the LLM the last resort is the keyword path)."""

from datetime import UTC, datetime

from sqlalchemy import text

from app.config import get_config
from app.db import get_engine
from app.providers.base import ProviderUnavailable


def _windows(now: datetime) -> dict[str, datetime]:
    return {"minute": now.replace(second=0, microsecond=0), "day": now.replace(hour=0, minute=0, second=0, microsecond=0)}


def check(provider: str, *, tokens: int = 0, audio_seconds: float = 0.0) -> None:
    """Raise ProviderUnavailable if this call would pass `stop_at_fraction_of_free_cap` of any cap."""
    cfg = get_config().providers
    caps = cfg.get("free_caps", {}).get(provider, {})
    if not caps:
        return
    frac = cfg.get("stop_at_fraction_of_free_cap", 0.8)
    now = datetime.now(UTC)
    with get_engine().connect() as c:
        used = {r.window_kind: r for r in c.execute(text(
            "SELECT window_kind, calls, tokens, audio_seconds FROM provider_usage WHERE provider = :p"
            " AND ((window_kind = 'minute' AND window_start = :m) OR (window_kind = 'day' AND window_start = :d))"),
            {"p": provider, "m": _windows(now)["minute"], "d": _windows(now)["day"]})}
    for cap_name, limit in caps.items():
        what, _, per = cap_name.rpartition("_per_")
        window = {"min": "minute", "day": "day"}[per]
        row = used.get(window)
        current = 0 if row is None else {"calls": row.calls, "tokens": row.tokens,
                                         "audio_seconds": float(row.audio_seconds)}[what]
        planned = {"calls": 1, "tokens": tokens, "audio_seconds": audio_seconds}[what]
        if current + planned > frac * limit:
            raise ProviderUnavailable(f"{int(frac * 100)}% of the free cap {cap_name}={limit} reached")


def record(provider: str, *, tokens: int = 0, audio_seconds: float = 0.0) -> None:
    now = datetime.now(UTC)
    with get_engine().begin() as c:
        for kind, start in _windows(now).items():
            c.execute(text(
                "INSERT INTO provider_usage (provider, window_kind, window_start, calls, tokens, audio_seconds)"
                " VALUES (:p, :k, :s, 1, :t, :a)"
                " ON CONFLICT (provider, window_kind, window_start) DO UPDATE SET calls = provider_usage.calls + 1,"
                " tokens = provider_usage.tokens + :t, audio_seconds = provider_usage.audio_seconds + :a"),
                {"p": provider, "k": kind, "s": start, "t": tokens, "a": audio_seconds})
