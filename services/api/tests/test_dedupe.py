"""F-D1: candidates, the agreeing-signal score (missing = 0), the decision table and the per-incident lock."""

import threading
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.jobs import drain
from app.modules.dedupe.signals import Household, score
from app.pipeline import register_handlers
from app.pipeline.run import process_report
from tests.conftest import login, needs_db, one, rows

pytestmark = needs_db
DEMO = "Thawe gaon mein, Durga mandir ke peeche, pul ke paas, chhat pe 6 log fase hain. Paani ghus gaya hai, ek buzurg hain, dawai chahiye."
SON = "Mere mummy papa Thawe gaon mein hain, Durga mandir ke peeche, pul ke paas. 6 log chhat par fase hain, dawai chahiye."
NOW = datetime.now(UTC)


def H(**kw):
    base = dict(case_id=None, village="Thawe", lat=26.4374, lng=84.3947, radius_m=150, confidence="medium",
                landmarks={"osm:1": "temple", "osm:2": "bridge"}, people=6, at=NOW)
    return Household(**{**base, **kw})


def test_missing_evidence_counts_zero_and_without_a_phone_the_most_is_0_70():
    full = score(H(phones={"p"}), H(phones={"p"}, at=NOW + timedelta(minutes=4)))
    assert full.total == pytest.approx(0.95)            # phone .30 + place .20 + geo .20 + landmarks .10 + headcount .10 + time .05
    no_phone = score(H(phones={"a"}), H(phones={"b"}))
    assert no_phone.total <= 0.70 and "phone_or_device" not in no_phone.signals   # a different phone isn't evidence against
    bare = score(H(village=None, lat=None, landmarks={}, people=None), H())
    assert bare.total <= 0.05                           # nothing known → nothing scored (only time can agree)


def test_geo_counts_only_when_both_pins_are_medium_or_better():
    assert "geo" not in score(H(confidence="low", radius_m=1500), H()).signals
    assert "geo" in score(H(), H()).signals


def test_a_headcount_gap_lowers_the_score_but_never_blocks():
    s = score(H(people=4), H(people=6))
    assert s.signals["headcount"] == 0.5 and "headcount 4 ≠ 6" in s.conflicts


def desk(client, text, phone=None):
    body = {"incident": "BR", "text": text, "client_id": str(uuid.uuid4())}
    if phone:
        body["phone"] = phone
    return client.post("/v1/ingest/desk", json=body).json()["report_id"]


def case_of(app_db, rid):
    return one(app_db, "SELECT case_id FROM reports WHERE id = :r", r=rid)


@pytest.fixture
def desk_client(seeded, client):
    register_handlers()
    login(client, "priya")
    return client


def test_the_sons_report_from_another_phone_is_suggested_with_reasons(desk_client, app_db):
    a = desk(desk_client, DEMO, phone="+91 98765 40001")
    drain(app_db)
    b = desk(desk_client, SON, phone="+91 98765 40002")
    drain(app_db)
    assert case_of(app_db, a) != case_of(app_db, b)                          # suggested, not merged
    s = rows(app_db, "SELECT strength, reasons, score FROM merge_suggestions WHERE case_id = :c", c=case_of(app_db, b))[0]
    assert s.strength == "strong" and 0.6 <= float(s.score) < 0.85
    assert any(r.startswith("same village (Thawe)") for r in s.reasons) and any("same landmarks" in r for r in s.reasons)
    assert "possible_duplicate" in one(app_db, "SELECT flags FROM cases WHERE id = :c", c=case_of(app_db, b))
    line = one(app_db, "SELECT body::jsonb->'data'->>'line' FROM events WHERE action = 'merge.suggested' ORDER BY seq DESC LIMIT 1")
    assert line.startswith(f"Likely same household as {one(app_db, 'SELECT public_id FROM cases WHERE id = :c', c=case_of(app_db, a))}: ")


def test_same_phone_and_village_but_a_different_count_is_only_suggested(desk_client, app_db):
    a = desk(desk_client, DEMO, phone="+91 98765 40013")
    drain(app_db)
    b = desk(desk_client, SON.replace("6 log", "7 log"), phone="+91 98765 40013")
    drain(app_db)
    assert case_of(app_db, a) != case_of(app_db, b)
    s = rows(app_db, "SELECT strength, conflicts FROM merge_suggestions WHERE case_id = :c", c=case_of(app_db, b))[0]
    assert s.strength == "strong" and s.conflicts == ["headcount 7 ≠ 6"]    # the difference, in red


