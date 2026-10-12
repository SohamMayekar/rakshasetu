"""F-L4 data: the committed OSM extract loads, and place names meet across scripts and spellings."""

import pytest
from rapidfuzz import fuzz

from app.modules.location.names import norm
from tests.conftest import needs_db, one

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
