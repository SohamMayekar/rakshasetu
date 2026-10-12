# reporter · the voice PWA at /r (public listener)

- **What it does:** one big button. Tap once and speak; recording stops after ~2 s of silence or at 30 s. The clip goes to `POST /v1/public/voice-turns` with a random **device id** (localStorage) and a per-clip session id (its idempotency key). The server stores the original content-addressed, transcodes it with ffmpeg to 16 kHz mono WAV, refuses empty or too-short clips ("Didn't hear anything, try again", no case), and runs the same pipeline. The phone shows the case id only after the server confirms it.
- **Key tables / files:** `reports` (channel `voice`, `device_hash`), `evidence` (type `audio`, sha256), `app/modules/public/router.py`, `apps/web/app/r/page.tsx`, `apps/web/lib/recorder.ts`.
- **The tricky rule:** the case never depends on AI. If every speech-to-text provider fails, the clip still becomes an **"audio only: listen"** case with an id. The reply is the one fixed sentence (Hindi + English text, plus the team's recorded clip once it exists), never generated text, never a promised time.
- **Limits:** 5 clips a minute per device, 20 a minute overall (per-IP limits don't work behind the tunnel); 2 MB per clip.
- **How to show it:** open `/r` on a phone through the tunnel, speak the demo line, watch the case id appear; the desk shows the case seconds later.
