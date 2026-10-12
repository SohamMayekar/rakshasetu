"""The duplicate score (PRD F-D1): a weighted sum of the signals that AGREE. Missing evidence counts 0,
never "neutral": relatives call from different phones, so a different phone isn't evidence against, but
no phone match also adds nothing. Without a phone/device match the maximum score is 0.70, so an
automatic merge needs a phone or device match by arithmetic. Pure functions; the weights are the team's.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime

from rapidfuzz import fuzz

from app.config import get_config
from app.modules.location.names import norm

CONF_ORDER = {"very_low": 0, "low": 1, "medium": 2, "high": 3}


@dataclass
class Household:
    """What we know about one household, from a case (all its reports) or from a new report."""
    case_id: int | None
    phones: set[str] = field(default_factory=set)        # keyed hashes, never numbers
    devices: set[str] = field(default_factory=set)
    village: str | None = None                             # place name (as matched)
    lat: float | None = None
    lng: float | None = None
    radius_m: int | None = None
    confidence: str | None = None
    landmarks: dict[str, str] = field(default_factory=dict)  # key → label: "osm:123" → "Thawe durga mata mandir",
                                                             # "type:bridge" → "bridge" (a bare word counts half)
    people: int | None = None
    names: list[str] = field(default_factory=list)
    at: datetime | None = None                             # latest report time
    public_id: str | None = None
    relay_phones: set[str] = field(default_factory=set)    # m27: phones that stopped counting as identity


@dataclass
class Score:
    total: float
    signals: dict[str, float]
    reasons: list[str]
    conflicts: list[str]
    phone_match: bool
    geo_ok: bool
    place_ok: bool


def _metres(a: Household, b: Household) -> float:
    dy = (a.lat - b.lat) * 111_320
    dx = (a.lng - b.lng) * 111_320 * math.cos(math.radians((a.lat + b.lat) / 2))
    return math.hypot(dx, dy)


def _minutes(a: Household, b: Household) -> float | None:
    if a.at is None or b.at is None:
        return None
    return abs((a.at - b.at).total_seconds()) / 60


def score(new: Household, old: Household) -> Score:
    w = get_config().dedupe.weights
    s: dict[str, float] = {}
    reasons: list[str] = []
    conflicts: list[str] = []

    # phone or device: counts only when it matches (and isn't a relay phone, m27)
    shared = (new.phones & old.phones) - new.relay_phones - old.relay_phones
    if shared or (new.devices & old.devices):
        s["phone_or_device"] = 1.0
        reasons.append("same phone" if shared else "same reporter's phone (app)")

    # place: same village 1, fuzzy ≥ 85 → 0.5
    if new.village and old.village:
        if norm(new.village) == norm(old.village):
            s["place"] = 1.0
            reasons.append(f"same village ({old.village})")
        elif fuzz.ratio(norm(new.village), norm(old.village)) >= 85:
            s["place"] = 0.5
            reasons.append(f"similar village name ({new.village} ~ {old.village})")

    # geo: circle overlap, only when both pins are Medium or better
    geo_ok = False
    if None not in (new.lat, old.lat) and new.radius_m and old.radius_m:
        floor = CONF_ORDER[get_config().dedupe.geo_min_confidence]
        if CONF_ORDER.get(new.confidence, 0) >= floor and CONF_ORDER.get(old.confidence, 0) >= floor:
            overlap = max(0.0, 1 - _metres(new, old) / (new.radius_m + old.radius_m))
            if overlap > 0:
                s["geo"] = round(overlap, 3)
                geo_ok = True
                reasons.append(f"circles overlap ({int(_metres(new, old))} m apart)")

    # landmarks: Jaccard of the same mapped features (or names); a bare type ("temple") counts half
    if new.landmarks and old.landmarks:
        both = set(new.landmarks) & set(old.landmarks)
        if both:
            weight = sum(0.5 if x.startswith("type:") else 1.0 for x in both)
            s["landmarks"] = round(weight / len(set(new.landmarks) | set(old.landmarks)), 3)
            reasons.append("same landmarks (" + ", ".join(sorted(old.landmarks[x] for x in both)) + ")")

    # headcount: 1 equal, 0.5 within 2, lower with the gap; a gap never blocks
    if new.people and old.people:
        gap = abs(new.people - old.people)
        hc = 1.0 if gap == 0 else 0.5 if gap <= 2 else max(0.0, 0.5 - 0.1 * (gap - 2))
        if hc:
            s["headcount"] = hc
            reasons.append(f"same headcount ({old.people})" if gap == 0 else f"similar headcount ({new.people} vs {old.people})")
        if gap:
            conflicts.append(f"headcount {new.people} ≠ {old.people}")

    # time: 1 within 30 min, falling to 0 at 12 h
    minutes = _minutes(new, old)
    if minutes is not None:
        decay = get_config().dedupe.time_decay_hours * 60
        t = 1.0 if minutes <= 30 else max(0.0, 1 - (minutes - 30) / (decay - 30))
        if t:
            s["time"] = round(t, 3)
            reasons.append(f"{int(minutes)} min apart" if minutes < 120 else f"{minutes / 60:.0f} h apart")

    total = round(sum(getattr(w, k) * v for k, v in s.items()), 3)
    return Score(total=total, signals=s, reasons=reasons, conflicts=conflicts,
                 phone_match="phone_or_device" in s, geo_ok=geo_ok, place_ok=s.get("place", 0) > 0)
