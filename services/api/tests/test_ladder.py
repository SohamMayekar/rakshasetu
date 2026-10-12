"""F-L4: landmark words → a pin with an honest circle, decided by rules over real OSM data."""

import math

import pytest

from app.modules.location.ladder import resolve
from app.pipeline.keywords import extract_keywords
from tests.conftest import needs_db, one

pytestmark = needs_db
DEMO = "Thawe gaon mein, Durga mandir ke peeche, pul ke paas, chhat pe 6 log fase hain. Paani ghus gaya hai, ek buzurg hain, dawai chahiye."
DEMO_HI = "थावे गाँव में, दुर्गा मंदिर के पीछे, पुल के पास, छत पे 6 लोग फँसे हैं। पानी घुस गया है, एक बुज़ुर्ग हैं, दवाई चाहिए।"


def metres(a, b):
    return math.hypot((a[0] - b[0]) * 111_320, (a[1] - b[1]) * 111_320 * math.cos(math.radians(a[0])))


def locate(app_db, line, hint=None):
    br = one(app_db, "SELECT id FROM incidents WHERE code = 'BR'")
    with app_db.connect() as c:
        return resolve(c, br, extract_keywords(line), line, hint)


def temple(app_db):
    with app_db.connect() as c:
        r = c.execute(__import__("sqlalchemy").text(
            "SELECT ST_Y(geom::geometry), ST_X(geom::geometry) FROM landmarks WHERE name = 'Thawe durga mata mandir'")).one()
    return (r[0], r[1])


@pytest.mark.parametrize("line", [DEMO, DEMO_HI], ids=["latin", "devanagari"])
def test_the_demo_line_pins_inside_300_m_around_the_temple_bridge_pair(seeded, app_db, line):
    loc = locate(app_db, line)
    assert loc.step == 3 and loc.radius_m <= 300 and loc.confidence in ("high", "medium")
    assert metres((loc.lat, loc.lng), temple(app_db)) <= loc.radius_m    # the real temple is inside the circle
    assert "Thawe durga mata mandir" in loc.method and "bridge" in loc.method and "in Thawe" in loc.method
    assert loc.district_id == one(app_db, "SELECT id FROM districts WHERE name = 'Gopalganj'")


def test_village_only_is_a_low_circle_of_at_most_2_km(seeded, app_db):
    loc = locate(app_db, "Phulwaria mein hamare rishtedaar fase hain, 4 log, khana nahi hai")
    assert loc.step == 6 and loc.confidence == "low" and loc.radius_m <= 2000
    assert loc.method.startswith("Low · 1.5 km · village only: Phulwaria")


def test_a_single_landmark_pins_on_it_at_medium(seeded, app_db):
    loc = locate(app_db, "Thawe mein station ke paas 5 log fase hain")
    assert loc.step == 4 and loc.confidence == "medium" and loc.radius_m == 300
    assert "Thawe Junction" in loc.method


def test_no_location_means_needs_location_and_no_pin(seeded, app_db):
    gop = one(app_db, "SELECT id FROM districts WHERE name = 'Gopalganj'")
    loc = locate(app_db, "Hum log fase hain, 3 log, ek buzurg, jaldi aaiye", hint=gop)
    assert loc.lat is None and loc.step == 8 and "needs_location" in loc.flags and loc.district_id == gop


def test_district_only_is_very_low_and_still_needs_location(seeded, app_db):
    loc = locate(app_db, "Gopalganj district mein 5 log fase hain")
    assert loc.step == 7 and loc.confidence == "very_low" and loc.radius_m == 15000 and "needs_location" in loc.flags


def test_someone_far_away_needs_a_location(seeded, app_db):
    loc = locate(app_db, "I'm in London, my family is stuck, 4 people")
    assert loc.lat is None and "needs_location" in loc.flags


def test_a_village_named_without_cues_is_found_by_the_gazetteer_scan(seeded, app_db):
    loc = locate(app_db, "Kuchaikote ke paas 6 log chhat par hain")
    assert loc.place and loc.place["name"] == "Kuchaikote"


def test_the_case_goes_to_the_district_where_the_place_is(seeded, app_db):
    gop = one(app_db, "SELECT id FROM districts WHERE name = 'Gopalganj'")
    loc = locate(app_db, "Kanti gaon mein 5 log fase hain", hint=gop)     # typed at the Gopalganj desk
    assert loc.district_id == one(app_db, "SELECT id FROM districts WHERE name = 'Muzaffarpur'")


def test_the_circle_always_comes_with_its_method_in_words(seeded, app_db):
    for line in (DEMO, "Phulwaria mein 4 log", "Thawe mein station ke paas 5 log"):
        loc = locate(app_db, line)
        assert loc.method.split(" · ")[0] in ("High", "Medium", "Low", "Very low")


def test_end_to_end_a_typed_report_gets_its_circle(seeded, client, app_db):
    import uuid

    from app.core.jobs import drain
    from app.pipeline import register_handlers
    from tests.conftest import login
    register_handlers()
    login(client, "priya")
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "text": DEMO, "client_id": str(uuid.uuid4())}).json()["report_id"]
    drain(app_db)
    case = client.get(f"/v1/cases/{one(app_db, 'SELECT case_id FROM reports WHERE id = :r', r=rid)}").json()
    assert case["radius_m"] <= 300 and case["location_source"] == "rule" and "needs_location" not in case["flags"]
    assert case["location_text"] == "Thawe" and case["location_method"].endswith("in Thawe")
    assert len(case["attributes"]["location_detail"]["landmarks"]) == 2
    assert any(step["step"] == "place" for step in case["reports"][0]["receipt"])
