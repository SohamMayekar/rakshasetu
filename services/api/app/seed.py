"""Seed loader (PRD F-C12): wipe the demo database and load the scenario packs, with every timestamp
relative to the moment of seeding (otherwise every seeded case would look hours stale on stage).

Runs as rakshasetu_owner (it truncates tables, which the app role can't), and only with DEMO_MODE=true.
    python -m app.seed            # all packs
    python -m app.seed --packs BR
"""

import argparse
import os
import sys
from datetime import timedelta
from functools import lru_cache
from pathlib import Path

import yaml
from sqlalchemy import Connection, text

from app.core.eventlog import SYSTEM, append_event
from app.core.passwords import hash_password
from app.core.phones import protect
from app.db import engine_for
from app.settings import get_settings

PACKS = ("BR", "OD", "HP")
DEMO_PASSWORD = "rakshasetu"  # synthetic demo users only; documented in data/scenarios/users.yaml
KEEP_TABLES = {"schema_migrations", "spatial_ref_sys"}


def _yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text()) if path.exists() else {}


def wipe(conn: Connection) -> None:
    """Empty every domain table and restart id sequences. Owner role only."""
    tables = [r[0] for r in conn.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'")) if r[0] not in KEEP_TABLES]
    if tables:
        conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))


def _point(lat_lon):
    return None if not lat_lon else f"SRID=4326;POINT({lat_lon[1]} {lat_lon[0]})"


def load_pack(conn: Connection, root: Path, code: str, now) -> dict:
    inc = _yaml(root / code / "incident.yaml")
    incident_id = conn.execute(text(
        "INSERT INTO incidents (code, name, type, states, language, center, status, next_case_number)"
        " VALUES (:code, :name, :type, :states, :language, CAST(:center AS geography), :status, :next)"
        " RETURNING id"), dict(code=inc["code"], name=inc["name"], type=inc["type"], states=inc["states"],
                               language=inc.get("language", "hi"), center=_point(inc.get("center")),
                               status=inc.get("status", "active"), next=inc.get("next_case_number", 1))).scalar_one()
    append_event(conn, actor=SYSTEM, action="incident.seeded", entity_type="incident", entity_id=incident_id,
                 incident_id=incident_id, data={"code": inc["code"], "name": inc["name"], "type": inc["type"]})
    districts = {}
    for d in inc["districts"]:
        districts[d["name"]] = conn.execute(text(
            "INSERT INTO districts (incident_id, name, state, centroid)"
            " VALUES (:i, :name, :state, CAST(:c AS geography)) RETURNING id"),
            dict(i=incident_id, name=d["name"], state=d["state"], c=_point(d["centroid"]))).scalar_one()

    teams = {}
    for t in _yaml(root / code / "teams.yaml").get("teams", []):
        teams[t["name"]] = conn.execute(text(
            "INSERT INTO teams (incident_id, district_id, name, agency, capabilities, has_app, radio_channel,"
            " base_geom, last_geom, last_geom_at, max_active, status, status_reason)"
            " VALUES (:i, :d, :name, :agency, :caps, :app, :radio, CAST(:geom AS geography), CAST(:geom AS geography),"
            "         :now - make_interval(mins => :age), :max, :status, :reason) RETURNING id"),
            dict(i=incident_id, d=districts[t["district"]], name=t["name"], agency=t["agency"],
                 caps=t.get("capabilities", []), app=t.get("has_app", True), radio=t.get("radio_channel"),
                 geom=_point(t["base"]), now=now, age=t.get("position_age_min", 0), max=t.get("max_active", 2),
                 status=t.get("status", "available"), reason=t.get("status_reason"))).scalar_one()
        append_event(conn, actor=SYSTEM, action="team.seeded", entity_type="team", entity_id=teams[t["name"]],
                     incident_id=incident_id, district_id=districts[t["district"]], team_id=teams[t["name"]],
                     data={"name": t["name"], "has_app": t.get("has_app", True), "status": t.get("status", "available")})

    gazetteer = load_gazetteer(conn, root / code / "gazetteer", incident_id, districts)

    cases = sorted(_yaml(root / code / "cases.yaml").get("cases", []), key=lambda c: -c["minutes_ago"])
    for c in cases:
        _insert_case(conn, incident_id, inc["code"], districts, c, now)
    return {"incident_id": incident_id, "districts": districts, "teams": teams, "cases": len(cases), **gazetteer}


