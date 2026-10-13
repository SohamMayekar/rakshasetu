"""Not only floods: fires, road accidents, earthquakes and storm damage are read, ranked and dispatched sensibly.
Pure tests (no database): the word rules, the priority rules and the team ranking."""

from types import SimpleNamespace

import pytest

from app.modules.dispatch.service import needed, rank
from app.modules.triage.rules import triage
from app.pipeline.keywords import extract_keywords


def _fields(text: str) -> dict:
    ex = extract_keywords(text)
    return {"hazards": [h.type for h in ex.hazards], "needs": [n.type for n in ex.needs],
            "vulnerable": [v.type for v in ex.vulnerable], "people_count": ex.people_count.value if ex.people_count else None}


# --- reading ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("text,hazard", [
    ("Ghar mein aag lagi hai, 4 log andar fase hain", "fire"),
    ("Building on fire, three people on the second floor", "fire"),
    ("घरात आग लागली आहे, चार जण आत आहेत", "fire"),
    ("Gas leak ho gaya hai, dhuan bhar gaya, bachche behosh hain", "smoke_gas"),
    ("Truck aur car ki takkar, accident hua hai, 3 log ghayal", "road_accident"),
    ("There was a road accident near the bridge, two people injured", "road_accident"),
    ("Bhukamp ke baad imarat gir gayi, 5 log dabe hain", "earthquake"),
    ("Toofan mein chhat ud gayi aur ped gir gaya, 4 log ghar mein hain", "wind_damage"),
    ("Cyclone ke baad ghar toot gaya hai, shelter chahiye", "wind_damage"),
])
def test_other_disasters_are_read(text, hazard):
    assert hazard in _fields(text)["hazards"]


def test_a_fire_brigade_is_not_a_fire():
    assert "fire" not in _fields("Fire brigade ko bulao, paani ghar mein ghus gaya hai")["hazards"]
    assert "fire" not in _fields("The fire station is near the temple, water is rising")["hazards"]


def test_shelter_and_rescue_are_needs():
    assert "shelter" in _fields("Hamara ghar toot gaya, shelter chahiye, 6 log")["needs"]
    assert "rescue" in _fields("Please rescue us, bachao")["needs"]


def test_the_flood_demo_line_is_unchanged():
    demo = "Thawe gaon mein, Durga mandir ke peeche, pul ke paas, chhat pe 6 log fase hain. Paani ghus gaya hai, ek buzurg hain, dawai chahiye."
    f = _fields(demo)
    assert set(f["hazards"]) == {"trapped_on_roof", "water_entering"} and f["needs"] == ["medicine"]


# --- priority --------------------------------------------------------------------------------------------------

def test_a_fire_with_people_is_urgent_and_an_accident_with_injured_is_urgent():
    assert triage(_fields("Ghar mein aag lagi hai, 4 log andar fase hain"))[0] == "P1"
    assert triage(_fields("Road accident, bus palat gayi, 6 log ghayal"))[0] == "P1"
    assert triage(_fields("Bhukamp aaya, imarat gir gayi, 3 log dabe hain"))[0] == "P1"


def test_an_accident_or_storm_damage_alone_is_worth_a_check_not_an_alarm():
    assert triage(_fields("Gaadi ki takkar hui hai"))[0] == "P2"
    assert triage(_fields("Toofan mein ped gir gaya"))[0] == "P2"


def test_a_spreading_fire_ranks_with_rising_water_inside_the_urgent_group():
    _, _, fire_rank = triage({"hazards": ["fire"]})
    _, _, water_rank = triage({"hazards": ["trapped_on_roof", "water_rising"]})
    assert fire_rank == water_rank == 2


# --- sending a team --------------------------------------------------------------------------------------------

def test_trapped_or_stranded_alone_does_not_ask_for_a_boat():
    assert needed(["trapped_inside"], []) == (set(), set())
    assert needed(["cut_off"], []) == (set(), set())
    assert needed(["trapped_inside", "fire"], [])[0] == set()


def test_water_still_asks_for_a_boat_and_a_roof_still_does_unless_something_else_explains_it():
    assert needed(["trapped_on_roof"], []) == ({"boat"}, set())
    assert needed(["trapped_inside", "water_entering"], [])[0] == {"boat"}
    assert needed(["trapped_on_roof", "wind_damage"], [])[0] == set()


def test_fire_and_accident_capabilities():
    assert needed(["fire"], []) == (set(), {"fire", "medical"})
    assert needed(["road_accident"], ["medical_urgent"]) == (set(), {"medical", "heavy_lift"})
    assert needed(["earthquake", "trapped_inside"], [])[0] == {"heavy_lift"}


def _team(**kw):
    base = dict(id=1, name="Team", agency="Agency", capabilities=[], has_app=True, radio_channel=None,
                status="available", status_reason=None, max_active=2, last_geom_at=None, lat=19.0, lng=72.0, active=0)
    return SimpleNamespace(**{**base, **kw})


def test_a_fire_crew_is_suggested_for_a_fire_and_a_boat_team_is_not_ruled_out():
    teams = [_team(id=1, name="Police QRT", agency="Police", capabilities=["rope"], lat=19.05, lng=72.85),
             _team(id=2, name="Fire station, Kurla", agency="Fire & Rescue", capabilities=["rope"], lat=19.09, lng=72.9),
             _team(id=3, name="SDRF Boat 6", agency="SDRF", capabilities=["boat"], lat=19.051, lng=72.851)]
    out = rank({"lat": 19.05, "lng": 72.85, "hazards": ["fire", "trapped_inside"], "needs": []}, teams)
    assert out["suggestions"][0]["name"] == "Fire station, Kurla"          # the fire crew leads, though it is further
    assert "fire" in out["suggestions"][0]["capabilities"]
    assert {t["name"] for t in out["suggestions"]} == {"Fire station, Kurla", "Police QRT", "SDRF Boat 6"}


def test_a_trapped_family_in_a_collapse_still_needs_heavy_lift_not_a_boat():
    boats = [_team(id=1, name="Boat", capabilities=["boat"])]
    out = rank({"lat": 19.0, "lng": 72.0, "hazards": ["structure_collapsed", "trapped_inside"], "needs": []}, boats)
    assert out["suggestions"] == [] and out["more"][0]["missing"] == ["heavy_lift"]
