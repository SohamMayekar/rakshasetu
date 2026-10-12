"""PRD F-C12: `make demo-reset` restores the starting state in under 10 s, and every scene resets on its own,
by replaying the earlier scenes through the real API (data/scenarios/BR/demo.yaml). Plus the demo controls'
guards: local listener, DEMO_MODE, System admin."""

import hashlib
import json
import time

import pytest

from app.modules.demo import scenes
from tests.conftest import TEST_OWNER_DB, login, needs_db, one

pytestmark = [needs_db, pytest.mark.scenario]


def test_a_reset_to_the_start_is_the_seed_under_10_s(seeded, client, app_db):
    t = time.monotonic()
    out = scenes.reset("son", owner_url=TEST_OWNER_DB, http=client)
    assert time.monotonic() - t < 10 and out["son_case"] is None
    assert one(app_db, "SELECT body::jsonb->'data'->>'reason' FROM events WHERE seq = 1") == "demo reset to scene 'son'"
    assert one(app_db, "SELECT count(*) FROM reports WHERE device_hash IS NOT NULL") == 0


def test_a_reset_to_never_doubled_starts_with_the_sons_case_from_the_recorded_clip(seeded, client, app_db):
    out = scenes.reset("merge", owner_url=TEST_OWNER_DB, http=client)
    pid = out["son_case"]
    c = one(app_db, "SELECT to_jsonb(c) FROM cases c WHERE public_id = :p", p=pid)
    assert c["priority"] == "P1" and c["people_count"] == 6 and c["status"] == "reported"
    assert one(app_db, "SELECT r.channel FROM reports r JOIN cases c ON c.id = r.case_id WHERE c.public_id = :p", p=pid) == "voice"
    assert one(app_db, "SELECT body::jsonb->'data'->>'synthetic_voice' FROM events WHERE action = 'demo.clip_played'") == "true"
    login(client, "rdas")
    lines = [e["line"] for e in client.get(f"/v1/cases/{pid}/timeline").json()["events"]]
    assert any("son-line.synthetic.ogg (a synthetic voice), through the same voice path a phone uses" in x for x in lines)


@pytest.mark.slow
def test_a_reset_to_the_receipts_replays_the_whole_spine_through_the_api(seeded, client, app_db):
    out = scenes.reset("receipts", owner_url=TEST_OWNER_DB, http=client)
    assert list(out["timings"]) == ["seed", "son", "merge", "sheet", "stale", "rescue"]
    pid = out["son_case"]
    c = one(app_db, "SELECT to_jsonb(c) FROM cases c WHERE public_id = :p", p=pid)
    assert c["status"] == "rescued" and "family_confirmed" in c["flags"] and c["attributes"]["person_names"] == ["Ramesh Das"]
    # never doubled: the forward folded in by a person; the Das family refused, not merged
    assert one(app_db, "SELECT count(*) FROM merges m JOIN cases c ON c.id = m.target_case_id WHERE c.public_id = :p", p=pid) == 1
    assert "name Rajesh ≠ Ramesh" in one(app_db, "SELECT s.conflicts FROM merge_suggestions s JOIN cases c ON"
                                                " c.id = s.candidate_case_id WHERE c.public_id = :p AND s.strength = 'refused'", p=pid)
    # never stale: Boat 2 went overdue on the record, the officer reassigned, Boat 2 owes a stand-down
    acts = [r for r in one(app_db, "SELECT array_agg(action ORDER BY seq) FROM events e JOIN cases c ON c.id = e.case_id"
                                   " WHERE c.public_id = :p", p=pid)]
    for a in ("demo.clock_advanced", "assignment.overdue", "rescue.partial", "rescue.recorded", "rescue.confirmed"):
        assert a in acts, a
    assert acts.index("demo.clock_advanced") < acts.index("assignment.overdue")
    assert one(app_db, "SELECT count(*) FROM assignments WHERE state IN ('open', 'overdue')"
                       " AND case_id = (SELECT id FROM cases WHERE public_id = :p)", p=pid) == 0

    login(client, "rdas")
    lines = [e["line"] for e in client.get(f"/v1/cases/{pid}/timeline").json()["events"]]
    assert "Fire & Rescue Boat 5: took 4, 2 still there · back to the queue with its original time" in lines
    assert "Fire & Rescue Boat 5: 2 more rescued, 6 of 6 in all, nobody left" in lines
    assert "The family confirmed: 6 rescued" in lines
    assert client.get("/v1/integrity").json()["problems"] == 0
    assert client.get("/v1/audit/verify").json()["ok"] is True
    st = client.get(f"/v1/public/cases/{pid}/status", params={"device": "demo-son-phone-0001"}).json()
    assert st["check"] == {"people_taken": 6, "answered": "yes"} and st["demo"] is True
    # F-C11 "done when": every item on the demo case opens its source, and its hash matches the file and the chain
    ev = client.get(f"/v1/cases/{pid}/timeline").json()["evidence"]
    kinds = sorted(e["type"] for e in ev)
    assert kinds == ["audio", "merge", "message", "radio", "rescue", "rescue", "transcript"], kinds
    for e in ev:
        r = client.get(f"/v1/evidence/{e['id']}/file")
        assert r.status_code == 200 and hashlib.sha256(r.content).hexdigest() == e["sha256"], e
        assert e["file_ok"] and e["chain_ok"], e
    rescues = [json.loads(client.get(f"/v1/evidence/{e['id']}/file").content) for e in ev if e["type"] == "rescue"]
    assert all(r["team"] == "Fire & Rescue Boat 5" and r["team_position"] and r["metres_from_pin"] is not None for r in rescues)


