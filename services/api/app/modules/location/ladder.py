"""The location ladder (PRD F-L4): landmark words → a pin with an HONEST circle, and the method in words.
Deterministic rules over the committed OSM gazetteer. The AI (or the keywords) only extracted the words.

    1  match the village/locality (any script, fuzzy) in the incident, preferring the stated district;
       if no village was extracted, scan the text for a known place name (a rule, not AI)
    2  for each landmark type mentioned, find mapped landmarks of that type within 2 km of the place
    3  two types with candidates → the closest pair; ≤ 500 m apart → midpoint, ~150 m
       High only if the village matched and it's the only such pair within 1 km, or a landmark matched by name
    4  one type with a single candidate → pin on it, ~300 m, Medium
    5  several candidates of one type, all within 500 m → their centroid, a circle covering them (≤ 1 km);
       spread wider than 500 m → never averaged (P1 #12): fall back to the village
    6  village only → the village point, ~1.5 km, Low (dashed)
    7  district only → the district centroid, ~15 km, Very low, needs_location
    8  nothing usable → no pin; the case goes to "Needs location" and is never dropped

Relations like "behind" or "opposite" are NOT used for geometry; the circle carries that uncertainty.
Radii and distances are the team's constants in rakshasetu.config.yaml.
"""

import math
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz
from sqlalchemy import Connection, text

from app.config import get_config
from app.contracts import Extraction
from app.modules.location.names import norm
from app.pipeline.keywords import DEVANAGARI

TYPE_WORD = {"temple": "temple", "mosque": "mosque", "church": "church", "gurdwara": "gurdwara",
             "place_of_worship": "place of worship", "bridge": "bridge", "school": "school", "hospital": "hospital",
             "water_tower": "water tower", "railway_station": "station", "market": "market", "tower": "tower",
             "canal": "canal", "panchayat_bhawan": "panchayat bhawan", "police_station": "police station"}
CONF_WORD = {"high": "High", "medium": "Medium", "low": "Low", "very_low": "Very low"}


@dataclass
class Located:
    lat: float | None = None
    lng: float | None = None
    radius_m: int | None = None
    confidence: str | None = None          # high | medium | low | very_low | None (no pin)
    method: str = "No location yet: needs a person"
    step: int = 8
    district_id: int | None = None
    place: dict | None = None
    landmarks: list[dict] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def fields(self) -> dict:
        return {"lat": self.lat, "lng": self.lng, "radius_m": self.radius_m, "location_confidence": self.confidence,
                "location_method": self.method, "location_source": "rule" if self.lat is not None else None,
                "location_detail": {"step": self.step, "place": self.place, "landmarks": self.landmarks}}


def _m(a: tuple[float, float], b: tuple[float, float]) -> float:
    dy = (a[0] - b[0]) * 111_320
    dx = (a[1] - b[1]) * 111_320 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dx, dy)


def _km(m: float) -> str:
    return f"{m / 1000:.1f} km".replace(".0 km", " km") if m >= 1000 else f"{int(round(m, -1))} m"


def _places(conn: Connection, incident_id: int) -> list:
    return conn.execute(text(
        "SELECT p.id, p.name, p.name_hi, p.alt_names, p.name_norm, p.type, p.district_id, p.radius_m, d.name AS district,"
        " ST_Y(p.geom::geometry) AS lat, ST_X(p.geom::geometry) AS lng"
        " FROM places p LEFT JOIN districts d ON d.id = p.district_id WHERE p.incident_id = :i"), {"i": incident_id}).all()


