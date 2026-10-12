"""Voice clips (PRD F-L2, rule R15): ffmpeg transcodes ANY browser format to 16 kHz mono WAV, capped at
30 s, with a 10 s timeout. A clip that's too short or silent is refused before anything is stored as a report."""

import array
import io
import math
import subprocess
import wave


class BadAudio(Exception):
    pass


def to_wav16k(src_path: str, max_seconds: int = 30, timeout_s: int = 10) -> bytes:
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", src_path, "-t", str(max_seconds),
             "-ac", "1", "-ar", "16000", "-f", "wav", "-acodec", "pcm_s16le", "pipe:1"],
            capture_output=True, timeout=timeout_s, check=False)
    except subprocess.TimeoutExpired as e:
        raise BadAudio("ffmpeg timed out") from e
    if out.returncode != 0 or len(out.stdout) < 100:
        raise BadAudio(f"not playable audio ({out.stderr.decode(errors='replace')[:200]})")
    return out.stdout


def measure(wav_bytes: bytes) -> tuple[float, float]:
    """(seconds, RMS loudness 0..1) of a 16-bit mono WAV."""
    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())   # ffmpeg writing to a pipe can't fix the header's length,
    samples = array.array("h", frames[: len(frames) // 2 * 2])  # so the duration comes from the data read
    if not samples:
        return 0.0, 0.0
    step = max(1, len(samples) // 20000)
    sampled = samples[::step]
    rms = math.sqrt(sum(s * s for s in sampled) / len(sampled))
    return len(samples) / float(rate), rms / 32768.0
