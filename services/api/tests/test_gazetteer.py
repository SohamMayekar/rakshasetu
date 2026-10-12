"""F-L4 data: the committed OSM extract loads, and place names meet across scripts and spellings."""

import pytest
from rapidfuzz import fuzz

from app.modules.location.names import norm
from tests.conftest import needs_db, one, rows

pytestmark = needs_db


def test_the_gazetteer_loads_with_the_seed(seeded, app_db):
    assert seeded["cases"] > 0
    assert one(app_db, "SELECT count(*) FROM places") >= 70
    assert one(app_db, "SELECT count(*) FROM landmarks WHERE type = 'bridge'") > 1000
    assert one(app_db, "SELECT name FROM places WHERE name_norm = :n", n=norm("Thawe")) == "Thawe"


def test_the_demo_village_has_its_temple_and_a_bridge_within_500_m(seeded, app_db):
    temple_m = one(app_db, "SELECT round(ST_Distance(p.geom, l.geom)) FROM places p, landmarks l"
                           " WHERE p.name = 'Thawe' AND l.name = 'Thawe durga mata mandir'")
    bridge_m = one(app_db, "SELECT round(min(ST_Distance(t.geom, b.geom))) FROM landmarks t, landmarks b"
                           " WHERE t.name = 'Thawe durga mata mandir' AND b.type = 'bridge'")
    assert temple_m < 100 and bridge_m < 200


def test_district_boundaries_contain_their_villages(seeded, app_db):
    assert one(app_db, "SELECT d.name FROM districts d, places p WHERE p.name = 'Thawe'"
                       " AND ST_Covers(d.boundary, p.geom)") == "Gopalganj"
    assert one(app_db, "SELECT d.name FROM districts d, places p WHERE p.name = 'Kanti'"
                       " AND ST_Covers(d.boundary, p.geom)") == "Muzaffarpur"


@pytest.mark.parametrize("heard,mapped", [
    ("थावे", "Thawe"), ("Thave", "Thawe"), ("हथुआ", "Hathua"), ("फुलवरिया", "Phulwaria"),
    ("सिधवलिया", "Sidhwalia"), ("देवापुर", "Dewapur"), ("Kuchaykot", "Kuchaikote"), ("मीनापुर", "Minapur"),
])
def test_names_meet_across_scripts(heard, mapped):
    assert fuzz.ratio(norm(heard), norm(mapped)) >= 85, (norm(heard), norm(mapped))


def test_different_villages_stay_apart():
    assert fuzz.ratio(norm("Barauli"), norm("Bariarpur")) < 85
    assert fuzz.ratio(norm("Manjha"), norm("Minapur")) < 85


# --- Mumbai (MH, m87) --------------------------------------------------------------------------------------------

def _place_said(app_db, text: str) -> str | None:
    from app.modules.location.ladder import match_place
    from app.pipeline.keywords import extract_keywords
    mh = one(app_db, "SELECT id FROM incidents WHERE code = 'MH'")
    with app_db.connect() as conn:
        place, _ = match_place(conn, mh, extract_keywords(text), text)
    return place.name if place else None


def test_mumbai_loads_with_its_two_districts_and_the_demo_temple_by_a_bridge(seeded, app_db):
    assert one(app_db, "SELECT count(*) FROM places p JOIN incidents i ON i.id = p.incident_id WHERE i.code = 'MH'") > 900
    assert one(app_db, "SELECT d.name FROM districts d, places p WHERE p.name = 'Kurla West'"
                       " AND ST_Covers(d.boundary, p.geom)") == "Mumbai Suburban"
    bridge_m = one(app_db, "SELECT round(min(ST_Distance(t.geom, b.geom))) FROM landmarks t, landmarks b"
                           " WHERE t.name LIKE 'shankar mandir (kranti nagar%' AND b.type = 'bridge'")
    assert bridge_m < 150


@pytest.mark.parametrize("text, place", [
    ("6 people stuck in Kurla, water inside", "Kurla"),                         # the halves joined: a derived place
    ("My family is in Kurla West, near the bridge", "Kurla West"),              # the half said beats the joined place
    ("Sion Koliwada, 8 people on a roof", "Sion Koliwada"),                     # two-word names before one-word ones
    ("आम्ही चेंबूरला अडकलो आहोत", "Chembur"),                                     # Marathi "-ला", and चें = "chem"
])
def test_mumbai_names_are_found_the_way_people_say_them(seeded, app_db, text, place):
    assert _place_said(app_db, text) == place


def test_mumbai_teams_have_a_radio_only_boat_and_the_demo_teams_start_free(seeded, app_db):
    teams = {r[0]: r[1:] for r in rows(
        app_db, "SELECT t.name, t.has_app, t.status FROM teams t JOIN incidents i ON i.id = t.incident_id WHERE i.code = 'MH'")}
    assert teams["NDRF Boat 2"][0] is False and any(s == "out_of_service" for _, s in teams.values())
    assert one(app_db, "SELECT count(*) FROM assignments a JOIN teams t ON t.id = a.team_id"
                       " WHERE t.name IN ('NDRF Boat 2', 'Fire Brigade Boat 5') AND a.state = 'open'") == 0
