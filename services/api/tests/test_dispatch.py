"""Dispatch suggestions (PRD F-C4): capability, then straight-line distance, then load; reasons on every line;
overdue / out-of-service / full teams greyed out with why; deterministic; an officer still decides."""

from sqlalchemy import text

from app.modules.dispatch.service import needed
from tests.conftest import login, needs_db, one, rows

pytestmark = [needs_db]


def test_capabilities_follow_the_situation():
    assert needed(["trapped_on_roof"], []) == ({"boat"}, set())
    assert needed(["structure_collapsed"], ["medical_urgent"]) == ({"heavy_lift"}, {"medical"})
    assert needed([], ["food"]) == (set(), set())


def _roof_case(db):
    return one(db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                   " AND 'trapped_on_roof' = ANY(c.hazards) AND c.geom IS NOT NULL ORDER BY c.id LIMIT 1")


def test_suggestions_rank_boats_by_distance_with_reasons_and_grey_out_the_unavailable(seeded, client, app_db):
    login(client, "rdas")
    pid = _roof_case(app_db)
    d = client.get(f"/v1/cases/{pid}/dispatch-suggestions").json()
    ranked = d["suggestions"] + d["more"]
    has_boat = ["boat" in t["capabilities"] for t in ranked]
    assert len(d["suggestions"]) == 3 and has_boat == sorted(has_boat, reverse=True)     # capability first
    boats = [t["distance_km"] for t in ranked if "boat" in t["capabilities"]]
    assert boats == sorted(boats) and d["suggestions"][0]["capabilities"].count("boat")  # then distance
    top = d["suggestions"]
    assert all("km straight-line" in t["line"] and "position" in t["line"] for t in top)  # labelled honestly
    greyed = {g["name"]: g["why"] for g in d["greyed"]}
    assert greyed["SDRF Boat 4"].startswith("Out of service")
    assert client.get(f"/v1/cases/{pid}/dispatch-suggestions").json() == d                           # deterministic


def test_an_overdue_or_full_team_is_never_suggested(seeded, client, app_db):
    login(client, "rdas")
    pid = _roof_case(app_db)
    first = client.get(f"/v1/cases/{pid}/dispatch-suggestions").json()["suggestions"][0]
    with app_db.begin() as c:
        c.execute(text("UPDATE teams SET status = 'overdue' WHERE id = :t"), {"t": first["team_id"]})
    d = client.get(f"/v1/cases/{pid}/dispatch-suggestions").json()
    assert first["team_id"] not in [t["team_id"] for t in d["suggestions"]]
    assert any(g["team_id"] == first["team_id"] and "overdue" in g["why"] for g in d["greyed"])
    second = d["suggestions"][0]
    others = [r[0] for r in rows(app_db, "SELECT c.id FROM cases c JOIN districts d ON d.id = c.district_id"
                                          " WHERE d.name = 'Gopalganj' AND NOT EXISTS (SELECT 1 FROM assignments a WHERE"
                                          " a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT :n",
                                 n=second["max_active"] - second["active"])]
    with app_db.begin() as c:
        for cid in others:
            c.execute(text("INSERT INTO assignments (case_id, team_id, next_contact_due) VALUES (:c, :t, now() + interval '1 hour')"),
                      {"c": cid, "t": second["team_id"]})
    d = client.get(f"/v1/cases/{pid}/dispatch-suggestions").json()
    assert any(g["team_id"] == second["team_id"] and g["why"].startswith("at capacity") for g in d["greyed"])


def test_the_officers_row_button_names_the_best_team(seeded, client, app_db):
    login(client, "rdas")
    queue = client.get("/v1/queue?incident=BR").json()["rows"]
    assign = [r for r in queue if r["action"]["kind"] == "assign"]
    assert assign and all(r["action"]["label"].startswith("Assign → ") and r["action"]["target"] for r in assign)


def test_suggestions_stay_inside_the_scope(seeded, client, app_db):
    login(client, "mkumar")
    assert client.get(f"/v1/cases/{_roof_case(app_db)}/dispatch-suggestions").status_code == 404