def match_place(conn: Connection, incident_id: int, ex: Extraction, report_text: str) -> tuple[object | None, int]:
    """Best fuzzy match of the extracted village (or a place named anywhere in the text). (place, score)."""
    places = _places(conn, incident_id)
    if not places:
        return None, 0
    want_district = (ex.location.district or "").strip().lower()
    floor = get_config().location.village_fuzzy_min
    v = ex.location.village_or_locality
    wanted = [n for n in ([v.latin, v.original] if v else []) if n]
    best, best_score = None, 0
    for p in places:
        names = [p.name, *(p.alt_names or []), p.name_hi or ""]
        for w in wanted:
            score = max(fuzz.ratio(norm(w), norm(n)) for n in names if n)
            score += 3 if want_district and p.district and p.district.lower() == want_district else 0
            if score > best_score:
                best, best_score = p, score
    if best_score >= floor:
        return best, min(best_score, 100)
    # Gazetteer scan (a rule): a known place name anywhere in the text, word by word. "Gopalganj district"
    # names a district, not the town, so "<name> district/zila" is left to step 7.
    scan_text = re.sub(r"\S+\s+(?:district|zila|jila|zilla|ज़िला|जिला)", " ", report_text or "", flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z]+|[ऀ-ॿ]+", scan_text)
    # Two-word names first: "Sion Koliwada" is one place; "Koliwada" alone is many.
    grams = [" ".join(words[i:i + n]) for n in (2, 1) for i in range(len(words) - n + 1)]
    # Marathi joins a case ending to the name ("चेंबूरला" = to Chembur, "धारावीत" = in Dharavi): try it without.
    grams += [w for w in (re.sub(r"(?:ला|त|मध्ये|मधे|च्या|ची|चा|हून)$", "", w) for w in words if DEVANAGARI.match(w)) if w]
    for g in grams:   # in the order above, so the longest name said wins
        for p in places:
            if len(p.name_norm) >= 4 and fuzz.ratio(norm(g), p.name_norm) >= 92:
                return p, 92
    return None, 0


def _candidates(conn: Connection, incident_id: int, place, lm_type: str, radius_m: int) -> list:
    return conn.execute(text(
        "SELECT id, name, name_norm, type, osm_id, detail, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng,"
        " ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS from_place"
        " FROM landmarks WHERE incident_id = :i AND type = :t"
        " AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :r)"
        " ORDER BY from_place"), {"i": incident_id, "t": lm_type, "lat": place.lat, "lng": place.lng, "r": radius_m}).all()


def _lm_dict(r) -> dict:
    return {"id": r.id, "name": r.name, "type": r.type, "osm_id": r.osm_id, "lat": r.lat, "lng": r.lng}


def _label(r) -> str:
    return r.name or (f"{TYPE_WORD.get(r.type, r.type)} ({r.detail} road)" if r.type == "bridge" and r.detail
                      else TYPE_WORD.get(r.type, r.type))


