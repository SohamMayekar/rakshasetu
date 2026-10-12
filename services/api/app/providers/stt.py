"""Speech to text (PRD §8.4): Sarvam Saaras (primary) → Groq whisper-large-v3 (fallback).

Input is the server-transcoded 16 kHz mono WAV (≤ 30 s). In fixture mode the transcript comes from
`data/fixtures/stt/<sha256 of the original clip>.json`, a transcript recorded earlier (or written by the
team for a clip they recorded); the receipt then says `fixture`, never a provider name.
"""

import json
from dataclasses import dataclass

import httpx

from app.config import get_config
from app.providers import usage
from app.providers.base import ChainResult, ProviderFailed, ProviderUnavailable, api_key, mode, run_chain
from app.settings import get_settings

TIMEOUT = httpx.Timeout(20.0, connect=5.0)


@dataclass
class Transcript:
    text: str
    language: str | None          # BCP-47 like hi-IN when the provider says
    language_probability: float | None = None


def _model(name: str) -> str:
    return get_config().providers.get("models", {}).get(name, name)


def sarvam(wav: bytes, seconds: float) -> tuple[Transcript, str]:
    key = api_key("sarvam_saaras")
    if not key:
        raise ProviderUnavailable("no SARVAM_API_KEY")
    usage.check("sarvam_saaras", audio_seconds=seconds)
    model = _model("sarvam_saaras")
    try:
        r = httpx.post("https://api.sarvam.ai/speech-to-text", headers={"api-subscription-key": key},
                       data={"model": model, "mode": "transcribe", "language_code": "unknown"},
                       files={"file": ("clip.wav", wav, "audio/wav")}, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise ProviderFailed(f"network: {e}") from e
    usage.record("sarvam_saaras", audio_seconds=seconds)
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    return Transcript(body.get("transcript", ""), body.get("language_code"), body.get("language_probability")), model


def groq_whisper(wav: bytes, seconds: float) -> tuple[Transcript, str]:
    key = api_key("groq_whisper_large_v3")
    if not key:
        raise ProviderUnavailable("no GROQ_API_KEY")
    usage.check("groq_whisper_large_v3")
    model = _model("groq_whisper_large_v3")
    try:
        r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions",
                       headers={"Authorization": f"Bearer {key}"},
                       data={"model": model, "response_format": "verbose_json", "temperature": "0"},
                       files={"file": ("clip.wav", wav, "audio/wav")}, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise ProviderFailed(f"network: {e}") from e
    usage.record("groq_whisper_large_v3")
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    return Transcript(body.get("text", "").strip(), body.get("language")), model


def fixture(original_sha256: str) -> tuple[Transcript, str]:
    path = get_settings().data_dir / "fixtures" / "stt" / f"{original_sha256}.json"
    if not path.exists():
        raise ProviderUnavailable("no recorded transcript for this clip")
    f = json.loads(path.read_text())
    return Transcript(f["text"], f.get("language")), f.get("source", "fixture")


ADAPTERS = {"sarvam_saaras": sarvam, "groq_whisper_large_v3": groq_whisper}


def transcribe(wav: bytes, seconds: float, original_sha256: str) -> ChainResult:
    """Primary → fallback. In fixture mode only recorded transcripts are used. Raises AllProvidersFailed."""
    if mode() == "fixture":
        return run_chain(["fixture"], lambda _n: fixture(original_sha256))
    names = list(get_config().providers["stt"])
    # A recorded transcript for this exact clip (e.g. the demo's "play recorded clip") is used only
    # when no live provider answers, and the receipt says so.
    return run_chain([*names, "fixture"],
                     lambda n: fixture(original_sha256) if n == "fixture" else ADAPTERS[n](wav, seconds))
