"""The language model (PRD §8.4): Groq gpt-oss-120b (primary) → Gemini Flash (fallback) → the keyword path.

It is asked for ONE thing: the closed extraction JSON (contracts/extraction.schema.json). The caller
validates it with Pydantic and checks every quote; nothing here decides anything.
"""

import json

import httpx

from app.config import get_config
from app.providers import usage
from app.providers.base import ChainResult, ProviderFailed, ProviderUnavailable, api_key, mode, run_chain


def _model(name: str) -> str:
    return get_config().providers.get("models", {}).get(name, name)


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(float(get_config().llm.get("timeout_s", 8)), connect=3.0)


def provider_schema(schema: dict) -> dict:
    """Strict JSON-schema decoding wants every key required and no extra keys, and dislikes length
    constraints; Pydantic re-checks the lengths afterwards."""
    drop = {"minLength", "maxLength", "maxItems", "minimum", "maximum", "pattern", "$id", "$schema", "title",
            "description"}
    if isinstance(schema, dict):
        return {k: provider_schema(v) for k, v in schema.items() if k not in drop}
    if isinstance(schema, list):
        return [provider_schema(v) for v in schema]
    return schema


def groq(system: str, user: str, schema: dict, est_tokens: int) -> tuple[dict, str]:
    key = api_key("groq_gpt_oss_120b")
    if not key:
        raise ProviderUnavailable("no GROQ_API_KEY")
    usage.check("groq_gpt_oss_120b", tokens=est_tokens)
    model = _model("groq_gpt_oss_120b")
    body = {"model": model, "temperature": 0, "reasoning_effort": get_config().llm.get("reasoning_effort", "low"),
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "extraction", "strict": True, "schema": provider_schema(schema)}}}
    try:
        r = httpx.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {key}"},
                       json=body, timeout=_timeout())
    except httpx.TimeoutException as e:
        raise ProviderFailed("timeout") from e
    except httpx.HTTPError as e:
        raise ProviderFailed(f"network: {e}") from e
    tokens = (r.json().get("usage") or {}).get("total_tokens", est_tokens) if r.status_code == 200 else est_tokens
    usage.record("groq_gpt_oss_120b", tokens=tokens)
    if r.status_code == 429:
        raise ProviderFailed(f"rate limited (retry-after {r.headers.get('retry-after')})")
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:200]}")
    try:
        return json.loads(r.json()["choices"][0]["message"]["content"]), model
    except (KeyError, ValueError) as e:
        raise ProviderFailed(f"unreadable output: {e}") from e


def gemini(system: str, user: str, schema: dict, est_tokens: int) -> tuple[dict, str]:
    key = api_key("gemini_flash")
    if not key:
        raise ProviderUnavailable("no GEMINI_API_KEY")
    usage.check("gemini_flash", tokens=est_tokens)
    model = _model("gemini_flash")
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json",
                                 "responseJsonSchema": provider_schema(schema)}}
    try:
        r = httpx.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                       headers={"x-goog-api-key": key}, json=body, timeout=_timeout())
    except httpx.TimeoutException as e:
        raise ProviderFailed("timeout") from e
    except httpx.HTTPError as e:
        raise ProviderFailed(f"network: {e}") from e
    usage.record("gemini_flash", tokens=est_tokens)
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:200]}")
    try:
        return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"]), model
    except (KeyError, IndexError, ValueError) as e:
        raise ProviderFailed(f"unreadable output: {e}") from e


ADAPTERS = {"groq_gpt_oss_120b": groq, "gemini_flash": gemini}


def extract_json(system: str, user: str, schema: dict, est_tokens: int = 1500) -> ChainResult:
    """Primary → fallback. Raises AllProvidersFailed; the caller then uses the keyword path."""
    if mode() == "fixture":
        raise ProviderUnavailable("fixture mode: the language model is only read from the extraction cache")
    names = list(get_config().providers["llm"])
    return run_chain(names, lambda n: ADAPTERS[n](system, user, schema, est_tokens))