def resolve(conn: Connection, incident_id: int, ex: Extraction, report_text: str,
            district_hint: int | None = None) -> Located:
    cfg = get_config().location
    radius = cfg.radius_m
    place, score = match_place(conn, incident_id, ex, report_text)

    if place is None:
        district = _district_named(conn, incident_id, ex, report_text)
        if district:
            return Located(lat=district.lat, lng=district.lng, radius_m=radius.district, confidence="very_low",
                           method=f"Very low · {_km(radius.district)} · district only: {district.name}", step=7,
                           district_id=district.id, flags=["needs_location"])
        return Located(district_id=district_hint, flags=["needs_location"])

    where = place.name
    found: dict[str, list] = {}
    named: dict[str, bool] = {}
    for lm in ex.location.landmarks:
        cands = _candidates(conn, incident_id, place, lm.type, cfg.landmark_search_radius_m)
        if lm.name:   # a landmark named by the caller ("Durga mandir") narrows the candidates if one matches
            want = norm(re.sub(r"\b(mandir|temple|masjid|school|pul|bridge)\b", "", lm.name, flags=re.I))
            by_name = [c for c in cands if c.name_norm and want and fuzz.partial_ratio(want, c.name_norm) >= 85]
            if by_name:
                cands, named[lm.type] = by_name, True
        if cands:
            found[lm.type] = cands
    base = dict(district_id=place.district_id, place={"id": place.id, "name": place.name, "lat": place.lat, "lng": place.lng})

    # Step 3: two landmark types → the closest pair.
    types = list(found)
    if len(types) >= 2:
        best = None
        for i, ta in enumerate(types):
            for tb in types[i + 1:]:
                for a in found[ta]:
                    for b in found[tb]:
                        d = _m((a.lat, a.lng), (b.lat, b.lng))
                        if best is None or d < best[0]:
                            best = (d, a, b)
        d, a, b = best
        if d <= cfg.pair_max_gap_m:
            mid = ((a.lat + b.lat) / 2, (a.lng + b.lng) / 2)
            others = {(x.osm_id, y.osm_id) for x in found[a.type] for y in found[b.type]
                      if _m((x.lat, x.lng), (y.lat, y.lng)) <= cfg.pair_max_gap_m
                      and _m(mid, ((x.lat + y.lat) / 2, (x.lng + y.lng) / 2)) <= cfg.high_requires_unique_pair_within_m}
            unique = len(others) == 1
            high = (score >= 90 and unique) or named.get(a.type) or named.get(b.type)
            conf = "high" if high else "medium"
            why = "" if high else (" · another such pair nearby" if not unique else " · village match is approximate")
            return Located(lat=mid[0], lng=mid[1], radius_m=radius.two_landmarks, confidence=conf, step=3,
                           method=f"{CONF_WORD[conf]} · {_km(radius.two_landmarks)} · matched {_label(a)} + {_label(b)},"
                                  f" {_km(d)} apart, in {where}{why}",
                           landmarks=[_lm_dict(a), _lm_dict(b)], **base)

    # Steps 4–5: one landmark type.
    for t in types:
        cands = found[t]
        features = {c.osm_id for c in cands}
        if len(features) == 1:
            c = cands[0]   # the nearest point (a long bridge's nearest part)
            return Located(lat=c.lat, lng=c.lng, radius_m=radius.one_landmark, confidence="medium", step=4,
                           method=f"Medium · {_km(radius.one_landmark)} · matched the only {TYPE_WORD.get(t, t)}"
                                  f" mapped near {where}: {_label(c)}", landmarks=[_lm_dict(c)], **base)
        lat = sum(c.lat for c in cands) / len(cands)
        lng = sum(c.lng for c in cands) / len(cands)
        spread = max(_m((lat, lng), (c.lat, c.lng)) for c in cands)
        widest = max(_m((a.lat, a.lng), (b.lat, b.lng)) for a in cands for b in cands)
        if widest <= cfg.pair_max_gap_m:
            r = min(max(int(spread) + 100, radius.one_landmark), radius.many_candidates_cap)
            conf = "medium" if r <= 500 else "low"
            return Located(lat=lat, lng=lng, radius_m=r, confidence=conf, step=5,
                           method=f"{CONF_WORD[conf]} · {_km(r)} · {len(features)} {TYPE_WORD.get(t, t)}s mapped near"
                                  f" {where}, all within {_km(widest)}", landmarks=[_lm_dict(c) for c in cands], **base)
        place_note = f" · {len(features)} {TYPE_WORD.get(t, t)}s near {where} are {_km(widest)} apart: not averaged"
        break
    else:
        place_note = ""

    # Step 6: village only.
    r = min(place.radius_m or radius.village, radius.village)
    return Located(lat=place.lat, lng=place.lng, radius_m=r, confidence="low", step=6,
                   method=f"Low · {_km(r)} · village only: {where}{place_note}", **base)


def _district_named(conn: Connection, incident_id: int, ex: Extraction, report_text: str):
    rows = conn.execute(text("SELECT id, name, ST_Y(centroid::geometry) AS lat, ST_X(centroid::geometry) AS lng"
                             " FROM districts WHERE incident_id = :i"), {"i": incident_id}).all()
    said = (ex.location.district or "") + " " + (report_text or "")
    for d in rows:
        if re.search(rf"\b{re.escape(d.name)}\b", said, re.IGNORECASE):
            return d
    return None
