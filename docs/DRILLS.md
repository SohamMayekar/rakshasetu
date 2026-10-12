# Failure drills (PRD §16.4, T2, F-C10)

`make drills` (`apps/web/e2e/drills.mjs`) breaks something on purpose on the **running stack**, then measures how
the system and the screens recover. Numbers below are from one run on 12 Oct 2026 (local stack, same VM); **all
14 checks passed**.

| Drill | What we did | What happened (measured) |
|---|---|---|
| **D1 · the worker crashes mid-surge** (T2, live) | `kill -9` on the worker process 8 s into a 30/s surge | It came back **by itself in 0.5 s** (`restart: unless-stopped`, added in m56: before, a crashed service stayed down). The backlog drained **61 s** after the crash, because the jobs the dead worker held are reclaimed once their lock is 60 s old. **All 600 surge reports in exactly one case** (0 without, 0 made twice); integrity **0**, 3,305 events verified |
| **D2 · the desk is cut off for 30 s** (F-C10 "done when") | stopped the proxy between the projector and the API for 30 s; a partner report arrived inside the server meanwhile | The header said **"Live updates paused since …"** within 5 s. When the link came back the desk went live again and **the new case was on it 3.2 s later, without a reload** (it resubscribes from its last event; nothing lost) |
| **D3 · the API restarts** | `docker restart` of the API under an open desk | API healthy in **4.3 s**; the desk said "paused", then **reconnected by itself**; a report made afterwards reached it without a reload |
| **D4 · the tile server is unreachable** (venue network) | every map tile request blocked | Plain paper with the circles, saying **"Map tiles unavailable: circles only"**, within a second |
| **D5 · the language model is off** (F-C14) | the demo switch | A typed report became a case **in 0.3 s**, read by the rules (≤ 5 s) |
| **D6 · an insider edits history** (the Q&A tamper demo) | `make tamper SEQ=12`: a superuser rewrites one past event's reason | Verify chain: **"broken at #12"** (the row no longer matches its hashed body). A reset (4.3 s) starts a fresh chain: ✓ 223 events |
| **D7 · a scene fails on stage** | reset to "The rescue" | **22.7 s**; BR-199 offered to Fire & Rescue Boat 5 on the real clock, waiting for the presenter |

**What the drills don't cover:** the public tunnel itself going down (the projector runs on localhost, so the desk
keeps working; the phones would wait), a real phone losing mobile data (needs the humans), and the database
restarting (not drilled; the services reconnect on their next query, but it hasn't been measured).

**How D2 cuts the link:** Chromium's offline emulation leaves an already-open WebSocket connected, so the drill
stops the proxy instead. From the browser's side that is the same as the laptop losing the server.