def test_a_reset_to_the_rescue_leaves_boat_5_waiting_on_the_real_clock(seeded, client, app_db, monkeypatch):
    monkeypatch.setattr(scenes, "PLAY", {**scenes.PLAY, "sheet": lambda st, s: None})   # the sheet isn't needed here
    pid = scenes.reset("rescue", owner_url=TEST_OWNER_DB, http=client)["son_case"]
    a = one(app_db, "SELECT to_jsonb(a) FROM assignments a JOIN cases c ON c.id = a.case_id WHERE c.public_id = :p"
                    " AND a.state = 'open'", p=pid)
    assert a["phase"] == "offered" and a["demo_clock"] is False
    assert one(app_db, "SELECT extract(epoch FROM next_contact_due - now()) FROM assignments WHERE id = :a", a=a["id"]) > 60
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'demo.clock_real'") == 1


def test_an_unknown_scene_is_refused_before_anything_is_wiped(seeded, client, app_db):
    before = one(app_db, "SELECT count(*) FROM events")
    with pytest.raises(scenes.ScriptError, match="no scene 'finale'"):
        scenes.reset("finale", owner_url=TEST_OWNER_DB, http=client)
    assert one(app_db, "SELECT count(*) FROM events") == before


def test_demo_controls_are_the_admins_on_the_local_listener_only(seeded, client, public_client):
    login(public_client, "admin", "rakshasetu")
    assert public_client.post("/v1/demo/reset", json={"scene": "son"}).status_code == 403
    login(client, "rdas")
    for method, path, body in (("post", "/v1/demo/reset", {"scene": "son"}), ("post", "/v1/demo/surge", {}),
                               ("post", "/v1/demo/play-clip", {"clip": "clips/son-line.synthetic.ogg"}),
                               ("get", "/v1/demo/qr?target=reporter", None), ("get", "/v1/demo/scenes", None)):
        r = getattr(client, method)(path, **({"json": body} if body is not None else {}))
        assert r.status_code == 403, (path, r.status_code)
    login(client, "admin")
    assert [s["id"] for s in client.get("/v1/demo/scenes").json()] == ["son", "merge", "sheet", "stale", "rescue", "receipts"]
    assert client.post("/v1/demo/play-clip", json={"clip": "clips/../demo.yaml"}).status_code == 422     # no path tricks
    assert client.post("/v1/demo/play-clip", json={"clip": "clips/nope.ogg"}).status_code == 404
    assert [c["clip"] for c in client.get("/v1/demo/clips").json()] == ["clips/son-line.synthetic.ogg"]


def test_the_qr_codes_point_at_the_public_address(seeded, client, monkeypatch):
    login(client, "admin")
    monkeypatch.setenv("PUBLIC_URL", "")
    assert client.get("/v1/demo/qr", params={"target": "reporter"}).status_code == 409
    monkeypatch.setenv("PUBLIC_URL", "https://example.trycloudflare.com/")
    r = client.get("/v1/demo/qr", params={"target": "reporter"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/svg+xml") and r.text.startswith("<svg")
    assert r.headers["x-qr-url"] == "https://example.trycloudflare.com/r"
    assert client.get("/v1/demo/qr", params={"target": "son"}).status_code == 404       # the son hasn't reported yet
