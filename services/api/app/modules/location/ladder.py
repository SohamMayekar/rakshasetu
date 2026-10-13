"""The location ladder (PRD F-L4): landmark words → a pin with an HONEST circle, and the method in words.
Deterministic rules over the committed OSM gazetteer. The AI (or the keywords) only extracted the words.

    1  match the village/locality (any script, fuzzy) in the incident, preferring the stated district;
       if no village was extracted, scan the text for a known place name (a rule, not AI)
    1b no village matched → a specific name in the words (a campus, a store, the Sea Link — wherever the
       extraction put it) that matches exactly ONE mapped feature pins the report, ~300 m, Medium
    1c nothing there either → the free OSM geocoders (Photon → Nominatim; the database cache first) for an
       address the committed gazetteer cannot hold — a hotel, a building, a street, another state: a venue or
       a street pins ~300–500 m, Medium; a town or a neighbourhood 1.5 km, Low. The service is named on the pin.
    2  for each landmark type mentioned, find mapped landmarks of that type within 2 km of the place
    3  two types with candidates → the closest pair; ≤ 500 m apart → midpoint, ~150 m
       High only if the village matched and it's the only such pair within 1 km, or a landmark matched by name
    4  one type with a single candidate → pin on it, ~300 m, Medium. A landmark the caller NAMED takes the
       nearest feature with that name to the stated place; and a name matching exactly ONE mapped feature
       (wherever the extraction filed it) beats the village circle (step 6)
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
from app.providers import geocode
from app.providers.base import AllProvidersFailed

TYPE_WORD = {"temple": "temple", "mosque": "mosque", "church": "church", "gurdwara": "gurdwara",
             "place_of_worship": "place of worship", "bridge": "bridge", "school": "school", "hospital": "hospital",
             "water_tower": "water tower", "railway_station": "station", "market": "market", "tower": "tower",
             "canal": "canal", "panchayat_bhawan": "panchayat bhawan", "police_station": "police station"}
# The contract lets the model and the rules name one OSM feature with any worship word ("Shankar mandir" comes
# back as temple or place_of_worship, "masjid" as mosque or place_of_worship), and the gazetteer keeps each
# feature under its own OSM type. A name that matches the map is therefore looked for across the family, not
# only under the guessed type — without it, two reports of one family can land on two different temples.
WORSHIP = ("temple", "mosque", "church", "gurdwara", "place_of_worship")
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
    address: str | None = None             # the geocoder's label, when the pin came from one

    def fields(self) -> dict:
        detail = {"step": self.step, "place": self.place, "landmarks": self.landmarks}
        if self.address:
            detail["address"] = self.address
        return {"lat": self.lat, "lng": self.lng, "radius_m": self.radius_m, "location_confidence": self.confidence,
                "location_method": self.method, "location_source": "rule" if self.lat is not None else None,
                "location_detail": detail}


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


def _best_place(places: list, wanted: list[str], want_district: str):
    best, best_score = None, 0
    for p in places:
        names = [p.name, *(p.alt_names or []), p.name_hi or ""]
        for w in wanted:
            score = max(fuzz.ratio(norm(w), norm(n)) for n in names if n)
            score += 3 if want_district and p.district and p.district.lower() == want_district else 0
            if score > best_score:
                best, best_score = p, score
    return best, best_score


def match_place(conn: Connection, incident_id: int, ex: Extraction, report_text: str) -> tuple[object | None, int]:
    """Best fuzzy match of the extracted village (or a place named anywhere in the text). (place, score)."""
    places = _places(conn, incident_id)
    if not places:
        return None, 0
    want_district = (ex.location.district or "").strip().lower()
    floor = get_config().location.village_fuzzy_min
    v = ex.location.village_or_locality
    wanted = [n for n in ([v.latin, v.original] if v else []) if n]
    best, best_score = _best_place(places, wanted, want_district)
    if best_score < floor and v:
        # Callers (and the model) tack a qualifier onto the name — "Andheri East Area", "Vasai West ilaka":
        # when the whole thing matches no place, the name without its trailing words is tried before the scan.
        shortened = [" ".join(w.split()[:cut]) for w in wanted for cut in range(len(w.split()) - 1, 0, -1)]
        best, best_score = _best_place(places, shortened, want_district)
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


def _candidates(conn: Connection, incident_id: int, place, lm_type: str | tuple[str, ...], radius_m: int) -> list:
    types = [lm_type] if isinstance(lm_type, str) else list(lm_type)
    return conn.execute(text(
        "SELECT id, name, name_norm, type, osm_id, detail, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lng,"
        " ST_Distance(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) AS from_place"
        " FROM landmarks WHERE incident_id = :i AND type = ANY(:types)"
        " AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :r)"
        " ORDER BY from_place"), {"i": incident_id, "types": types, "lat": place.lat, "lng": place.lng,
                                  "r": radius_m}).all()


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
    # a name matching exactly one mapped feature (city-wide); the village itself is never its own landmark
    one = _named_on_the_map(conn, incident_id, ex, exclude=place.name if place else None)

    if place is None:
        if one is not None:
            return Located(lat=one.lat, lng=one.lng, radius_m=radius.one_landmark, confidence="medium", step=4,
                           method=f"Medium · {_km(radius.one_landmark)} · matched {_label(one)} by name"
                                  f" (no village named)",
                           landmarks=[_lm_dict(one)], district_id=one.district_id)
        geo = _geocoded_pin(conn, incident_id, ex, radius, precise_only=False)
        if geo is not None:
            return geo
        district = _district_named(conn, incident_id, ex, report_text)
        if district:
            return Located(lat=district.lat, lng=district.lng, radius_m=radius.district, confidence="very_low",
                           method=f"Very low · {_km(radius.district)} · district only: {district.name}", step=7,
                           district_id=district.id, flags=["needs_location"])
        return Located(district_id=district_hint, flags=["needs_location"])

    where = place.name
    found: dict[str, list] = {}
    named: dict[str, int] = {}
    for lm in ex.location.landmarks:
        cands = _candidates(conn, incident_id, place, lm.type, cfg.landmark_search_radius_m)
        if lm.name:   # a landmark named by the caller ("Durga mandir") narrows the candidates if one matches
            want = norm(re.sub(r"\b(mandir|temple|masjid|school|pul|bridge)\b", "", lm.name, flags=re.I))
            by_name = [c for c in cands if c.name_norm and want and fuzz.partial_ratio(want, c.name_norm) >= 85]
            if not by_name and lm.type in WORSHIP:
                # Not under the guessed type: a name that matches the map (any worship word) wins over it.
                by_name = [c for c in _candidates(conn, incident_id, place, WORSHIP, cfg.landmark_search_radius_m)
                           if c.name_norm and want and fuzz.partial_ratio(want, c.name_norm) >= 85]
            if by_name:
                # The candidates are ordered by distance from the stated place, so the nearest name match is the
                # reading we pin: "DMart in Powai" is the DMart nearest Powai, not the one 1.3 km away (and a
                # node and a way for one store, both mapped, do not turn one store into two candidates).
                cands, named[lm.type] = [by_name[0]], len(by_name)
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
                            best = (d, a, b, ta, tb)
        d, a, b, ta, tb = best
        if d <= cfg.pair_max_gap_m:
            mid = ((a.lat + b.lat) / 2, (a.lng + b.lng) / 2)
            others = {(x.osm_id, y.osm_id) for x in found[ta] for y in found[tb]
                      if _m((x.lat, x.lng), (y.lat, y.lng)) <= cfg.pair_max_gap_m
                      and _m(mid, ((x.lat + y.lat) / 2, (x.lng + y.lng) / 2)) <= cfg.high_requires_unique_pair_within_m}
            unique = len(others) == 1
            high = (score >= 90 and unique) or named.get(ta) or named.get(tb)
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
            what = (f"matched {_label(c)}, the nearest of {named[t]} with that name near {where}"
                    if named.get(t, 0) > 1 else
                    f"matched the only {TYPE_WORD.get(t, t)} mapped near {where}: {_label(c)}")
            return Located(lat=c.lat, lng=c.lng, radius_m=radius.one_landmark, confidence="medium", step=4,
                           method=f"Medium · {_km(radius.one_landmark)} · {what}", landmarks=[_lm_dict(c)], **base)
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

    # Step 6: village only — unless something more precise the words gave beats a village circle: a mapped
    # feature with exactly that name, else the free geocoders for what the gazetteer does not hold.
    if one is not None:
        return Located(lat=one.lat, lng=one.lng, radius_m=radius.one_landmark, confidence="medium", step=4,
                       method=f"Medium · {_km(radius.one_landmark)} · matched {_label(one)} by name, in {where}",
                       landmarks=[_lm_dict(one)], **{**base, "district_id": one.district_id or place.district_id})
    geo = _geocoded_pin(conn, incident_id, ex, radius, precise_only=True)
    if geo is not None:
        return geo
    r = min(place.radius_m or radius.village, radius.village)
    return Located(lat=place.lat, lng=place.lng, radius_m=r, confidence="low", step=6,
                   method=f"Low · {_km(r)} · village only: {where}{place_note}", **base)


def _geocode_queries(ex: Extraction, *, include_area: bool) -> list[str]:
    """What to ask a geocoder, most specific first: the address the model wrote, each named landmark with the
    area, and — when nothing more specific came (no place matched) — the area itself. One call per text, and
    every answer is cached, so a repeat never costs a second request."""
    out: list[str] = []
    a = ex.location.address
    if a is not None and a.text.strip():
        out.append(a.text.strip())
    v = ex.location.village_or_locality
    area = v.latin if v else None
    state = ex.location.state
    for lm in ex.location.landmarks:
        if lm.name:
            out.append(", ".join(p for p in (lm.name, area, state) if p))
    if include_area and area:
        out.append(", ".join(p for p in (area, ex.location.district, state) if p))
    seen, unique = set(), []
    for q in out:
        if q.lower() not in seen:
            seen.add(q.lower())
            unique.append(q)
    return unique[:4]


def _geocoded_pin(conn: Connection, incident_id: int, ex: Extraction, radius, *, precise_only: bool):
    """Last resort for anything the committed gazetteer does not hold (a hotel, a building, a street, a peak,
    another state): the free OSM geocoders, cache first, one query at a time — the address, then a named
    landmark with the area, then the area itself (the last only when `precise_only` is off). An answer that
    names another state than the report's is dropped (a street exists in two states). A venue or a street pins
    Medium with the service named; a town or neighbourhood 1.5 km, Low. Never raises."""
    for q in _geocode_queries(ex, include_area=not precise_only):
        try:
            res = geocode.geocode(q)
        except AllProvidersFailed as e:
            if e.attempts and all(a.get("outcome", "").startswith("failed") for a in e.attempts):
                return None                   # the network, not the words: every query would fail the same way
            continue                          # this text found nothing; the next query may
        hit: geocode.Hit = res.value
        if hit.kind == "area" or (precise_only and hit.kind == "settlement"):
            continue
        if ex.location.state and norm(ex.location.state) not in norm(hit.label):
            continue                          # same name, another state: not this report's place
        cached = bool(res.attempts) and res.attempts[0].get("outcome") == "cached"
        if hit.kind == "settlement":
            conf, r = "low", radius.village
        else:
            base = radius.one_landmark if hit.kind == "venue" else 500
            conf, r = "medium", min(max(hit.extent_m or base, radius.two_landmarks), 1000)
        district_id = conn.execute(text(
            "SELECT id FROM districts WHERE incident_id = :i AND ST_Covers(boundary, ST_SetSRID(ST_MakePoint(:lng,"
            " :lat), 4326)::geography) LIMIT 1"), {"i": incident_id, "lng": hit.lng, "lat": hit.lat}).scalar()
        outside = "" if district_id else " · outside the mapped districts"
        return Located(lat=hit.lat, lng=hit.lng, radius_m=r, confidence=conf,
                       step=4 if conf == "medium" else 6, district_id=district_id, address=hit.label,
                       method=f"{CONF_WORD[conf]} · {_km(r)} · geocoded “{hit.label}” "
                              f"({res.provider}{', cached' if cached else ''}){outside}")
    return None


def _district_named(conn: Connection, incident_id: int, ex: Extraction, report_text: str):
    rows = conn.execute(text("SELECT id, name, ST_Y(centroid::geometry) AS lat, ST_X(centroid::geometry) AS lng"
                             " FROM districts WHERE incident_id = :i"), {"i": incident_id}).all()
    said = (ex.location.district or "") + " " + (report_text or "")
    for d in rows:
        if re.search(rf"\b{re.escape(d.name)}\b", said, re.IGNORECASE):
            return d
    return None


def _named_on_the_map(conn: Connection, incident_id: int, ex: Extraction, exclude: str | None = None):
    """A specific name in the words when no village matched ("Rajiv Gandhi Institute of Technology", "the Sea
    Link"; the model often puts such a place in the village field): the one mapped feature with that name pins
    the report, with its district. The whole name must match it (not a substring: "Thawe" sits inside "Thawe
    durga mata mandir" and is not a pin). Two places with that name (fourteen DMarts in one city) stay for a
    person — the name alone, with nothing else to go on, is not enough to choose between them. `exclude` is the
    village that already matched: naming it is not naming a landmark (a station that carries the village's own
    name must not beat the village circle)."""
    wants = []
    v = ex.location.village_or_locality
    if v:
        wants += [v.latin, v.original]
    wants += [lm.name for lm in ex.location.landmarks if lm.name]
    skip = norm(exclude or "")
    names = []
    for want in wants:
        w = norm(re.sub(r"\b(mandir|temple|masjid|school|pul|bridge)\b", "", want or "", flags=re.I))
        if len(w) >= 4 and not (skip and fuzz.ratio(w, skip) >= 90):
            names.append(w)
    if not names:
        return None
    rows = conn.execute(text(
        "SELECT id, district_id, name, name_norm, type, osm_id, detail, ST_Y(geom::geometry) AS lat,"
        " ST_X(geom::geometry) AS lng FROM landmarks WHERE incident_id = :i AND name_norm IS NOT NULL"),
        {"i": incident_id}).all()
    hits = [r for r in rows if any(fuzz.ratio(n, r.name_norm) >= 90 for n in names)]
    clusters: list[list] = []
    for r in hits:                                  # a node and a way for one place count once
        for cl in clusters:
            if any(_m((r.lat, r.lng), (c.lat, c.lng)) <= 200 for c in cl):
                cl.append(r)
                break
        else:
            clusters.append([r])
    return clusters[0][0] if len(clusters) == 1 else None
