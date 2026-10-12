"""T10 (PRD §13.6, scenario M / N28): with the language model off, a typed report still becomes a case
with an ID in ≤ 5 s, and its chips read Rule. (LLM-error and STT-failure branches join in m19/m20.)"""

import time
import uuid

import pytest

from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import login, needs_db, one

pytestmark = [needs_db, pytest.mark.scenario]
LINE = "Thawe gaon mein, Durga mandir ke peeche, pul ke paas, chhat pe 6 log fase hain. Paani ghus gaya hai, ek buzurg hain, dawai chahiye."


def test_t10_language_model_off_a_typed_report_becomes_a_rule_made_case_fast(seeded, client, app_db):
    register_handlers()
    login(client, "admin")
    assert client.post("/v1/demo/language-model", json={"on": False}).json() == {"language_model": "off"}
    assert client.get("/v1/demo/status").json()["language_model"] == "off"
    login(client, "priya")
    started = time.monotonic()
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "text": LINE, "client_id": str(uuid.uuid4())}).json()["report_id"]
    drain(app_db)
    case_ref = one(app_db, "SELECT case_id FROM reports WHERE id = :r", r=rid)
    assert case_ref is not None and time.monotonic() - started < 5.0
    case = client.get(f"/v1/cases/{case_ref}").json()
    assert case["public_id"].startswith("BR-")
    assert case["people_count"] == 6 and set(case["hazards"]) == {"trapped_on_roof", "water_entering"}
    assert case["needs"] == ["medicine"] and case["vulnerable"] == ["elderly"]
    prov = case["provenance"]
    assert prov["people_count"]["method"] == "rule" and prov["people_count"]["quote"] == "chhat pe 6 log fase hain"
    assert all(p["method"] == "rule" and not p["checked"] for p in prov["hazards"] + prov["needs"] + prov["vulnerable"])
    assert case["summary"] == "6 people · roof · water inside · medicine · elderly"
    assert "language model off" in case["reports"][0]["receipt"][0]["detail"]


def test_desk_preview_gives_live_chips_without_storing_anything(seeded, client, app_db):
    login(client, "priya")
    before = one(app_db, "SELECT count(*) FROM reports")
    r = client.post("/v1/ingest/desk/preview", json={"text": "Rajesh Das, 5 log, mandir ke paas"}).json()
    assert r["summary"].startswith("5 people")
    assert r["extraction"]["person_names"][0]["name"] == "Rajesh Das"
    assert one(app_db, "SELECT count(*) FROM reports") == before


def test_only_the_admin_can_flip_the_switch(seeded, client):
    login(client, "priya")
    assert client.post("/v1/demo/language-model", json={"on": False}).status_code == 403


def test_t10_llm_error_a_typed_report_still_becomes_a_case_fast(seeded, client, app_db, monkeypatch):
    from app.providers import llm
    from app.providers.base import AllProvidersFailed

    def down(*a, **k):
        raise AllProvidersFailed([{"provider": "groq_gpt_oss_120b", "outcome": "failed: HTTP 500"}])
    monkeypatch.setattr(llm, "extract_json", down)
    register_handlers()
    login(client, "priya")
    started = time.monotonic()
    rid = client.post("/v1/ingest/desk", json={"incident": "BR", "text": LINE, "client_id": str(uuid.uuid4())}).json()["report_id"]
    drain(app_db)
    assert one(app_db, "SELECT case_id FROM reports WHERE id = :r", r=rid) is not None
    assert time.monotonic() - started < 5.0
