"""T4 (PRD §13.6, N2 / scenario B): Ramesh Das and Rajesh Das, same village and headcount, different phones
→ two cases, nothing above "weak", and the names shown in red as the reason it wasn't merged."""

import uuid

import pytest

from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one, rows

pytestmark = [needs_db, pytest.mark.scenario]


def test_t4_ramesh_das_and_rajesh_das_stay_two_cases_and_the_refusal_is_shown(seeded, client, app_db):
    register_handlers()
    login(client, "priya")

    def report(text, phone):
        return client.post("/v1/ingest/desk", json={"incident": "BR", "text": text, "phone": phone,
                                                    "client_id": str(uuid.uuid4())}).json()["report_id"]
    a = report("Ramesh Das, 5 log, Thawe gaon, mandir ke paas, chhat par fase hain", "+91 98765 50001")
    drain(app_db)
    b = report("Rajesh Das, 5 log, Thawe gaon, mandir ke paas, chhat par fase hain", "+91 98765 50002")
    drain(app_db)
    ca, cb = (one(app_db, "SELECT case_id FROM reports WHERE id = :r", r=r) for r in (a, b))
    assert ca != cb                                                              # two cases
    sug = rows(app_db, "SELECT strength, conflicts, score FROM merge_suggestions WHERE case_id = :c", c=cb)
    assert [s.strength for s in sug] == ["refused"]                              # nothing above "weak"
    assert sug[0].conflicts == ["name Rajesh ≠ Ramesh"]                          # the names, in red
    assert float(sug[0].score) >= 0.6                                            # it WOULD have looked strong
    line = one(app_db, "SELECT body::jsonb->'data'->>'line' FROM events WHERE action = 'merge.refused' ORDER BY seq DESC LIMIT 1")
    pid_a = one(app_db, "SELECT public_id FROM cases WHERE id = :c", c=ca)
    assert line == f"Not merged with {pid_a}: Rajesh ≠ Ramesh. Village and headcount alone are weak."
    assert "possible_duplicate" not in one(app_db, "SELECT flags FROM cases WHERE id = :c", c=cb)


def test_the_same_given_name_is_a_strong_signal(seeded, client, app_db):
    register_handlers()
    login(client, "priya")
    for phone in ("+91 98765 50003", "+91 98765 50004"):
        client.post("/v1/ingest/desk", json={"incident": "BR", "client_id": str(uuid.uuid4()), "phone": phone,
                                             "text": "Sunil Yadav, 4 log, Thawe gaon, mandir ke paas, fase hain"})
        drain(app_db)
    s = rows(app_db, "SELECT strength, reasons FROM merge_suggestions ORDER BY id DESC LIMIT 1")[0]
    assert s.strength == "strong" and "same name (Sunil)" in s.reasons