def load_gazetteer(conn: Connection, folder: Path, incident_id: int, districts: dict) -> dict:
    """The committed OSM extract (scripts/import_osm.py) → places, landmarks, district boundaries."""
    import csv
    import json as _json

    from app.modules.location.names import norm
    if not (folder / "places.csv").exists():
        return {"places": 0, "landmarks": 0}
    radius = {"village": 1500, "hamlet": 800, "town": 3000, "city": 6000, "suburb": 1500, "locality": 800,
              "neighbourhood": 800, "isolated_dwelling": 300}
    places = list(csv.DictReader((folder / "places.csv").open()))
    conn.execute(text(
        "INSERT INTO places (incident_id, district_id, name, name_hi, alt_names, name_norm, type, geom, radius_m,"
        " osm_type, osm_id) VALUES (:i, :d, :name, NULLIF(:hi, ''), :alts, :norm, :type,"
        " ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius, :ot, :oid)"),
        [dict(i=incident_id, d=districts.get(p["district"]), name=p["name"], hi=p["name_hi"],
              alts=[a for a in p["alt_names"].split(";") if a], norm=norm(p["name"]), type=p["type"],
              lon=float(p["lon"]), lat=float(p["lat"]), radius=radius.get(p["type"], 1500), ot=p["osm_type"],
              oid=int(p["osm_id"])) for p in places])
    lms = list(csv.DictReader((folder / "landmarks.csv").open()))
    conn.execute(text(
        "INSERT INTO landmarks (incident_id, district_id, name, name_norm, type, religion, detail, geom, osm_type,"
        " osm_id, part) VALUES (:i, :d, NULLIF(:name, ''), :norm, :type, NULLIF(:rel, ''), NULLIF(:detail, ''),"
        " ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :ot, :oid, :part)"),
        [dict(i=incident_id, d=districts.get(x["district"]), name=x["name"], norm=norm(x["name"]), type=x["type"],
              rel=x["religion"], detail=x["detail"], lon=float(x["lon"]), lat=float(x["lat"]), ot=x["osm_type"],
              oid=int(x["osm_id"]), part=int(x.get("part") or 0)) for x in lms])
    geo = folder / "districts.geojson"
    if geo.exists():
        for f in _json.loads(geo.read_text())["features"]:
            if f["properties"]["name"] in districts:
                conn.execute(text("UPDATE districts SET boundary = ST_Multi(ST_GeomFromGeoJSON(:g))::geography"
                                  " WHERE id = :d"), {"g": _json.dumps(f["geometry"]), "d": districts[f["properties"]["name"]]})
    return {"places": len(places), "landmarks": len(lms)}


def _case_fields(c: dict) -> dict:
    """The pack gives fields explicitly (`fields`, thin packs) or as the generator's `truth` (BR).
    Until the pipeline exists, a BR case is placed where its text says: the village, as a Low circle."""
    if "fields" in c:
        f = dict(c["fields"])
        loc = f.pop("location", None) or {}
        return {**f, **{f"loc_{k}": v for k, v in loc.items()}}
    t = c["truth"]
    f = {"people_count": t["people_count"], "people_count_kind": "stated", "hazards": t["hazards"],
         "needs": t["needs"], "vulnerable": t["vulnerable"], "location_text": t["village"]}
    if t.get("village_point"):
        lat, lon = t["village_point"]
        f.update(loc_lat=lat, loc_lon=lon, loc_radius_m=1500, loc_confidence="low", loc_source="rule",
                 loc_method=f"Low · 1.5 km · village only: {t['village']}")
    return f


