"""Build the BR gazetteer (places + landmarks) from OpenStreetMap, once, and commit it (PRD F-L4).

    python scripts/import_osm.py --pbf /path/to/bihar.osm.pbf         # an extract file (used for this build)
    python scripts/import_osm.py --overpass                             # Overpass API (needs open internet)

Writes data/scenarios/BR/gazetteer/{places.csv, landmarks.csv, districts.geojson, meta.json}. No live geocoding
per report: the ladder only ever reads these committed rows. OSM data © OpenStreetMap contributors, ODbL.
Needs the optional tools: pip install osmium shapely (dev only; not in the API image).
"""

import argparse
import csv
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "scenarios" / "BR" / "gazetteer"
BUFFER_DEG = 0.02            # ~2 km around each district, so landmarks just over the line still count
PLACE_TYPES = {"village", "hamlet", "town", "suburb", "neighbourhood", "locality", "isolated_dwelling", "city"}
RELIGION = {"hindu": "temple", "muslim": "mosque", "islam": "mosque", "christian": "church", "sikh": "gurdwara"}


def landmark_type(tags) -> str | None:
    if tags.get("amenity") == "place_of_worship":
        return RELIGION.get(tags.get("religion", ""), "place_of_worship")
    if tags.get("bridge") in ("yes", "viaduct", "aqueduct") or tags.get("man_made") == "bridge":
        return "bridge"
    if tags.get("amenity") in ("school", "college"):
        return "school"
    if tags.get("amenity") in ("hospital", "clinic"):
        return "hospital"
    if tags.get("man_made") == "water_tower" or (tags.get("man_made") == "storage_tank" and tags.get("content") == "water"):
        return "water_tower"
    if tags.get("railway") in ("station", "halt"):
        return "railway_station"
    if tags.get("amenity") == "marketplace":
        return "market"
    if tags.get("man_made") in ("tower", "mast") and tags.get("tower:type") == "communication":
        return "tower"
    return None


def from_pbf(pbf: Path, district_names: list[str]):
    import osmium
    from shapely import wkb
    from shapely.geometry import Point

    wkbf = osmium.geom.WKBFactory()
    districts: dict[str, object] = {}

    class Boundaries(osmium.SimpleHandler):
        def area(self, a):
            t = a.tags
            if t.get("boundary") == "administrative" and t.get("admin_level") == "5" and t.get("name") in district_names:
                districts[t.get("name")] = wkb.loads(wkbf.create_multipolygon(a), hex=True)

    Boundaries().apply_file(str(pbf), locations=True, idx="flex_mem")
    missing = set(district_names) - set(districts)
    if missing:
        sys.exit(f"district boundaries not found in the extract: {sorted(missing)}")
    buffered = {n: g.buffer(BUFFER_DEG) for n, g in districts.items()}

    def district_of(lon, lat):
        p = Point(lon, lat)
        for name, g in districts.items():
            if g.contains(p):
                return name
        for name, g in buffered.items():
            if g.contains(p):
                return name
        return None

    places, landmarks = [], []

    class Features(osmium.SimpleHandler):
        def node(self, n):
            if not n.location.valid():
                return
            self._feature("node", n.id, n.tags, n.location.lon, n.location.lat)

        def way(self, w):
            lt = landmark_type(w.tags)
            pl = w.tags.get("place") in PLACE_TYPES
            if not (lt or pl):
                return
            try:
                pts = [(nd.lon, nd.lat) for nd in w.nodes if nd.location.valid()]
            except Exception:
                return
            if not pts:
                return
            if lt == "bridge":
                # A long bridge (or causeway) is sampled every ~150 m along its length, so "near the bridge"
                # is measured to its nearest part, not to one point that may be far from the caller's end.
                for part, (lon, lat) in enumerate(sample_line(pts, 150.0)):
                    self._feature("way", w.id, w.tags, lon, lat, part)
            else:
                lon, lat = sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)
                self._feature("way", w.id, w.tags, lon, lat)

        def _feature(self, kind, osm_id, tags, lon, lat, part=0):
            lt = landmark_type(tags)
            is_place = tags.get("place") in PLACE_TYPES and tags.get("name")
            if not (lt or is_place):
                return
            d = district_of(lon, lat)
            if d is None:
                return
            if is_place:
                alts = [tags.get(k) for k in ("alt_name", "old_name", "name:en") if tags.get(k)]
                places.append({"osm_type": kind, "osm_id": osm_id, "name": tags.get("name"),
                               "name_hi": tags.get("name:hi") or "", "alt_names": ";".join(alts),
                               "type": tags.get("place"), "district": d, "lat": round(lat, 6), "lon": round(lon, 6)})
            if lt:
                landmarks.append({"osm_type": kind, "osm_id": osm_id, "part": part, "name": tags.get("name") or "",
                                  "type": lt, "religion": tags.get("religion") or "",
                                  "detail": tags.get("highway") or tags.get("railway") or tags.get("waterway") or "",
                                  "district": d, "lat": round(lat, 6), "lon": round(lon, 6)})

    Features().apply_file(str(pbf), locations=True, idx="flex_mem")
    return districts, places, landmarks


