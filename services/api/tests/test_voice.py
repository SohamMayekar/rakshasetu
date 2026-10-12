"""F-L2: the reporter PWA's backend. Clip → ffmpeg 16 kHz WAV → STT (fixture mode here) → the same pipeline.
An empty clip gets "Didn't hear anything" and no case; total STT failure still gives an "audio only" case."""

import hashlib
import io
import json
import math
import struct
import uuid
import wave

import pytest

from app.core.jobs import drain
from app.pipeline import register_handlers
from tests.conftest import needs_db, one

pytestmark = needs_db
DEMO = "Thawe gaon mein, Durga mandir ke peeche, pul ke paas, chhat pe 6 log fase hain. Paani ghus gaya hai, ek buzurg hain, dawai chahiye."


def wav(seconds=2.0, amplitude=8000, freq=440, rate=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(amplitude * math.sin(2 * math.pi * freq * i / rate)))
                               for i in range(int(seconds * rate))))
    return buf.getvalue()


@pytest.fixture
def voice(seeded, public_client, monkeypatch, tmp_path):
    register_handlers()
    monkeypatch.setenv("VOICE_WAIT_SECONDS", "0")
    monkeypatch.setenv("FILES_DIR", str(tmp_path / "files"))
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data" / "fixtures" / "stt").mkdir(parents=True)

    def send(clip: bytes, device="device-0001-abcd", transcript: str | None = None, session=None):
        if transcript is not None:   # a recorded transcript for exactly this clip
            sha = hashlib.sha256(clip).hexdigest()
            (tmp_path / "data" / "fixtures" / "stt" / f"{sha}.json").write_text(json.dumps({"text": transcript, "language": "hi-IN"}))
        return public_client.post("/v1/public/voice-turns", files={"audio": ("clip.webm", clip, "audio/webm")},
                                  data={"device_id": device, "session_id": session or str(uuid.uuid4()), "incident": "BR"})
    return send


def test_a_clip_becomes_a_case_with_its_audio_as_evidence(voice, public_client, app_db):
    clip = wav()
    r = voice(clip, transcript=DEMO)
    assert r.status_code == 200 and r.json()["reply"]["en"].startswith("Your report is registered")
    rid = r.json()["report_id"]
    drain(app_db)
    st = public_client.get(f"/v1/public/turns/{rid}", params={"device_id": "device-0001-abcd"}).json()
    assert st["status"] == "registered" and st["public_id"].startswith("BR-")
    case_id = one(app_db, "SELECT case_id FROM reports WHERE id = :r", r=rid)
    assert one(app_db, "SELECT people_count FROM cases WHERE id = :c", c=case_id) == 6
    receipt = one(app_db, "SELECT receipt FROM reports WHERE id = :r", r=rid)
    assert receipt[0]["by"] == "Fixture" and "not a live STT call" in receipt[0]["detail"]
    ev_sha = one(app_db, "SELECT sha256 FROM evidence WHERE case_id = :c AND type = 'audio'", c=case_id)
    assert ev_sha == hashlib.sha256(clip).hexdigest()
    assert one(app_db, "SELECT count(*) FROM events WHERE action = 'evidence.added' AND body LIKE :s", s=f"%{ev_sha}%") == 1


def test_stt_failing_completely_still_gives_an_audio_only_case(voice, app_db):
    r = voice(wav(seconds=2.5, freq=300))          # no recorded transcript, no keys: every STT provider fails
    drain(app_db)
    case_id = one(app_db, "SELECT case_id FROM reports WHERE id = :r", r=r.json()["report_id"])
    assert one(app_db, "SELECT summary FROM cases WHERE id = :c", c=case_id) == "audio only: listen"
    assert "audio_only" in one(app_db, "SELECT flags FROM cases WHERE id = :c", c=case_id)


@pytest.mark.parametrize("label,clip,code", [
    ("silence", wav(amplitude=0), "empty_clip"),
    ("too short", wav(seconds=0.4), "empty_clip"),
    ("not audio", b"this is not audio at all" * 50, "bad_audio"),
], ids=["silence", "too-short", "not-audio"])
def test_empty_or_broken_clips_get_try_again_and_no_case(voice, app_db, label, clip, code):
    before = one(app_db, "SELECT count(*) FROM reports")
    r = voice(clip)
    assert r.status_code == 422 and r.json()["detail"]["code"] == code, label
    assert one(app_db, "SELECT count(*) FROM reports") == before


def test_voice_caps_per_device(voice):
    clip = wav(seconds=1.5)
    for i in range(5):
        assert voice(clip, device="device-caps-1").status_code == 200, i
    assert voice(clip, device="device-caps-1").status_code == 429
    assert voice(clip, device="device-caps-2").status_code == 200       # another phone is unaffected


def test_a_retried_upload_is_one_report(voice):
    clip = wav()
    a = voice(clip, session="same-session-0001").json()["report_id"]
    b = voice(clip, session="same-session-0001").json()["report_id"]
    assert a == b


def test_only_the_sending_device_can_poll(voice, public_client):
    rid = voice(wav()).json()["report_id"]
    assert public_client.get(f"/v1/public/turns/{rid}", params={"device_id": "someone-else-00"}).status_code == 404


def test_typed_text_from_the_pwa(seeded, public_client, app_db, monkeypatch):
    register_handlers()
    monkeypatch.setenv("VOICE_WAIT_SECONDS", "0")
    r = public_client.post("/v1/public/text-turns", json={"device_id": "device-typed-01", "session_id": str(uuid.uuid4()),
                                                         "incident": "BR", "text": DEMO})
    drain(app_db)
    assert one(app_db, "SELECT c.people_count FROM reports r JOIN cases c ON c.id = r.case_id WHERE r.id = :r",
               r=r.json()["report_id"]) == 6
