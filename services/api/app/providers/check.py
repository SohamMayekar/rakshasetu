"""`make provider-check`: one tiny call to each provider whose key is set (synthetic input only)."""

import io
import math
import struct
import wave

from app.providers import llm, stt
from app.providers.base import ProviderFailed, ProviderUnavailable


def _tone_wav(seconds=1.0, rate=16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * math.sin(2 * math.pi * 440 * i / rate)))
                               for i in range(int(seconds * rate))))
    return buf.getvalue()


def main() -> None:
    wav = _tone_wav()
    for name, fn in stt.ADAPTERS.items():
        try:
            t, model = fn(wav, 1.0)
            print(f"OK       {name} ({model}): transcript {t.text!r}")
        except ProviderUnavailable as e:
            print(f"BLOCKED  {name}: {e}")
        except ProviderFailed as e:
            print(f"FAILED   {name}: {e}")
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"], "additionalProperties": False}
    for name, fn in llm.ADAPTERS.items():
        try:
            out, model = fn("Reply with JSON.", 'Return {"ok": true}.', schema, 50)
            print(f"OK       {name} ({model}): {out}")
        except ProviderUnavailable as e:
            print(f"BLOCKED  {name}: {e}")
        except ProviderFailed as e:
            print(f"FAILED   {name}: {e}")


if __name__ == "__main__":
    main()
