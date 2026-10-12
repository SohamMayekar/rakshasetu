"""T9 (PRD §13.6, E13/E14): on-site No → reopen P1 · distant relative's No → disputed, no auto-close · a
stranger → rejected · silence → closes. The family is never required to do anything."""

import uuid

import pytest
from sqlalchemy import text

from app.contracts import CanonicalReport, Content, Reporter, Source
from app.core.eventlog import Actor
from app.core.jobs import drain
from app.modules.escalations.ticker import tick
from app.modules.intake.service import accept
from app.modules.public.router import device_hash
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = [needs_db, pytest.mark.scenario]

ON_SITE = "Hum log chhat par hain, Katiya gaon mein, 4 log hain, aspatal ke paas, paani badh raha hai"
FAR = "Mere mummy papa Katiya gaon mein fase hain, 4 log hain, aspatal ke paas, paani badh raha hai"


def _rescued_case(client, db, text_, relation="unknown"):
    """A case reported from a device, rescued (nobody left). Returns (public id, device id)."""
    register_handlers()
    device = str(uuid.uuid4())
    # The same registration as POST /v1/public/text-turns (without its wait for the case, which needs a worker)
    report = CanonicalReport(schema_version="1", idempotency_key=str(uuid.uuid4()), channel="web_form", incident_hint="BR",
                             reporter=Reporter(device_id=device), content=Content(text=text_), source=Source(system="reporter-pwa"))
    with db.begin() as c:
        accept(c, report, source_ns=f"voice:{device_hash(device)[:16]}", actor=Actor("reporter", "test", "reporter"),
               lane="live_voice")
    drain(db)
    rid = one(db, "SELECT id FROM reports WHERE device_hash IS NOT NULL ORDER BY id DESC LIMIT 1")
    if relation != "unknown":
        with db.begin() as c:
            c.execute(text("UPDATE reports SET reporter_relation = :r WHERE id = :id"), {"r": relation, "id": rid})
    pid = one(db, "SELECT c.public_id FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.id = :r", r=rid)
    login(client, "rdas")
    tid = one(db, "SELECT id FROM teams WHERE name = 'Fire & Rescue Boat 5'")
    assert client.post("/v1/assignments", json={"case": pid, "team_id": tid}).status_code == 201
    login(client, "boat5")
    assert client.post(f"/v1/cases/{pid}/rescues", json={"people_taken": 4, "anyone_left": "no"}).status_code == 200
    client.cookies.clear()
    return pid, device


def _confirm(client, pid, device, answer):
    return client.post(f"/v1/public/cases/{pid}/confirm", json={"device_id": device, "answer": answer})


def test_t9_the_person_on_site_says_no_and_it_reopens_as_p1_with_its_original_time(seeded, client, app_db):
    pid, device = _rescued_case(client, app_db, ON_SITE)
    since = one(app_db, "SELECT queue_since FROM cases WHERE public_id = :p", p=pid)
    st = client.get(f"/v1/public/cases/{pid}/status?device={device}").json()
    assert st["check"] == {"people_taken": 4, "answered": None}
    r = _confirm(client, pid, device, "no")
    assert r.status_code == 200 and r.json()["result"] == "reopened"
    assert one(app_db, "SELECT status IN ('reported', 'checked') AND priority = 'P1' AND 'reopened' = ANY(flags)"
                       " FROM cases WHERE public_id = :p", p=pid)
    assert one(app_db, "SELECT queue_since FROM cases WHERE public_id = :p", p=pid) == since
    login(client, "rdas")
    row = next(r for r in client.get("/v1/queue?incident=BR").json()["rows"] if r["public_id"] == pid)
    assert row["broken"] and row["chip"] == "reopened"
    assert _confirm(client, pid, device, "yes").status_code in (409,)               # one answer per device


def test_t9_a_relative_far_away_says_no_and_it_cant_close_until_an_officer_acts(seeded, client, app_db):
    pid, device = _rescued_case(client, app_db, FAR, relation="family")
    r = _confirm(client, pid, device, "no")
    assert r.json()["result"] == "disputed"
    with app_db.begin() as c:
        c.execute(text("UPDATE cases SET rescued_at = now() - interval '3 hours' WHERE public_id = :p"), {"p": pid})
    tick(app_db)
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "rescued"           # no auto-close
    login(client, "rdas")
    row = next(r for r in client.get("/v1/queue?incident=BR").json()["rows"] if r["public_id"] == pid)
    assert row["chip"] == "disputed: radio the team" and row["action"]["label"] == "Radio the team, then decide"
    assert client.post(f"/v1/cases/{pid}/close", json={"reason": "Boat 5 confirmed all 4 on VHF"}).status_code == 200


def test_t9_a_stranger_with_the_case_number_cant_answer(seeded, client, app_db):
    pid, _ = _rescued_case(client, app_db, ON_SITE)
    stranger = str(uuid.uuid4())
    assert client.get(f"/v1/public/cases/{pid}/status?device={stranger}").json()["check"] is None
    assert _confirm(client, pid, stranger, "no").status_code == 403
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "rescued"


def test_t9_silence_closes_normally_and_yes_adds_the_badge(seeded, client, app_db):
    pid, _ = _rescued_case(client, app_db, ON_SITE)
    with app_db.begin() as c:
        c.execute(text("UPDATE cases SET rescued_at = now() - interval '3 hours' WHERE public_id = :p"), {"p": pid})
    tick(app_db)
    assert one(app_db, "SELECT status FROM cases WHERE public_id = :p", p=pid) == "closed"           # silence: closed
    pid2, device2 = _rescued_case(client, app_db, FAR, relation="family")
    assert _confirm(client, pid2, device2, "yes").json() == {"recorded": "yes"}
    with app_db.begin() as c:
        c.execute(text("UPDATE cases SET rescued_at = now() - interval '3 hours' WHERE public_id = :p"), {"p": pid2})
    tick(app_db)
    assert one(app_db, "SELECT resolution FROM cases WHERE public_id = :p", p=pid2).endswith("· confirmed by family")
