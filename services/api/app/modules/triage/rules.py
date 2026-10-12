"""Triage (PRD F-C3): priority comes from the team's ordered rules in rakshasetu.config.yaml, applied to
facts extracted with quotes. The language model never outputs a priority.

- The HIGHEST matching level wins, and the row shows every reason at that level
  ("P1 because: trapped + water/urgent medical · trapped + vulnerable person").
- `medicine` (routine) is not `medical_urgent` (unconscious, not breathing, bleeding, labour).
- buried / structure_collapsed are P1 when people are there, so a landslide isn't triaged like a flood.
- Inside P1: infant or urgent medical → water rising → other vulnerable → longest wait (p1_order).
"""

from functools import lru_cache

from app.config import get_config
from app.core.expr import evaluate, parse

TRAPPED = {"trapped_on_roof", "trapped_inside"}
SUPPLIES = {"food", "drinking_water", "baby_supplies", "shelter"}


def facts_of(fields: dict) -> dict:
    hazards = set(fields.get("hazards") or [])
    needs = set(fields.get("needs") or [])
    vulnerable = set(fields.get("vulnerable") or [])
    return {
        "trapped": bool(hazards & TRAPPED), "water_rising": "water_rising" in hazards,
        "water_entering": "water_entering" in hazards, "buried": "buried" in hazards,
        "structure_collapsed": "structure_collapsed" in hazards, "landslide": "landslide" in hazards,
        "cut_off": "cut_off" in hazards, "medical_urgent": "medical_urgent" in needs, "medicine": "medicine" in needs,
        "needs_supplies": bool(needs & SUPPLIES), "vulnerable": bool(vulnerable), "infant": "infant" in vulnerable,
        "elderly": "elderly" in vulnerable, "child": "child" in vulnerable, "pregnant": "pregnant" in vulnerable,
        "disabled": "disabled" in vulnerable, "people_count": fields.get("people_count"),
    }


@lru_cache(maxsize=1)
def _compiled():
    return [(r.level, parse(r.when), r.reason) for r in get_config().priority]


def triage(fields: dict) -> tuple[str, list[str], int | None]:
    """(priority, reasons at the winning level, p1_rank)."""
    facts = facts_of(fields)
    matched = [(level, reason) for level, tree, reason in _compiled() if evaluate(tree, facts)]
    best = min(level for level, _ in matched)                     # "P1" < "P2" < … ; the catch-all always matches
    reasons = list(dict.fromkeys(reason for level, reason in matched if level == best))
    return best, reasons, p1_rank(facts) if best == "P1" else None


def p1_rank(facts: dict) -> int:
    for rank, key in enumerate(get_config().p1_order, start=1):
        if key == "infant_or_medical_urgent" and (facts["infant"] or facts["medical_urgent"]):
            return rank
        if key == "water_rising" and facts["water_rising"]:
            return rank
        if key == "vulnerable" and facts["vulnerable"]:
            return rank
    return len(get_config().p1_order)        # waiting time decides the rest
