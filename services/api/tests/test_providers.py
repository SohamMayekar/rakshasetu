"""PRD §8.4: provider chains, fixture mode, the 80% cap, and request shapes (checked offline against the
providers' documented APIs; live calls are an integration check with real keys, `make provider-check`)."""

import json

import httpx
import pytest
from sqlalchemy import text

from app.providers import llm, stt, usage
from app.providers.base import AllProvidersFailed, ProviderUnavailable, run_chain
from tests.conftest import needs_db

pytestmark = needs_db


class Captured:
    def __init__(self, status=200, body=None):
        self.calls, self.status, self.body = [], status, body or {}

    def __call__(self, url, **kw):
        self.calls.append((url, kw))
        return httpx.Response(self.status, json=self.body, request=httpx.Request("POST", url))


@pytest.fixture
def live(monkeypatch, seeded, owner_db):
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    for k in ("SARVAM_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.setenv(k, f"test-{k}")
    with owner_db.begin() as c:
        c.execute(text("TRUNCATE provider_usage"))


def test_sarvam_request_matches_its_documented_shape(live, monkeypatch):
    cap = Captured(body={"transcript": "थावे में 6 लोग", "language_code": "hi-IN", "language_probability": 0.97})
    monkeypatch.setattr(httpx, "post", cap)
    t, model = stt.sarvam(b"RIFF....", 4.0)
    url, kw = cap.calls[0]
    assert url == "https://api.sarvam.ai/speech-to-text"
    assert kw["headers"] == {"api-subscription-key": "test-SARVAM_API_KEY"}
    assert kw["data"] == {"model": "saaras:v4", "mode": "transcribe", "language_code": "unknown"}
    assert "file" in kw["files"] and model == "saaras:v4"
    assert (t.text, t.language) == ("थावे में 6 लोग", "hi-IN")


def test_groq_whisper_request(live, monkeypatch):
    cap = Captured(body={"text": " six people ", "language": "hindi"})
    monkeypatch.setattr(httpx, "post", cap)
    t, _ = stt.groq_whisper(b"RIFF....", 3.0)
    url, kw = cap.calls[0]
    assert url == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert kw["data"]["model"] == "whisper-large-v3" and t.text == "six people"


def test_groq_llm_uses_strict_json_schema_and_no_priority_field(live, monkeypatch):
    cap = Captured(body={"choices": [{"message": {"content": '{"ok": true}'}}], "usage": {"total_tokens": 321}})
    monkeypatch.setattr(httpx, "post", cap)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean", "description": "x"}},
              "required": ["ok"], "additionalProperties": False}
    out, model = llm.groq("sys", "user", schema, 100)
    url, kw = cap.calls[0]
    assert url == "https://api.groq.com/openai/v1/chat/completions"
    rf = kw["json"]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert "description" not in json.dumps(rf["json_schema"]["schema"])
    assert kw["json"]["model"] == "openai/gpt-oss-120b" and kw["json"]["reasoning_effort"] == "low"
    assert out == {"ok": True}


def test_gemini_request(live, monkeypatch):
    cap = Captured(body={"candidates": [{"content": {"parts": [{"text": '{"ok": false}'}]}}]})
    monkeypatch.setattr(httpx, "post", cap)
    out, _ = llm.gemini("sys", "user", {"type": "object"}, 100)
    url, kw = cap.calls[0]
    assert url.endswith("/models/gemini-2.5-flash:generateContent") and kw["headers"] == {"x-goog-api-key": "test-GEMINI_API_KEY"}
    assert kw["json"]["generationConfig"]["responseMimeType"] == "application/json" and out == {"ok": False}


def test_primary_failure_falls_back_to_the_secondary(live, monkeypatch):
    calls = []

    def fake_post(url, **kw):
        calls.append(url)
        if "groq" in url:
            return httpx.Response(500, text="down", request=httpx.Request("POST", url))
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "{}"}]}}]},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", fake_post)
    res = llm.extract_json("s", "u", {"type": "object"})
    assert res.provider == "gemini_flash" and [a["outcome"][:6] for a in res.attempts] == ["failed", "ok"]


