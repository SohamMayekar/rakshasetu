"""F-C9: cookie auth, roles from roles.yaml, and the Scope inside every query (rule R8)."""

import pytest
from sqlalchemy import text

from app.core.auth import COOKIE
from tests.conftest import login, needs_db, one

pytestmark = needs_db


def test_picker_login_works_on_the_local_listener_without_a_password(seeded, client):
    login(client, "priya")
    me = client.get("/v1/me").json()
    assert me["user"]["role"] == "call_taker" and me["user"]["role_label"] == "Call-taker"
    assert "case.check" in me["permissions"] and "assignment.create" not in me["permissions"]
    assert me["flags"]["family_check"] is True


def test_the_public_listener_needs_a_password(seeded, public_client):
    assert public_client.post("/v1/auth/login", json={"username": "boat5"}).status_code == 401
    assert public_client.post("/v1/auth/login", json={"username": "boat5", "password": "nope"}).status_code == 401
    login(public_client, "boat5", "rakshasetu")
    assert public_client.get("/v1/me").json()["team"]["name"] == "Fire & Rescue Boat 5"


def test_the_picker_list_is_local_only(seeded, client, public_client):
    assert public_client.get("/v1/auth/users").status_code == 404
    users = client.get("/v1/auth/users").json()
    assert {"username": "spatil", "name": "S. Patil", "role": "duty_officer", "role_label": "Duty officer",
            "team": None, "title": "Duty officer", "line": "Runs the Mumbai control room desk"} in users


def test_the_picker_shows_three_profiles_and_the_other_users_still_exist(seeded, client, app_db):
    """m65 (D22): the sign-in screen lists exactly the duty officer, the rescue team and the state admin. The other
    seeded users stay (the permission and IDOR tests sign in as them); they are only off the picker."""
    users = client.get("/v1/auth/users").json()
    assert [(u["title"], u["username"], u["role"]) for u in users] == [
        ("Duty officer", "spatil", "duty_officer"), ("Rescue team", "fb5", "team_lead"), ("State admin", "admin", "admin")]
    assert users[1]["team"] == "Fire Brigade Boat 5"
    assert one(app_db, "SELECT count(*) FROM users") == 17
    login(client, "rdas")     # off the picker (m88: the desk is Mumbai's), still a real user with their own role
    assert client.get("/v1/me").json()["user"]["role"] == "duty_officer"
    login(client, "asinha")
    assert client.get("/v1/me").json()["user"]["role"] == "incharge"


def test_the_duty_officer_sees_only_bihar_and_the_admin_sees_all_four(seeded, client):
    login(client, "rdas")
    assert [i["code"] for i in client.get("/v1/me").json()["incidents"]] == ["BR"]
    client.post("/v1/auth/logout")
    login(client, "admin")
    assert sorted(i["code"] for i in client.get("/v1/me").json()["incidents"]) == ["BR", "HP", "MH", "OD"]


def test_the_picker_is_refused_through_the_tunnel_even_on_local(seeded, client):
    r = client.post("/v1/auth/login", json={"username": "admin"}, headers={"CF-Connecting-IP": "203.0.113.9"})
    assert r.status_code == 401


def test_no_cookie_or_a_forged_cookie_is_401(seeded, client):
    assert client.get("/v1/me").status_code == 401
    client.cookies.set(COOKIE, "MTo5OTk5OTk5OTk5.0000")
    assert client.get("/v1/me").status_code == 401


def test_role_is_loaded_from_the_database_on_every_request(seeded, client, owner_db):
    login(client, "priya")
    assert client.get("/v1/cases").status_code == 200
    with owner_db.begin() as c:
        c.execute(text("UPDATE users SET role = 'seoc_viewer' WHERE username = 'priya'"))
    assert client.get("/v1/cases").status_code == 403   # same cookie, new role, no re-login


def test_form_encoded_mutations_are_refused(seeded, client):
    r = client.post("/v1/auth/login", data={"username": "admin"})
    assert r.status_code == 415


@pytest.mark.parametrize("user,expected_districts", [
    ("rdas", {"Gopalganj"}), ("priya", {"Gopalganj"}), ("mkumar", {"Muzaffarpur"}), ("admin", {"Gopalganj", "Muzaffarpur"}),
])
def test_case_lists_are_scoped_in_sql_by_incident_and_district(seeded, client, user, expected_districts):
    login(client, user)
    cases = client.get("/v1/cases", params={"incident": "BR"}).json()
    assert cases and {c["district"] for c in cases} == expected_districts


def test_an_odisha_officer_sees_no_bihar_case(seeded, client):
    login(client, "spatra")
    assert client.get("/v1/cases", params={"incident": "BR"}).json() == []
    assert client.get("/v1/cases/BR-151").status_code == 404


def test_seoc_viewer_sees_totals_only(seeded, client):
    login(client, "seoc")
    assert client.get("/v1/cases").status_code == 403


def test_a_team_lead_without_assignments_sees_nothing_and_gets_the_visible_403(seeded, client):
    login(client, "boat5")
    assert client.get("/v1/cases").json() == []
    r = client.get("/v1/cases/BR-151")
    assert r.status_code == 403 and r.json()["detail"] == "Not assigned to your team"


def test_case_detail_masks_phones(seeded, client):
    login(client, "rdas")
    case = client.get("/v1/cases/BR-151").json()
    assert case["reports"][0]["reporter_phone_masked"].count("x") == 6
    assert "reporter_phone_enc" not in case["reports"][0]


def test_websocket_needs_a_session(seeded, client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e, client.websocket_connect("/v1/ws?since=0") as ws:
        ws.receive_json()
    assert e.value.code == 4401


def test_audit_read_is_for_officers_and_admin_only(seeded, client):
    login(client, "priya")
    assert client.get("/v1/audit/verify").status_code == 403
    login(client, "rdas")
    assert client.get("/v1/audit/verify").json()["ok"] is True
    assert one is not None
