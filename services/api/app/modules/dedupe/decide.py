"""The duplicate decision (PRD F-D1). Rules only; the language model plays no part.

    auto-merge   score ≥ 0.85 AND phone/device match AND place or geo agree AND nothing conflicts
    suggest      score 0.60–0.85, or ≥ 0.85 without a phone/device match; "weak" if no phone/device,
                 given-name or Medium+ geo agreement; same phone + village but different counts → suggest,
                 with the differences shown in red
    refused      differing given names (m27): shown as "Not merged: Ramesh ≠ Rajesh", in red
    new case     otherwise
Minimum evidence: at least two non-time signals, including place or geo, or there is no suggestion at all.
Hard blocks: both pins High and > 2 km apart (same phone → review instead); a pair a person blocked.
No chains: a new report is compared with each existing case directly, never through another case.
"""

from dataclasses import dataclass, field

from sqlalchemy import Connection, text

from app.config import get_config
from app.modules.dedupe.signals import Household, Score, score


@dataclass
class Match:
    candidate: Household
    score: Score
    outcome: str            # auto_merge | suggest | refused
    strength: str           # strong | weak | refused
    reasons: list[str]
    conflicts: list[str]


@dataclass
class Decision:
    kind: str                                   # new | auto_merge
    target: Match | None = None
    suggestions: list[Match] = field(default_factory=list)


def blocked(conn: Connection, a: int | None, b: int | None) -> bool:
    if not a or not b:
        return False
    lo, hi = sorted((a, b))
    return conn.execute(text("SELECT 1 FROM merge_blocks WHERE case_a = :a AND case_b = :b"),
                        {"a": lo, "b": hi}).first() is not None


def judge(new: Household, old: Household, conn: Connection | None = None) -> Match | None:
    cfg = get_config().dedupe
    sc = score(new, old)
    non_time = [k for k, v in sc.signals.items() if k != "time" and v > 0]
    if len(non_time) < cfg.min_signals or not (sc.place_ok or sc.geo_ok):
        return None                              # missing evidence isn't evidence: no suggestion
    if conn is not None and blocked(conn, new.case_id, old.case_id):
        return None
    far = (new.confidence == "high" and old.confidence == "high" and new.lat is not None and old.lat is not None
           and _far(new, old, cfg.block.get("high_conf_distance_km_gt", 2) * 1000))
    if far and not sc.phone_match:
        return None
    name_conflicts = [c for c in sc.conflicts if c.startswith("name ")]
    if name_conflicts:
        return Match(old, sc, "refused", "refused", sc.reasons, sc.conflicts)
    if (sc.total >= cfg.auto_merge_at and sc.phone_match and (sc.place_ok or sc.geo_ok)
            and not sc.conflicts and not far):
        return Match(old, sc, "auto_merge", "strong", sc.reasons, sc.conflicts)
    if sc.total >= cfg.suggest_at or (sc.phone_match and sc.place_ok):
        strong = sc.phone_match or sc.signals.get("names", 0) > 0 or sc.geo_ok
        return Match(old, sc, "suggest", "strong" if strong else "weak", sc.reasons, sc.conflicts)
    return None


def _far(a: Household, b: Household, metres: float) -> bool:
    from app.modules.dedupe.signals import _metres
    return _metres(a, b) > metres


def decide(conn: Connection, new: Household, cands: list[Household]) -> Decision:
    matches = [m for m in (judge(new, c, conn) for c in cands) if m]
    autos = sorted((m for m in matches if m.outcome == "auto_merge"), key=lambda m: (-m.score.total, m.candidate.case_id))
    if autos:
        return Decision("auto_merge", target=autos[0])
    shown = sorted((m for m in matches if m.outcome in ("suggest", "refused")),
                   key=lambda m: (m.outcome == "refused", -m.score.total))[:3]
    return Decision("new", suggestions=shown)


def reason_line(m: Match) -> str:
    """Plain-language reasons from a template, never from a model."""
    pid = m.candidate.public_id
    if m.outcome == "refused":
        names = "; ".join(c.removeprefix("name ") for c in m.conflicts if c.startswith("name "))
        return f"Not merged with {pid}: {names}. " + ("Village and headcount alone are weak."
                                                       if not m.score.phone_match else "Same phone, different family.")
    lead = "Merged into" if m.outcome == "auto_merge" else "Likely same household as"
    return f"{lead} {pid}: " + " · ".join(m.reasons)
