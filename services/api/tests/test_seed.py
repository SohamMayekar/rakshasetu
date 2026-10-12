"""F-C12 / S1-02: the seed loads 3 incidents, BR teams (one radio-only, one out of service), 40+ cases,
with timestamps relative to the moment of seeding."""

import os

import pytest
from sqlalchemy import create_engine, text

from app.seed import seed

OWNER = os.environ.get("TEST_OWNER_DATABASE_URL")
pytestmark = pytest.mark.skipif(not OWNER, reason="needs TEST_OWNER_DATABASE_URL")


@pytest.fixture(scope="module")
def seeded():
    summary = seed(OWNER)
    eng = create_engine(OWNER)
    yield summary, eng
    eng.dispose()


def q(eng, sql, **kw):
    with eng.connect() as c:
        return c.execute(text(sql), kw).all()


def test_three_incidents_and_their_districts(seeded):
    summary, eng = seeded
    assert summary["incidents"] == 3
    assert {r[0] for r in q(eng, "SELECT code FROM incidents")} == {"BR", "OD", "HP"}
    assert q(eng, "SELECT count(*) FROM districts WHERE incident_id = (SELECT id FROM incidents WHERE code='BR')")[0][0] == 2


def test_br_teams_include_a_radio_only_and_an_out_of_service_team(seeded):
    _, eng = seeded
    rows = q(eng, "SELECT t.name, t.has_app, t.status FROM teams t JOIN incidents i ON i.id = t.incident_id WHERE i.code='BR'")
    assert any(not has_app for _, has_app, _ in rows)
    assert any(status == "out_of_service" for _, _, status in rows)
    assert "SDRF Boat 2" in {r[0] for r in rows}


def test_forty_plus_seeded_br_cases_with_relative_timestamps(seeded):
    _, eng = seeded
    n, newest, oldest = q(eng, "SELECT count(*), max(queue_since), min(queue_since) FROM cases c"
                                " JOIN incidents i ON i.id = c.incident_id WHERE i.code='BR'")[0]
    assert n >= 40
    age_newest = q(eng, "SELECT extract(epoch FROM now() - :t)", t=newest)[0][0]
    age_oldest = q(eng, "SELECT extract(epoch FROM now() - :t)", t=oldest)[0][0]
    assert 0 < age_newest < 3600, "the newest seeded case should be minutes old, not stale"
    assert age_oldest < 11 * 3600


def test_the_honesty_cases_exist(seeded):
    _, eng = seeded
    assert q(eng, "SELECT count(*) FROM cases WHERE location_confidence = 'low'")[0][0] >= 1
    assert q(eng, "SELECT count(*) FROM cases WHERE geom IS NULL AND 'needs_location' = ANY(flags)")[0][0] >= 1


def test_public_ids_are_sequential_per_incident(seeded):
    _, eng = seeded
    ids = [r[0] for r in q(eng, "SELECT public_id FROM cases c JOIN incidents i ON i.id=c.incident_id"
                                " WHERE i.code='BR' ORDER BY c.id")]
    assert ids[0] == "BR-151" and ids[-1] == f"BR-{150 + len(ids)}"


def test_phones_are_stored_encrypted_hashed_and_masked_never_in_clear(seeded):
    _, eng = seeded
    enc, h, masked = q(eng, "SELECT reporter_phone_enc, reporter_phone_hash, reporter_phone_masked FROM reports"
                            " WHERE reporter_phone_hash IS NOT NULL LIMIT 1")[0]
    assert "98765" not in enc and len(h) == 64 and masked.count("x") == 6


def test_demo_users_have_roles_and_scopes(seeded):
    _, eng = seeded
    rows = dict(q(eng, "SELECT username, role FROM users"))
    assert rows["rdas"] == "duty_officer" and rows["boat5"] == "team_lead" and rows["seoc"] == "seoc_viewer"