def test_no_keys_means_every_provider_is_skipped_not_errored(seeded, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    for k in ("SARVAM_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(AllProvidersFailed) as e:
        llm.extract_json("s", "u", {})
    assert all(a["outcome"].startswith("skipped") for a in e.value.attempts)


def test_fixture_mode_never_calls_the_network(seeded, monkeypatch):
    monkeypatch.setenv("PROVIDER_MODE", "fixture")
    monkeypatch.setenv("GROQ_API_KEY", "would-be-used")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: pytest.fail("network call in fixture mode"))
    with pytest.raises(ProviderUnavailable):
        llm.extract_json("s", "u", {})
    with pytest.raises(AllProvidersFailed):
        stt.transcribe(b"RIFF", 1.0, "0" * 64)


def test_stt_fixture_transcript_is_used_and_labelled(seeded, monkeypatch, tmp_path):
    monkeypatch.setenv("PROVIDER_MODE", "fixture")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    (tmp_path / "fixtures" / "stt").mkdir(parents=True)
    (tmp_path / "fixtures" / "stt" / ("a" * 64 + ".json")).write_text(json.dumps({"text": "6 log", "language": "hi-IN"}))
    res = stt.transcribe(b"RIFF", 1.0, "a" * 64)
    assert res.provider == "fixture" and res.value.text == "6 log"


def test_calls_stop_at_80_percent_of_a_free_cap(live, owner_db, monkeypatch):
    monkeypatch.setattr(httpx, "post", Captured(body={"choices": [{"message": {"content": "{}"}}]}))
    with owner_db.begin() as c:   # 799 of 1,000 daily calls already used: the 800th is the last allowed
        c.execute(text("INSERT INTO provider_usage (provider, window_kind, window_start, calls)"
                       " VALUES ('groq_gpt_oss_120b', 'day', date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC', 799)"))
    usage.check("groq_gpt_oss_120b")
    llm.groq("s", "u", {"type": "object"}, 10)
    with pytest.raises(ProviderUnavailable, match="80% of the free cap calls_per_day=1000"):
        usage.check("groq_gpt_oss_120b")


def test_run_chain_reports_every_attempt():
    def call(name):
        if name == "a":
            raise ProviderUnavailable("no key")
        return "value", "m"
    res = run_chain(["a", "b"], call)
    assert res.provider == "b" and res.attempts[0] == {"provider": "a", "outcome": "skipped: no key"}


def test_a_compose_comment_read_as_a_value_is_not_a_key(monkeypatch):
    from app.providers.base import api_key
    monkeypatch.setenv("PROVIDER_MODE", "auto")
    monkeypatch.setenv("GROQ_API_KEY", "# STT fallback + LLM primary")
    assert api_key("groq_gpt_oss_120b") is None
    monkeypatch.setenv("GROQ_API_KEY", "   ")
    assert api_key("groq_gpt_oss_120b") is None


def test_a_background_job_leaves_a_token_reserve_for_live_reports(seeded, app_db):
    """PRD F-C5: an import's model calls stop earlier than a live report's, keeping tokens per minute free."""
    from datetime import UTC, datetime
    now = usage._windows(datetime.now(UTC))
    with app_db.begin() as c:
        c.execute(text("INSERT INTO provider_usage (provider, window_kind, window_start, calls, tokens, audio_seconds)"
                       " VALUES ('groq_gpt_oss_120b', 'minute', :m, 1, 3000, 0)"), {"m": now["minute"]})
    usage.check("groq_gpt_oss_120b", tokens=1000)                   # a live report: 4000 ≤ 0.8 × 8000
    token = usage.RESERVE_TOKENS_PER_MIN.set(3000)
    try:
        with pytest.raises(ProviderUnavailable, match="keeping 3000 tokens/min for live reports"):
            usage.check("groq_gpt_oss_120b", tokens=1000)           # an import: 4000 > 6400 − 3000
    finally:
        usage.RESERVE_TOKENS_PER_MIN.reset(token)
