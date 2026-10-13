"""Address text → a point on the map, from the free OpenStreetMap geocoders: Photon → Nominatim.

The committed gazetteer answers first: it is deterministic, offline and exact for the demo packs. This chain is
the last resort for everything the gazetteer does not hold — a hotel, a building, a street, a peak, another
state — so a caller can say any place and the desk still gets a pin with an honest circle. No keys, no card:
both are public OSM services, and each answer is cached in `geocode_cache`, so one address text is never sent
twice (cleared with the database on a demo reset, like the extraction cache). Tests run in fixture mode:
cached results only, never the network. A Google Geocoding adapter (an API key, a bill) would slot into this
chain the same way if the team ever wants one.

Honesty: every pin names the service that answered ("photon", "nominatim"), or says "(cached)" for a remembered
answer — never a bare coordinate with no attribution.
"""

import hashlib
import json
import math

import httpx
from sqlalchemy import text

from app.config import get_config
from app.db import get_engine
from app.providers import usage
from app.providers.base import (
    AllProvidersFailed,
    ChainResult,
    ProviderFailed,
    ProviderUnavailable,
    api_key,
    mode,
    run_chain,
)

TIMEOUT = httpx.Timeout(5.0, connect=3.0)
UA = {"User-Agent": "rakshasetu-demo/1.0 (district rescue desk; OSM data, ODbL)"}   # Nominatim's policy

SETTLEMENT = {"city", "town", "village", "hamlet", "suburb", "neighbourhood", "locality", "quarter", "borough",
              "city_block", "district", "municipality", "isolated_dwelling", "municipal_corporation"}
AREA = {"state", "region", "county", "country", "province", "state_district", "administrative"}

# Google's own vocabulary (types / location_type) maps onto the same four kinds.
GOOGLE_STREET = {"route"}
GOOGLE_SETTLEMENT = {"locality", "sublocality", "sublocality_level_1", "neighborhood", "postal_town",
                     "colloquial_area", "postal_code"}
GOOGLE_AREA = {"country", "administrative_area_level_1", "administrative_area_level_2", "administrative_area_level_3"}


def kind_of_google(types: list[str] | None) -> str:
    t = set(types or [])
    if t & GOOGLE_AREA:
        return "area"
    if t & GOOGLE_STREET:
        return "street"
    if t & GOOGLE_SETTLEMENT:
        return "settlement"
    return "venue"          # street_address, premise, point_of_interest, establishment…


class Hit:
    """What a geocoder found: a point, a label to show the officer, how precise it is, and the mapped extent."""
    __slots__ = ("lat", "lng", "label", "kind", "extent_m")

    def __init__(self, lat: float, lng: float, label: str, kind: str, extent_m: int | None = None):
        self.lat, self.lng, self.label, self.kind, self.extent_m = lat, lng, label, kind, extent_m

    def as_dict(self) -> dict:
        return {"lat": self.lat, "lng": self.lng, "label": self.label, "kind": self.kind, "extent_m": self.extent_m}

    @classmethod
    def from_dict(cls, d: dict) -> "Hit":
        return cls(d["lat"], d["lng"], d["label"], d["kind"], d.get("extent_m"))


def kind_of(key: str | None, value: str | None) -> str:
    """venue (a building, shop, hotel, station…), street, settlement (a town/neighbourhood) or area (a state)."""
    if key == "place":
        if value in AREA:
            return "area"
        return "settlement" if value in SETTLEMENT else "venue"
    if key == "highway":
        return "street"
    return "venue"


def _metres(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    dy = (lat2 - lat1) * 111_320
    dx = (lng2 - lng1) * 111_320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot(dx, dy)


def _extent_m(lat: float, lng: float, box: list | None, *, order: str) -> int | None:
    """Half the diagonal of a bounding box in metres. Photon gives [west, south, east, north]; Nominatim gives
    [south, north, west, east] — sometimes as strings."""
    if not box or len(box) != 4:
        return None
    try:
        box = [float(x) for x in box]
    except (TypeError, ValueError):
        return None
    s, n, w, e = (box[1], box[3], box[0], box[2]) if order == "wsen" else (box[0], box[1], box[2], box[3])
    if not (n > s and e > w):
        return None
    return int(_metres(s, w, n, e) / 2)


def _label(parts: list[str | None]) -> str:
    return ", ".join(p for p in parts if p)


def photon(query: str) -> tuple[Hit, str]:
    usage.check("photon")
    try:
        r = httpx.get("https://photon.komoot.io/api", params={"q": query, "limit": 1, "lang": "en"},
                      headers=UA, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise ProviderFailed(f"network: {e}") from e
    usage.record("photon")
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:120]}")
    features = (r.json().get("features") or [])
    p = (features[0].get("properties") or {}) if features else {}
    coords = (features[0].get("geometry") or {}).get("coordinates") if features else None
    if not p or not coords or len(coords) != 2:
        raise ProviderUnavailable("no result")
    lat, lng = float(coords[1]), float(coords[0])
    label = _label([p.get("name"), p.get("street"), p.get("city") or p.get("district"), p.get("state"),
                    p.get("country")]) or query
    return Hit(round(lat, 6), round(lng, 6), label, kind_of(p.get("osm_key"), p.get("osm_value")),
               _extent_m(lat, lng, p.get("extent"), order="wsen")), "photon"


