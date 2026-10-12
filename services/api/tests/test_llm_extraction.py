"""PRD §8.2 / R13 with a stand-in model (a test double, never a real provider): the model proposes,
rules check the quotes and cross-check with keywords, people decide."""

import copy
import uuid

import pytest
from sqlalchemy import text

from app.core.jobs import drain
from app.pipeline import register_handlers
from app.providers import llm
from app.providers.base import AllProvidersFailed, ChainResult
from tests.conftest import login, needs_db, one

pytestmark = needs_db
LINE = "Thawe gaon mein, Durga mandir ke peeche, pul ke paas, chhat pe 6 log fase hain. Paani ghus gaya hai, ek buzurg hain, dawai chahiye."
MODEL_OUTPUT = {
    "language": "hi",
    "people_count": {"value": 6, "kind": "stated", "quote": "chhat pe 6 log fase hain"},
    "hazards": [{"type": "trapped_on_roof", "quote": "chhat pe 6 log fase hain"},
                {"type": "water_entering", "quote": "Paani ghus gaya hai"}],
    "needs": [{"type": "medicine", "quote": "dawai chahiye"}],
    "vulnerable": [{"type": "elderly", "quote": "ek buzurg hain"}],
    "location": {"village_or_locality": {"original": "Thawe", "latin": "Thawe", "quote": "Thawe gaon mein"},
                 "district": None, "state": "Bihar",
                 "landmarks": [{"type": "temple", "name": "Durga", "relation": "behind", "quote": "Durga mandir ke peeche"},
                               {"type": "bridge", "name": None, "relation": "near", "quote": "pul ke paas"}]},
    "person_names": [], "callback_phone": None, "reporter_on_site": False}


class StandIn:
    """Replaces app.providers.llm.extract_json for a test; counts calls."""

    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), 0

    def __call__(self, system, user, schema, est_tokens=0):
        self.calls += 1
        out = self.outputs.pop(0) if len(self.outputs) > 1 else self.outputs[0]
        if isinstance(out, Exception):
            raise out
        return ChainResult(value=out, provider="groq_gpt_oss_120b", model="openai/gpt-oss-120b", latency_ms=1200)


@pytest.fixture
def desk(seeded, client, owner_db):
    register_handlers()
    with owner_db.begin() as c:
        c.execute(text("TRUNCATE extraction_cache"))
    login(client, "priya")

    def submit(line=LINE):
        rid = client.post("/v1/ingest/desk", json={"incident": "BR", "text": line, "client_id": str(uuid.uuid4())}).json()["report_id"]
        return rid
    return submit


def _case(client, app_db, rid):
    return client.get(f"/v1/cases/{one(app_db, 'SELECT case_id FROM reports WHERE id = :r', r=rid)}").json()


def test_model_fields_carry_ai_chips_and_checked_quotes(desk, client, app_db, monkeypatch):
    monkeypatch.setattr(llm, "extract_json", StandIn([MODEL_OUTPUT]))
    rid = desk()
    drain(app_db)
    case = _case(client, app_db, rid)
    prov = case["provenance"]
    assert prov["people_count"]["method"] == "ai" and "amber" not in prov["people_count"]
    assert {p["value"] for p in prov["hazards"]} == {"trapped_on_roof", "water_entering"}
    receipt = case["reports"][0]["receipt"]
    assert receipt[0]["by"] == "AI" and "openai/gpt-oss-120b" in receipt[0]["detail"]
    assert receipt[1] == {"step": "quotes", "by": "Rule", "detail": "quotes ✓"}


def test_a_quote_the_caller_never_said_is_amber(desk, client, app_db, monkeypatch):
    out = copy.deepcopy(MODEL_OUTPUT)
    out["people_count"] = {"value": 9, "kind": "stated", "quote": "nau log the"}   # invented
    monkeypatch.setattr(llm, "extract_json", StandIn([out]))
    rid = desk()
    drain(app_db)
    p = _case(client, app_db, rid)["provenance"]["people_count"]
    assert p["value"] == 9 and p["amber"] == "quote not found in the report" and p["checked"] is False


def test_a_fact_the_model_dropped_is_kept_by_the_keywords_and_marked_amber(desk, client, app_db, monkeypatch):
    out = copy.deepcopy(MODEL_OUTPUT)
    out["needs"] = []                                                  # the model missed "dawai"
    monkeypatch.setattr(llm, "extract_json", StandIn([out]))
    rid = desk()
    drain(app_db)
    case = _case(client, app_db, rid)
    assert case["needs"] == ["medicine"]
    need = case["provenance"]["needs"][0]
    assert need["method"] == "rule" and "language model missed" in need["amber"]