def _insert_case(conn: Connection, incident_id: int, code: str, districts: dict, c: dict, now) -> int:
    f = _case_fields(c)
    number = conn.execute(text("UPDATE incidents SET next_case_number = next_case_number + 1 WHERE id = :i"
                               " RETURNING next_case_number - 1"), dict(i=incident_id)).scalar_one()
    at = now - timedelta(minutes=c["minutes_ago"])
    has_loc = f.get("loc_lat") is not None
    flags = [] if has_loc else ["needs_location"]
    case_id = conn.execute(text(
        "INSERT INTO cases (public_id, incident_id, district_id, status, priority, priority_reasons,"
        " people_count, people_count_kind, needs, vulnerable, hazards, geom, radius_m, location_confidence,"
        " location_method, location_source, location_text, flags, queue_since, last_confirmed_at, created_at, updated_at)"
        " VALUES (:pid, :i, :d, :status, 'P4', ARRAY['not triaged yet (seed)'], :people, :kind, :needs, :vuln, :haz,"
        "         CAST(:geom AS geography), :radius, :conf, :method, :src, :ltext, :flags, :at, :at, :at, :at)"
        " RETURNING id"),
        dict(pid=f"{code}-{number}", i=incident_id, d=districts[c["district"]], status=c.get("status", "reported"),
             people=f.get("people_count"), kind=f.get("people_count_kind"), needs=f.get("needs", []),
             vuln=f.get("vulnerable", []), haz=f.get("hazards", []),
             geom=_point([f["loc_lat"], f["loc_lon"]]) if has_loc else None, radius=f.get("loc_radius_m"),
             conf=f.get("loc_confidence"), method=f.get("loc_method"), src=f.get("loc_source"),
             ltext=f.get("location_text"), flags=flags, at=at)).scalar_one()
    phone = protect(c.get("phone"))
    report_id = conn.execute(text(
        "INSERT INTO reports (incident_id, channel, source_ns, idempotency_key, received_at, reporter_phone_enc,"
        " reporter_phone_hash, reporter_phone_masked, reporter_relation, is_forward, language, text, status, case_id, source)"
        " VALUES (:i, :channel, 'seed', :key, :at, :enc, :hash, :masked, :rel, :fwd, NULL, :text, 'processed', :case,"
        "         CAST(:source AS jsonb)) RETURNING id"),
        dict(i=incident_id, channel=c["channel"], key=c["key"], at=at, enc=phone["enc"], hash=phone["hash"],
             masked=phone["masked"], rel=c.get("relation", "unknown"), fwd=c.get("relation") == "forwarder",
             text=c["text"], case=case_id, source='{"system": "seed"}')).scalar_one()
    append_event(conn, actor=SYSTEM, action="case.seeded", entity_type="case", entity_id=case_id,
                 incident_id=incident_id, district_id=districts[c["district"]], case_id=case_id,
                 data={"public_id": f"{code}-{number}", "status": c.get("status", "reported"), "report_id": report_id,
                       "channel": c["channel"], "minutes_ago": c["minutes_ago"]})
    return case_id


@lru_cache(maxsize=1)
def _demo_password_hash() -> str:
    return hash_password(DEMO_PASSWORD)   # scrypt is deliberately slow; one hash per process is enough


def load_users(conn: Connection, root: Path, packs: dict) -> int:
    users = _yaml(root / "users.yaml").get("users", [])
    pw = _demo_password_hash()
    n = 0
    for u in users:
        if not set(u["incidents"]) & set(packs):
            continue
        incident_ids = [packs[c]["incident_id"] for c in u["incidents"] if c in packs]
        district_ids = []
        for code, names in u.get("districts", {}).items():
            if code in packs:
                ds = packs[code]["districts"]
                district_ids += list(ds.values()) if names == "all" else [ds[n] for n in names]
        team_id = None
        if u.get("team"):
            team_id = next(p["teams"][u["team"]] for p in packs.values() if u["team"] in p["teams"])
        uid = conn.execute(text(
            "INSERT INTO users (username, name, role, incident_ids, district_ids, team_id, password_hash)"
            " VALUES (:u, :n, :r, :inc, :dist, :team, :pw) RETURNING id"),
            dict(u=u["username"], n=u["name"], r=u["role"], inc=incident_ids, dist=district_ids, team=team_id,
                 pw=pw)).scalar_one()
        append_event(conn, actor=SYSTEM, action="user.seeded", entity_type="user", entity_id=uid, team_id=team_id,
                     data={"username": u["username"], "role": u["role"]})
        n += 1
    return n


def seed(owner_url: str, packs=PACKS, root: Path | None = None) -> dict:
    root = root or get_settings().data_dir / "scenarios"
    with engine_for(owner_url).begin() as conn:
        wipe(conn)
        # A reset starts a new chain: the genesis event records why (PRD F-C8).
        append_event(conn, actor=SYSTEM, action="chain.genesis", entity_type="chain",
                     data={"reason": "demo seed", "packs": list(packs)})
        now = conn.execute(text("SELECT now()")).scalar_one()
        loaded = {code: load_pack(conn, root, code, now) for code in packs}
        users = load_users(conn, root, loaded)
    return {"incidents": len(loaded), "cases": sum(p["cases"] for p in loaded.values()),
            "teams": sum(len(p["teams"]) for p in loaded.values()), "users": users}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--packs", default=",".join(PACKS))
    args = ap.parse_args()
    if not get_settings().demo_mode:
        sys.exit("refusing to seed: DEMO_MODE is off (seeding wipes the database)")
    url = os.environ.get("DEMO_OWNER_DATABASE_URL")
    if not url:
        sys.exit("DEMO_OWNER_DATABASE_URL is not set")
    print(seed(url, tuple(args.packs.split(","))))


if __name__ == "__main__":
    main()