def nominatim(query: str) -> tuple[Hit, str]:
    usage.check("nominatim")
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/search",
                      params={"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1}, headers=UA,
                      timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise ProviderFailed(f"network: {e}") from e
    usage.record("nominatim")
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:120]}")
    rows = r.json() or []
    if not rows:
        raise ProviderUnavailable("no result")
    row = rows[0]
    try:
        lat, lng = float(row["lat"]), float(row["lon"])
    except (KeyError, TypeError, ValueError) as e:
        raise ProviderFailed(f"no coordinates: {e}") from e
    return Hit(round(lat, 6), round(lng, 6), row.get("display_name") or query,
               kind_of(row.get("class"), row.get("type")),
               _extent_m(lat, lng, row.get("boundingbox"), order="snwe")), "nominatim"


def google(query: str) -> tuple[Hit, str]:
    """The team's Google Maps key (Geocoding API), when one is set: the most precise of the three, and the only
    one that answers at a doorway. First in the chain; without the key (or over its cap) it is skipped and the
    free OSM services take over."""
    key = api_key("google_geocoding")
    if not key:
        raise ProviderUnavailable("no GOOGLE_MAPS_API_KEY")
    usage.check("google_geocoding")
    try:
        r = httpx.get("https://maps.googleapis.com/maps/api/geocode/json",
                      params={"address": query, "key": key, "language": "en"}, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise ProviderFailed(f"network: {e}") from e
    usage.record("google_geocoding")
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:120]}")
    try:
        body = r.json()
    except ValueError as e:
        raise ProviderFailed(f"unreadable output: {e}") from e
    status = body.get("status", "")
    if status == "ZERO_RESULTS":
        raise ProviderUnavailable("no result")
    if status != "OK":
        raise ProviderFailed(f"{status}: {str(body.get('error_message', ''))[:120]}")
    row = (body.get("results") or [{}])[0]
    geometry = row.get("geometry") or {}
    try:
        loc = geometry["location"]
        lat, lng = float(loc["lat"]), float(loc["lng"])
    except (KeyError, TypeError, ValueError) as e:
        raise ProviderFailed(f"no coordinates: {e}") from e
    extent = None
    vp = geometry.get("viewport") or {}
    try:
        extent = int(_metres(vp["southwest"]["lat"], vp["southwest"]["lng"],
                             vp["northeast"]["lat"], vp["northeast"]["lng"]) / 2)
    except (KeyError, TypeError, ValueError):
        extent = None
    return Hit(round(lat, 6), round(lng, 6), row.get("formatted_address") or query,
               kind_of_google(row.get("types")), extent), "google_geocoding"


ADAPTERS = {"google_geocoding": google, "photon": photon, "nominatim": nominatim}


def text_sha(q: str) -> str:
    return hashlib.sha256(q.strip().lower().encode()).hexdigest()


def cached(q: str) -> tuple[Hit, str] | None:
    with get_engine().connect() as c:
        r = c.execute(text("SELECT provider, result FROM geocode_cache WHERE text_sha256 = :h"
                           " ORDER BY created_at DESC LIMIT 1"), {"h": text_sha(q)}).one_or_none()
    return (Hit.from_dict(r.result), r.provider) if r else None


def remember(q: str, provider: str, hit: Hit) -> None:
    with get_engine().begin() as c:
        c.execute(text("INSERT INTO geocode_cache (text_sha256, provider, result)"
                       " VALUES (:h, :p, CAST(:r AS jsonb)) ON CONFLICT DO NOTHING"),
                  {"h": text_sha(q), "p": provider, "r": json.dumps(hit.as_dict())})


def geocode(q: str) -> ChainResult:
    """The chain, cache first. Raises AllProvidersFailed when nothing can answer (the ladder then carries on)."""
    miss = [{"provider": "cache", "outcome": "miss"}]
    hit = cached(q)
    if hit is not None:
        return ChainResult(value=hit[0], provider=hit[1], model=hit[1], latency_ms=0,
                           attempts=[{"provider": hit[1], "outcome": "cached"}])
    names = list(get_config().providers.get("geocode") or [])
    if mode() == "fixture":
        raise AllProvidersFailed(miss)           # tests: cached results only, never the network
    if not names:
        raise AllProvidersFailed(miss)           # the team switched geocoding off (providers.geocode: [])
    res = run_chain(names, lambda n: ADAPTERS[n](q))
    remember(q, res.provider, res.value)
    return res
