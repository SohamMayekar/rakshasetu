"""The promise bar (PRD F-C6): every number equals its own database query, the funnel adds up, and a number
inverts only when its promise is broken. And /v1/integrity: 0 problems on a healthy database."""

import uuid

from sqlalchemy import text

from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = [needs_db]


def _bar(client, who="rdas"):
    login(client, who)
    r = client.get("/v1/metrics/promises?incident=BR")
    assert r.status_code == 200, r.text
    return r.json()


def test_every_number_is_its_query_and_the_funnel_adds_up(seeded, client, app_db):
    b = _bar(client, "seoc")                                   # the SEOC viewer sees the whole incident's totals
    lost = b["lost"]
    assert lost["adds_up"] and lost["reports"] == lost["cases"] + lost["merged"] + lost["to_check"] + lost["without_home"]
    assert lost["reports"] == one(app_db, "SELECT count(*) FROM reports WHERE incident_id = (SELECT id FROM incidents WHERE code = 'BR')")
    assert lost["cases"] == one(app_db, "SELECT count(DISTINCT case_id) FROM reports WHERE incident_id ="
                                        " (SELECT id FROM incidents WHERE code = 'BR')")
    assert b["stale"]["p1_unowned"] == 0 and b["stale"]["overdue"] == 0 and not b["stale"]["broken"]   # E22 after a reset
    assert not b["lost"]["broken"] and not b["doubled"]["broken"]


def test_the_desk_sees_its_own_districts_and_the_bar_still_adds_up(seeded, client, app_db):
    whole, mine = _bar(client, "seoc"), _bar(client, "priya")
    assert mine["lost"]["reports"] < whole["lost"]["reports"] and mine["lost"]["adds_up"]
    assert mine["lost"]["cases"] == one(app_db, "SELECT count(DISTINCT r.case_id) FROM reports r JOIN cases c ON c.id = r.case_id"
                                               " JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'")


def test_a_merge_and_a_new_report_move_the_funnel_and_it_still_adds_up(seeded, client, app_db):
    register_handlers()
    before = _bar(client)
    login(client, "priya")
    for phone in ("+91 98765 66001", "+91 98765 66001"):     # the same household twice: one case, one merged report
        client.post("/v1/ingest/desk", json={"incident": "BR", "client_id": str(uuid.uuid4()), "phone": phone,
                                             "text": "Thawe gaon, Durga mandir ke peeche pul ke paas, 6 log chhat par fase hain"})
        drain(app_db)
    after = _bar(client)
    assert after["lost"]["reports"] == before["lost"]["reports"] + 2
    assert after["lost"]["cases"] == before["lost"]["cases"] + 1 and after["lost"]["merged"] == before["lost"]["merged"] + 1
    assert after["doubled"]["merged"] == before["doubled"]["merged"] + 1 and after["lost"]["adds_up"]


def test_a_broken_promise_inverts_its_number(seeded, client, app_db):
    cid = one(app_db, "SELECT c.id FROM cases c JOIN districts d ON d.id = c.district_id WHERE d.name = 'Gopalganj'"
                      " AND c.status IN ('reported', 'checked') AND NOT EXISTS (SELECT 1 FROM assignments a WHERE"
                      " a.case_id = c.id AND a.state IN ('open', 'overdue')) ORDER BY c.id LIMIT 1")
    with app_db.begin() as c:
        c.execute(text("UPDATE cases SET priority = 'P1', queue_since = now() - interval '6 minutes' WHERE id = :c"), {"c": cid})
    b = _bar(client)
    assert b["stale"]["p1_unowned"] == 1 and b["stale"]["broken"]


def test_integrity_is_zero_on_a_healthy_database_and_names_what_breaks(seeded, client, app_db, owner_db):
    login(client, "rdas")
    assert client.get("/v1/integrity").json()["problems"] == 0
    with owner_db.begin() as c:   # a case marked owned with nobody actually holding it
        c.execute(text("UPDATE cases SET status = 'assigned' WHERE id = (SELECT c.id FROM cases c WHERE c.status = 'reported'"
                       " AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.case_id = c.id) ORDER BY c.id LIMIT 1)"))
    r = client.get("/v1/integrity").json()
    assert r["problems"] == 1 and r["details"] == ["1 case(s) marked as owned with no live assignment"]