def test_after_two_separate_households_the_phone_stops_counting_as_identity(desk_client, app_db):
    """The relay rule's trade-off, written down: once a phone has two separate cases, even a true repeat from it
    is only suggested, never auto-merged. A person merges it in one click."""
    desk(desk_client, DEMO, phone="+91 98765 40023")
    drain(app_db)
    desk(desk_client, SON.replace("6 log", "7 log"), phone="+91 98765 40023")
    drain(app_db)
    c = desk(desk_client, DEMO, phone="+91 98765 40023")
    drain(app_db)
    assert one(app_db, "SELECT count(*) FROM merges WHERE source_report_id = :r", r=c) == 0
    reasons = rows(app_db, "SELECT reasons FROM merge_suggestions WHERE case_id = :c", c=case_of(app_db, c))
    assert any("isn't used as identity" in " ".join(r.reasons) for r in reasons)


def test_the_same_phone_with_the_same_details_auto_merges_into_the_older_case(desk_client, app_db):
    a = desk(desk_client, DEMO, phone="+91 98765 40003")
    drain(app_db)
    c = desk(desk_client, DEMO.replace("ek buzurg", "ek buzurg aur do bachche"), phone="+91 98765 40003")
    drain(app_db)
    assert case_of(app_db, c) == case_of(app_db, a)                          # auto-merged
    target = case_of(app_db, a)
    assert one(app_db, "SELECT status FROM reports WHERE id = :r", r=c) == "merged"
    assert "child" in one(app_db, "SELECT vulnerable FROM cases WHERE id = :t", t=target)   # needs/vulnerable = union
    m = rows(app_db, "SELECT decided_by, reasons, snapshot FROM merges WHERE source_report_id = :r", r=c)[0]
    assert m.decided_by == "rule" and "same phone" in m.reasons and m.snapshot["target"]["id"] == target
    assert one(app_db, "SELECT count(*) FROM evidence WHERE case_id = :t AND type = 'merge'", t=target) == 1


def test_two_reports_of_one_household_in_the_same_second_make_one_case(desk_client, app_db):
    a = desk(desk_client, DEMO, phone="+91 98765 40004")
    b = desk(desk_client, DEMO + " Jaldi aaiye.", phone="+91 98765 40004")
    errors = []

    def run(rid):
        try:
            process_report(app_db, {"report_id": rid})
        except Exception as e:  # surface thread errors
            errors.append(e)
    ts = [threading.Thread(target=run, args=(r,)) for r in (a, b)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert not errors and case_of(app_db, a) == case_of(app_db, b)          # the per-incident lock serialised them


def test_one_shared_village_is_not_enough_evidence(desk_client, app_db):
    a = desk(desk_client, "Uchkagaon mein 3 log fase hain", phone="+91 98765 40005")
    drain(app_db)
    b = desk(desk_client, "Uchkagaon mein 8 log, khana nahi hai", phone="+91 98765 40006")
    drain(app_db)
    assert one(app_db, "SELECT count(*) FROM merge_suggestions WHERE case_id = :c", c=case_of(app_db, b)) == 0
    assert case_of(app_db, a) != case_of(app_db, b)


def test_other_incidents_are_never_candidates(desk_client, app_db):
    desk(desk_client, DEMO, phone="+91 98765 40007")
    drain(app_db)
    od_cases = one(app_db, "SELECT count(*) FROM merge_suggestions s JOIN cases c ON c.id = s.candidate_case_id"
                           " WHERE c.incident_id <> (SELECT id FROM incidents WHERE code = 'BR')")
    assert od_cases == 0


def test_a_shared_surname_alone_scores_nothing():
    s = score(H(names=["Ramesh Das"]), H(names=["Das"]))       # "Das" has no given name to compare
    assert "names" not in s.signals and not s.conflicts


def test_the_relay_phone_rule_keeps_ten_households_on_one_volunteer_phone_apart(desk_client, app_db):
    """N2/E5: a volunteer coordinator's phone reports 10 different families in one village."""
    families = ["Ramesh", "Suresh", "Mahesh", "Dinesh", "Naresh", "Mukesh", "Rakesh", "Umesh", "Kamlesh", "Yogesh"]
    for i, given in enumerate(families):
        desk(desk_client, f"{given} Paswan ka parivar, {3 + i % 4} log, Thawe gaon, mandir ke paas, fase hain",
             phone="+91 98765 49999")
        drain(app_db)
    ids = {r[0] for r in rows(app_db, "SELECT case_id FROM reports WHERE reporter_phone_hash IS NOT NULL"
                                      " AND idempotency_key NOT LIKE 'br-%' AND text LIKE '%Paswan ka parivar%'")}
    assert len(ids) == 10                                                    # ten households, ten cases
    assert one(app_db, "SELECT count(*) FROM merges WHERE decided_by = 'rule' AND source_report_id IN"
                       " (SELECT id FROM reports WHERE text LIKE '%Paswan ka parivar%')") == 0
