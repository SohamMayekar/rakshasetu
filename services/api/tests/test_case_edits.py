"""PRD F-L4 pin drag, §5.2 check, PATCH with If-Match: corrections by a person, each audited."""

from tests.conftest import login, needs_db, one

pytestmark = needs_db
THAWE = (26.4371, 84.3949)


def _noloc(app_db):
    return one(app_db, "SELECT public_id FROM cases WHERE geom IS NULL AND 'needs_location' = ANY(flags) LIMIT 1")


def test_a_pin_drag_sets_human_50_m_clears_needs_location_and_is_audited(seeded, client, app_db):
    pid = _noloc(app_db)
    login(client, "priya")
    r = client.patch(f"/v1/cases/{pid}/location", json={"lat": THAWE[0], "lng": THAWE[1], "reason": "caller said behind Thawe Junction"})
    assert r.status_code == 200
    case = client.get(f"/v1/cases/{pid}").json()
    assert (case["radius_m"], case["location_source"], case["location_confidence"]) == (50, "human", "high")
    assert case["location_method"] == "Human · 50 m · pin placed by Priya Kumari: caller said behind Thawe Junction"
    assert "needs_location" not in case["flags"]
    login(client, "rdas")
    audit = client.get("/v1/audit", params={"case_id": case["id"]}).json()
    moved = [e for e in audit if e["action"] == "case.location_moved"][0]
    assert moved["reason"] == "caller said behind Thawe Junction" and moved["data"]["to"]["radius_m"] == 50


def test_a_pin_moved_into_another_district_moves_the_case_to_that_desk(seeded, client, app_db):
    pid = _noloc(app_db)
    login(client, "priya")
    r = client.patch(f"/v1/cases/{pid}/location", json={"lat": 26.2145, "lng": 85.2982, "reason": "it's in Kanti"})
    assert r.json()["district_id"] == one(app_db, "SELECT id FROM districts WHERE name = 'Muzaffarpur'")
    assert client.get(f"/v1/cases/{pid}").status_code == 404           # no longer in Priya's district
    login(client, "mkumar")
    assert client.get(f"/v1/cases/{pid}").status_code == 200


def test_check_needs_a_location_first(seeded, client, app_db):
    pid = _noloc(app_db)
    login(client, "priya")
    r = client.post(f"/v1/cases/{pid}/check")
    assert r.status_code == 409 and "place the pin first" in r.json()["detail"]
    client.patch(f"/v1/cases/{pid}/location", json={"lat": THAWE[0], "lng": THAWE[1], "reason": "caller confirmed"})
    assert client.post(f"/v1/cases/{pid}/check").json()["status"] == "checked"
    case = client.get(f"/v1/cases/{pid}").json()
    assert case["status"] == "checked" and case["checked_by"] == one(app_db, "SELECT id FROM users WHERE username = 'priya'")
    assert all(p["checked"] and p["checked_by"] == "Priya Kumari" for p in case["provenance"].get("hazards", []))


def test_edits_need_the_current_version_and_a_stale_one_gets_a_409_naming_who(seeded, client, app_db):
    login(client, "priya")
    case = client.get("/v1/cases/BR-151").json()
    v = case["version"]
    ok = client.patch("/v1/cases/BR-151", json={"changes": {"people_count": 7}, "reason": "son called back: 7 people"},
                      headers={"If-Match": str(v)})
    assert ok.status_code == 200
    login(client, "rdas")
    stale = client.patch("/v1/cases/BR-151", json={"changes": {"people_count": 5}, "reason": "old info"},
                         headers={"If-Match": str(v)})
    assert stale.status_code == 409 and "Changed by Priya Kumari at" in stale.json()["detail"]
    after = client.get("/v1/cases/BR-151").json()
    assert after["people_count"] == 7 and after["provenance"]["people_count"]["method"] == "human"


def test_edits_without_if_match_or_to_other_fields_are_refused(seeded, client):
    login(client, "priya")
    assert client.patch("/v1/cases/BR-151", json={"changes": {"people_count": 3}, "reason": "x y z"}).status_code == 409
    v = client.get("/v1/cases/BR-151").json()["version"]
    r = client.patch("/v1/cases/BR-151", json={"changes": {"priority": "P1"}, "reason": "make it urgent"},
                     headers={"If-Match": str(v)})
    assert r.status_code == 409 and "Not editable" in r.json()["detail"]


def test_corrections_are_desk_only(seeded, client, public_client):
    login(client, "boat5")
    assert client.post("/v1/cases/BR-151/check").status_code == 403
    login(public_client, "priya", "rakshasetu")
    assert public_client.post("/v1/cases/BR-151/check").status_code == 404


def test_correcting_the_facts_re_runs_the_priority_rules(seeded, client, app_db):
    login(client, "priya")
    pid = one(app_db, "SELECT public_id FROM cases WHERE priority = 'P2' AND district_id = "
                      "(SELECT id FROM districts WHERE name = 'Gopalganj') ORDER BY id LIMIT 1")
    v = client.get(f"/v1/cases/{pid}").json()["version"]
    r = client.patch(f"/v1/cases/{pid}", json={"changes": {"needs": ["medical_urgent"]}, "reason": "caller: grandmother unconscious"},
                     headers={"If-Match": str(v)})
    assert r.status_code == 200
    case = client.get(f"/v1/cases/{pid}").json()
    assert case["priority"] == "P1" and "urgent medical need" in case["priority_reasons"]
    login(client, "rdas")
    events = client.get("/v1/audit", params={"case_id": case["id"]}).json()
    change = [e for e in events if e["action"] == "case.priority_changed"][-1]
    assert change["data"]["from"] == "P2" and change["data"]["to"] == "P1" and "unconscious" in change["reason"]