def _metres(a, b) -> float:
    dy = (a[1] - b[1]) * 111_000
    dx = (a[0] - b[0]) * 111_000 * math.cos(math.radians(a[1]))
    return math.hypot(dx, dy)


def sample_line(pts: list[tuple[float, float]], every_m: float) -> list[tuple[float, float]]:
    """Points along a polyline: both ends plus one every `every_m` metres. A short bridge gives its middle."""
    total = sum(_metres(a, b) for a, b in zip(pts, pts[1:], strict=False))
    if total <= every_m:
        return [pts[len(pts) // 2]]
    out, walked, target = [pts[0]], 0.0, every_m
    for a, b in zip(pts, pts[1:], strict=False):
        seg = _metres(a, b)
        while seg > 0 and walked + seg >= target:
            f = (target - walked) / seg
            out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            target += every_m
        walked += seg
    out.append(pts[-1])
    return [(round(x, 6), round(y, 6)) for x, y in out]


def collapse_bridges(landmarks: list[dict], within_m: float = 30.0) -> list[dict]:
    """Several mapped segments of one bridge become one landmark."""
    kept, bridges = [], []
    for lm in landmarks:
        if lm["type"] != "bridge":
            kept.append(lm)
            continue
        for b in bridges:
            dy = (lm["lat"] - b["lat"]) * 111_000
            dx = (lm["lon"] - b["lon"]) * 111_000 * math.cos(math.radians(b["lat"]))
            if math.hypot(dx, dy) <= within_m:
                break
        else:
            bridges.append(lm)
    return kept + bridges


def write(districts, places, landmarks, source: dict) -> None:
    from shapely.geometry import mapping
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "places.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(places[0]))
        w.writeheader()
        w.writerows(sorted(places, key=lambda p: (p["district"], p["name"])))
    with (OUT / "landmarks.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(landmarks[0]))
        w.writeheader()
        w.writerows(sorted(landmarks, key=lambda x: (x["district"], x["type"], x["osm_id"])))
    feats = [{"type": "Feature", "properties": {"name": n},
              "geometry": mapping(g.simplify(0.002, preserve_topology=True))} for n, g in districts.items()]
    (OUT / "districts.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    counts = {"places": len(places), "landmarks": {}}
    for lm in landmarks:
        counts["landmarks"][lm["type"]] = counts["landmarks"].get(lm["type"], 0) + 1
    (OUT / "meta.json").write_text(json.dumps({**source, "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
                                               "counts": counts, "licence": "ODbL, © OpenStreetMap contributors"},
                                              indent=2) + "\n")
    print(json.dumps(counts, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--pbf", type=Path)
    src.add_argument("--overpass", action="store_true")
    ap.add_argument("--source-url", default="https://download.openstreetmap.fr/extracts/asia/india/bihar.osm.pbf")
    args = ap.parse_args()
    names = [d["name"] for d in yaml.safe_load((ROOT / "data/scenarios/BR/incident.yaml").read_text())["districts"]]
    if args.overpass:
        sys.exit("Overpass mode: the query is in OVERPASS_QUERY below; overpass-api.de was unreachable from the build "
                 "sandbox, so this path is untested (docs/STATUS.md, BLOCKED). Use --pbf with an extract instead.")
    md5 = hashlib.md5(args.pbf.read_bytes()).hexdigest()
    districts, places, landmarks = from_pbf(args.pbf, names)
    write(districts, places, collapse_bridges(landmarks), {"source": args.source_url, "md5": md5, "districts": names})


OVERPASS_QUERY = """[out:json][timeout:180];
area["boundary"="administrative"]["admin_level"="5"]["name"~"^(Gopalganj|Muzaffarpur)$"]->.d;
( node(area.d)["place"~"village|hamlet|town|suburb|neighbourhood|locality|city"];
  nwr(area.d)["amenity"~"place_of_worship|school|college|hospital|clinic|marketplace"];
  way(area.d)["bridge"~"yes|viaduct|aqueduct"]; nwr(area.d)["man_made"~"bridge|water_tower"];
  node(area.d)["railway"~"station|halt"]; );
out center tags;"""

if __name__ == "__main__":
    main()
