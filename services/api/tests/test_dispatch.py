"""Dispatch suggestions (PRD F-C4): capability, then straight-line distance, then load; reasons on every line;
overdue / out-of-service / full teams greyed out with why; a team missing what the report needs is listed below
with the gap named, never as a suggestion; deterministic; an officer still decides."""

from types import SimpleNamespace

from sqlalchemy import text

from app.modules.dispatch.service import needed, rank
from tests.conftest import login, needs_db, one, rows

pytestmark = [needs_db]


def test_capabilities_follow_the_situation():
    assert needed(["trapped_on_roof"], []) == ({"boat"}, set())
    assert needed(["structure_collapsed"], ["medical_urgent"]) == ({"heavy_lift"}, {"medical"})
    assert needed([], ["food"]) == (set(), set())


def _team(**kw):
    base = dict(id=1, name="Team", agency="Agency", capabilities=[], has_app=True, radio_channel=None,
                status="available", status_reason=None, max_active=2, last_geom_at=None, lat=19.0, lng=72.0, active=0)
    return SimpleNamespace(**{**base, **kw})


def test_a_boat_team_is_not_the_answer_to_a_collapse():
    """The complaint that started this: a collapse needs heavy lift; a boat team is listed below with the gap
    named, and the screen is told there is no suitable team — never dressed up as "best suited"."""
    boats = [_team(id=1, name="Fire Brigade Boat 5", capabilities=["boat", "medical"]),
             _team(id=2, name="SDRF Boat 6", capabilities=["boat", "rope"])]
    out = rank({"lat": 19.05, "lng": 72.85, "hazards": ["structure_collapsed"], "needs": []}, boats)
    assert out["suggestions"] == []
    assert [t["name"] for t in out["more"]] == ["Fire Brigade Boat 5", "SDRF Boat 6"]
    assert all("no heavy_lift for this report" in t["line"] for t in out["more"])
    assert all(t["missing"] == ["heavy_lift"] for t in out["more"])


def test_a_team_with_what_it_needs_is_suggested_and_ranked_by_distance():
    near = _team(id=1, name="Near boat", capabilities=["boat"], lat=19.06, lng=72.85)
    far = _team(id=2, name="Far boat", capabilities=["boat"], lat=19.19, lng=72.94)
    other = _team(id=3, name="Rope team", capabilities=["rope"])
    out = rank({"lat": 19.05, "lng": 72.85, "hazards": ["trapped_on_roof"], "needs": []}, [far, other, near])
    assert [t["name"] for t in out["suggestions"]] == ["Near boat", "Far boat"]
    assert [t["rank"] for t in out["suggestions"]] == [1, 2]
    assert out["suggestions"][0]["line"].startswith("has boat for this report")     # the reason leads
    assert [t["name"] for t in out["more"]] == ["Rope team"]           # the gap is named, not hidden
    assert "no boat for this report" in out["more"][0]["line"]


def test_the_reason_leads_with_what_this_report_needs():
    """A road accident with an urgent medical need must read 'medical' first — not 'boat' (alphabetical once)."""
    team = _team(id=1, name="NDRF Team 5", agency="NDRF", capabilities=["boat", "medical", "rope"])
    out = rank({"lat": 19.05, "lng": 72.85, "hazards": [], "needs": ["medical_urgent"]}, [team])
    top = out["suggestions"][0]
    assert top["capabilities"] == ["medical", "boat", "rope"]          # relevance order, not alphabetical
    assert top["line"].startswith("medical cover for this report")
    plain = rank({"lat": 19.05, "lng": 72.85, "hazards": [], "needs": ["food"]}, [team])["suggestions"][0]
    assert plain["line"].startswith("closest available unit")          # nothing this report needs: say so plainly


def _roof_case(db):
    return one(db, "SELECT c.public_id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                   " AND 'trapped_on_roof' = ANY(c.hazards) AND c.geom IS NOT NULL ORDER BY c.id LIMIT 1")


def test_suggestions_rank_boats_by_distance_with_reasons_and_grey_out_the_unavailable(seeded, client, app_db):
    login(client, "rdas")
    pid = _roof_case(app_db)
    d = client.get(f"/v1/cases/{pid}/dispatch-suggestions").json()
    assert len(d["suggestions"]) >= 2 and all("boat" in t["capabilities"] for t in d["suggestions"])  # what it needs
    boats = [t["distance_km"] for t in d["suggestions"]]
    assert boats == sorted(boats) and d["suggestions"][0]["capabilities"].count("boat")               # then distance
    top = d["suggestions"]
    assert all("km straight-line" in t["line"] and "position" in t["line"] for t in top)  # labelled honestly
    others = [t for t in d["more"] if "boat" not in t["capabilities"]]
    assert others and all("no boat for this report" in t["line"] for t in others)         # below, gap named
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
