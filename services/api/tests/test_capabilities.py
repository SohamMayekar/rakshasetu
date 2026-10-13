"""The capability catalog: one list for every kind of disaster, used by dispatch and by the team form."""

from types import SimpleNamespace

import pytest

from app.capabilities import AGENCIES, CATALOG, HELPFUL_BY_HAZARD, HELPFUL_BY_NEED, KEYS, helpful
from app.contracts import Hazard, Need
from app.modules.dispatch.service import rank


def test_the_catalog_is_well_formed():
    keys = [c["key"] for c in CATALOG]
    assert len(keys) == len(set(keys)) and all(k == k.lower() and " " not in k for k in keys)
    assert all(c["label"] and c["group"] and c["for"] for c in CATALOG)
    assert {"boat", "rope", "medical", "heavy_lift", "fire"} <= KEYS          # what the original packs already use
    assert "Other" in AGENCIES and len(AGENCIES) == len(set(AGENCIES))


def test_every_helpful_capability_is_in_the_catalog_and_every_hazard_and_need_is_known():
    used = set().union(*HELPFUL_BY_HAZARD.values(), *HELPFUL_BY_NEED.values())
    assert used <= KEYS
    assert set(HELPFUL_BY_HAZARD) <= set(Hazard.__args__) and set(HELPFUL_BY_NEED) <= set(Need.__args__)


@pytest.mark.parametrize("hazards,needs,expect", [
    (["landslide"], [], {"mountain", "road_clearance"}),
    (["smoke_gas"], [], {"hazmat"}),
    (["road_accident"], ["medical_urgent"], {"ambulance", "extrication"}),
    (["wind_damage"], [], {"electrical", "road_clearance"}),
    ([], ["food"], {"food_water"}),
    ([], ["shelter"], {"shelter"}),
])
def test_helpful_follows_the_situation(hazards, needs, expect):
    assert expect <= helpful(hazards, needs)


def _team(**kw):
    base = dict(id=1, name="Team", agency="Agency", capabilities=[], has_app=True, radio_channel=None,
                status="available", status_reason=None, max_active=2, last_geom_at=None, lat=19.0, lng=72.0, active=0)
    return SimpleNamespace(**{**base, **kw})


def test_the_team_with_more_of_what_helps_leads_and_nobody_is_ruled_out():
    teams = [_team(id=1, name="Near, nothing listed", lat=19.001, lng=72.0),
             _team(id=2, name="Hazmat unit", capabilities=["hazmat"], lat=19.05, lng=72.0),
             _team(id=3, name="Fire and hazmat", agency="Fire & Rescue", capabilities=["hazmat"], lat=19.08, lng=72.0)]
    out = rank({"lat": 19.0, "lng": 72.0, "hazards": ["smoke_gas"], "needs": []}, teams)
    assert [t["name"] for t in out["suggestions"]] == ["Fire and hazmat", "Hazmat unit", "Near, nothing listed"]


def test_a_relief_team_is_preferred_for_a_supplies_case_without_excluding_others():
    teams = [_team(id=1, name="Generic, near", lat=19.001, lng=72.0), _team(id=2, name="Relief kitchen", capabilities=["food_water"], lat=19.1, lng=72.0)]
    out = rank({"lat": 19.0, "lng": 72.0, "hazards": [], "needs": ["food"]}, teams)
    assert [t["name"] for t in out["suggestions"]] == ["Relief kitchen", "Generic, near"]