def test_output_outside_the_contract_is_retried_once_then_rules_take_over(desk, client, app_db, monkeypatch):
    bad = {**MODEL_OUTPUT, "priority": "P1"}                           # a priority field is not allowed
    stand_in = StandIn([bad, bad])
    monkeypatch.setattr(llm, "extract_json", stand_in)
    rid = desk()
    drain(app_db)
    case = _case(client, app_db, rid)
    assert stand_in.calls == 2
    assert case["provenance"]["people_count"]["method"] == "rule"
    assert "didn't fit the contract" in case["reports"][0]["receipt"][0]["detail"]


def test_model_down_means_a_rule_made_case_now_and_an_ai_backfill_later(desk, client, app_db, monkeypatch, owner_db):
    down = AllProvidersFailed([{"provider": "groq_gpt_oss_120b", "outcome": "failed: timeout"},
                               {"provider": "gemini_flash", "outcome": "failed: HTTP 503"}])
    monkeypatch.setattr(llm, "extract_json", StandIn([down]))
    rid = desk()
    drain(app_db)
    case = _case(client, app_db, rid)
    assert case["public_id"].startswith("BR-") and case["provenance"]["people_count"]["method"] == "rule"
    assert one(app_db, "SELECT count(*) FROM jobs WHERE kind = 'llm.backfill' AND done_at IS NULL") == 1
    monkeypatch.setattr(llm, "extract_json", StandIn([MODEL_OUTPUT]))  # the model is back
    with owner_db.begin() as c:
        c.execute(text("UPDATE jobs SET run_at = now() WHERE kind = 'llm.backfill'"))
    drain(app_db)
    case = _case(client, app_db, rid)
    assert case["provenance"]["people_count"]["method"] == "ai"
    assert any(r["step"] == "backfill" for r in case["reports"][0]["receipt"])
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'case.updated' AND case_id = :c", c=case["id"]) == 1


def test_no_keys_at_all_is_not_an_outage_and_queues_no_backfill(desk, app_db, monkeypatch):
    skipped = AllProvidersFailed([{"provider": "groq_gpt_oss_120b", "outcome": "skipped: no GROQ_API_KEY"}])
    monkeypatch.setattr(llm, "extract_json", StandIn([skipped]))
    desk()
    drain(app_db)
    assert one(app_db, "SELECT count(*) FROM jobs WHERE kind = 'llm.backfill'") == 0


def test_the_same_text_is_read_from_the_cache_without_a_second_call(desk, client, app_db, monkeypatch):
    stand_in = StandIn([MODEL_OUTPUT])
    monkeypatch.setattr(llm, "extract_json", stand_in)
    desk()
    drain(app_db)
    rid = desk()
    drain(app_db)
    assert stand_in.calls == 1
    assert "cached result" in _case(client, app_db, rid)["reports"][-1]["receipt"][0]["detail"]


def test_backfill_waits_while_the_language_model_is_switched_off(desk, client, app_db, monkeypatch):
    login(client, "admin")
    client.post("/v1/demo/language-model", json={"on": False})
    login(client, "priya")
    desk()
    drain(app_db)                     # the case is made by rules; the back-fill tries and is told to wait
    for _ in range(3):                # however often it comes round, it waits without using up attempts
        with app_db.begin() as c:
            c.execute(text("UPDATE jobs SET run_at = now() WHERE kind = 'llm.backfill'"))
        drain(app_db)
    assert one(app_db, "SELECT error FROM jobs WHERE kind = 'llm.backfill'") == "waiting: language model off"
    assert one(app_db, "SELECT attempts FROM jobs WHERE kind = 'llm.backfill'") == 0
    assert one(app_db, "SELECT done_at IS NULL AND dead_at IS NULL FROM jobs WHERE kind = 'llm.backfill'")


def test_the_model_never_sees_a_phone_number(desk, client, app_db, monkeypatch):
    """P1 #11: numbers become <PHONE_n> before the call, and come back in the result after it."""
    sent = []
    out = copy.deepcopy(MODEL_OUTPUT)
    out["callback_phone"] = "<PHONE_1>"

    class Spy(StandIn):
        def __call__(self, system, user, schema, est_tokens=0):
            sent.append(user)
            return super().__call__(system, user, schema, est_tokens)
    monkeypatch.setattr(llm, "extract_json", Spy([out]))
    rid = desk(LINE + " Mera number 98765 43210 hai, ya +91 98765 43211.")
    drain(app_db)
    assert sent and "98765" not in sent[0] and "<PHONE_1>" in sent[0] and "<PHONE_2>" in sent[0]
    assert one(app_db, "SELECT extraction->>'callback_phone' FROM reports WHERE id = :r", r=rid) == "98765 43210"
