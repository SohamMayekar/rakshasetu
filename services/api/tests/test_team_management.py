"""Adding and editing teams: any agency, any capabilities from the catalog (and any the catalog lacks), a lead's
sign-in, admin only. Nothing here assumes a city."""

from tests.conftest import login, needs_db, one

pytestmark = needs_db

NEW = {"incident": "BR", "district": "Gopalganj", "name": "Hazmat unit 1", "agency": "Municipal Corporation",
       "capabilities": ["hazmat", "Ambulance", "tunnel rescue"], "has_app": True, "lat": 26.47, "lng": 84.44,
       "max_active": 3, "lead": {"username": "hazmat1", "password": "a-long-password"}}


def test_the_catalog_is_listed_for_the_form(seeded, client):
    login(client, "admin")
    body = client.get("/v1/teams/catalog").json()
    assert {"hazmat", "fire", "boat"} <= {c["key"] for c in body["capabilities"]} and "Other" in body["agencies"]


def test_the_admin_adds_a_team_and_its_lead_can_sign_in(seeded, client, public_client, app_db):
    login(client, "admin")
    r = client.post("/v1/teams", json=NEW)
    assert r.status_code == 201, r.text
    assert r.json()["unknown_capabilities"] == ["tunnel_rescue"]          # kept as written, and reported
    assert set(one(app_db, "SELECT capabilities FROM teams WHERE name = 'Hazmat unit 1'")) == {"hazmat", "ambulance", "tunnel_rescue"}
    assert one(app_db, "SELECT agency FROM teams WHERE name = 'Hazmat unit 1'") == "Municipal Corporation"
    login(public_client, "hazmat1", "a-long-password")
    assert public_client.get("/v1/me").json()["user"]["role"] == "team_lead"
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'team.created'") == 1


def test_only_the_admin_adds_or_edits_teams_and_names_stay_unique(seeded, client):
    login(client, "spatil")
    assert client.post("/v1/teams", json=NEW).status_code == 403
    login(client, "admin")
    assert client.post("/v1/teams", json=NEW).status_code == 201
    assert client.post("/v1/teams", json={**NEW, "lead": {"username": "another1", "password": "a-long-password"}}).status_code == 409


def test_a_teams_capabilities_can_be_changed_with_a_reason(seeded, client, app_db):
    login(client, "admin")
    tid = client.post("/v1/teams", json={**NEW, "lead": None}).json()["team_id"]
    assert client.patch(f"/v1/teams/{tid}", json={"capabilities": ["fire", "rope"]}).status_code == 422   # a reason is required
    r = client.patch(f"/v1/teams/{tid}", json={"capabilities": ["fire", "rope"], "reason": "new engine"})
    assert r.status_code == 200
    assert set(one(app_db, "SELECT capabilities FROM teams WHERE id = :t", t=tid)) == {"fire", "rope"}
