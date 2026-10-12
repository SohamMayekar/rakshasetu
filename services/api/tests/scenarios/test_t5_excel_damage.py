"""T5 (PRD §13.6, N4): 14 phones damaged by Excel → null, 0 auto-merges, counted in the summary.

Without the guard these would all read as one number (+919877000000), and "same phone + same village"
is exactly what auto-merges. With it, they are never identity; the control pair with an intact phone
still merges, so it's the guard, not luck, that keeps them apart."""

import pytest

from app.core.jobs import drain
from app.core.phones import normalise
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = [needs_db, pytest.mark.scenario]

# Each place has one mapped landmark of its type nearby, so every row gets a Medium pin and "circles overlap"
# counts: with a shared phone on top, these rows would score well past the auto-merge bar.
PLACES = [("Kalu Chhapra", "school ke paas"), ("Katiya", "hospital ke paas")]


def test_t5_excel_damaged_phones_never_merge(seeded, client, app_db):
    register_handlers()
    assert normalise("919877000000") == "+919877000000"          # what a naive importer would have used
    lines = ["Mob,Kitne log,Gaon,Location,Remarks"]
    for i in range(14):
        damaged = "9.19877E+11" if i % 2 == 0 else "919877000000"
        village, landmark = PLACES[i % 2]
        lines.append(f"{damaged},5,{village},{landmark},chhat par fase hain")
    lines += ["98765 62001,5,Bhore,hospital ke paas,chhat par fase hain"] * 2                 # the control pair
    login(client, "priya")
    imp = client.post("/v1/imports", files={"file": ("t5.csv", ("\n".join(lines) + "\n").encode(), "text/csv")},
                      data={"incident": "BR"}).json()
    client.post(f"/v1/imports/{imp['id']}/mapping", json={"mapping": imp["proposed"]})
    drain(app_db)
    imp = client.get(f"/v1/imports/{imp['id']}").json()
    key = f"{imp['file_sha256']}:%"

    assert imp["phones_damaged"] == 14 and "14 phone numbers damaged by Excel, not used" in imp["summary"]
    assert one(app_db, "SELECT count(*) FROM reports WHERE idempotency_key LIKE :k AND reporter_phone_hash IS NULL",
               k=key) == 14                                                                 # null, never identity
    damaged_cases = ("SELECT r.case_id FROM reports r JOIN evidence e ON e.report_id = r.id"
                     " WHERE r.idempotency_key LIKE :k AND (e.meta->>'row')::int <= 15")
    assert one(app_db, f"SELECT count(*) FROM merges WHERE decided_by = 'rule' AND (source_case_id IN ({damaged_cases})"
                       f" OR target_case_id IN ({damaged_cases}))", k=key) == 0          # 0 auto-merges
    assert one(app_db, "SELECT count(*) FROM cases c JOIN reports r ON r.case_id = c.id"
                       " WHERE r.idempotency_key LIKE :k AND 'phone_damaged_by_excel' = ANY(c.flags)", k=key) == 14
    assert imp["merged"] == 1                                                               # the control pair merged
    strong = one(app_db, "SELECT count(*) FROM merge_suggestions s JOIN reports r ON r.case_id = s.case_id"
                         " WHERE r.idempotency_key LIKE :k AND s.strength = 'strong'", k=key)
    assert strong > 0          # the look-alikes are shown to a person as likely duplicates, never merged by a rule
