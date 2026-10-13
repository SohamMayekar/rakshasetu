"""Speech to text (PRD §8.4): Sarvam Saaras (primary) → Groq whisper-large-v3 (fallback).

Input is the server-transcoded 16 kHz mono WAV (≤ 30 s). In fixture mode the transcript comes from
`data/fixtures/stt/<sha256 of the original clip>.json`, a transcript recorded earlier (or written by the
team for a clip they recorded); the receipt then says `fixture`, never a provider name.
"""

import json
import re
import time
from dataclasses import dataclass

import httpx

from app.config import get_config
from app.providers import usage
from app.providers.base import ChainResult, ProviderFailed, ProviderUnavailable, api_key, mode, run_chain
from app.settings import get_settings

TIMEOUT = httpx.Timeout(20.0, connect=5.0)

# What a speech model "hears" in near-silence or room noise. These are not reports: they must never become a
# transcript (the clip still becomes an "audio only: listen" case, so nothing is lost).
_NOISE = {"thank you", "thanks", "thanks for watching", "thank you for watching", "you", "bye", "okay", "ok", "hmm", "mm",
          "uh", "um", "yeah", "subtitles by the amara.org community", "धन्यवाद", "शुक्रिया"}

# A short vocabulary hint helps a model spell Hindi/English flood words; it is never shown to anyone.
HINT = ("Flood rescue call in India, Hindi and English mixed. chhat, paani, bachche, buzurg, nav, boat, gaon, mandir, "
        "pul, ghar, madad, log phase hain.")


def clean(text: str | None) -> str:
    """Whitespace tidied; a transcript that is only noise, or only our own hint echoed back, becomes ''."""
    t = re.sub(r"\s+", " ", (text or "")).strip()
    bare = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE).strip().lower()
    if not bare or bare in _NOISE or not re.search(r"\w", bare):
        return ""
    if HINT.lower()[:40] in t.lower():
        return ""
    return t


def _post(url: str, **kw) -> httpx.Response:
    """One retry for a failure that is plainly transient (connection trouble, 429, 5xx); never for a slow read."""
    last: Exception | None = None
    for attempt in range(2):
        try:
            r = httpx.post(url, timeout=TIMEOUT, **kw)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
            last = e
        except httpx.HTTPError as e:
            raise ProviderFailed(f"network: {e}") from e
        else:
            if r.status_code not in (429, 500, 502, 503, 504) or attempt == 1:
                return r
            last = None
        time.sleep(0.6)
    raise ProviderFailed(f"network: {last}")


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
    r = _post("https://api.sarvam.ai/speech-to-text", headers={"api-subscription-key": key},
              data={"model": model, "mode": "transcribe", "language_code": "unknown"},
              files={"file": ("clip.wav", wav, "audio/wav")})
    usage.record("sarvam_saaras", audio_seconds=seconds)
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    text = clean(body.get("transcript"))
    if not text:
        raise ProviderFailed("empty transcript")   # let the next provider try the same clip
    return Transcript(text, body.get("language_code"), body.get("language_probability")), model


def groq_whisper(wav: bytes, seconds: float) -> tuple[Transcript, str]:
    key = api_key("groq_whisper_large_v3")
    if not key:
        raise ProviderUnavailable("no GROQ_API_KEY")
    usage.check("groq_whisper_large_v3")
    model = _model("groq_whisper_large_v3")
    r = _post("https://api.groq.com/openai/v1/audio/transcriptions", headers={"Authorization": f"Bearer {key}"},
              data={"model": model, "response_format": "verbose_json", "temperature": "0", "prompt": HINT},
              files={"file": ("clip.wav", wav, "audio/wav")})
    usage.record("groq_whisper_large_v3")
    if r.status_code != 200:
        raise ProviderFailed(f"HTTP {r.status_code}: {r.text[:200]}")
    body = r.json()
    text = clean(body.get("text"))
    if not text:
        raise ProviderFailed("empty transcript")
    return Transcript(text, body.get("language")), model


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
