# demo · the controls behind the 5-minute run (PRD F-C12, §16)

- **The page (m71):** `/demo` is a numbered walk through the six scenes. The current scene is in big type with one line of what to do, a big **Next scene**, the scene's own button where there is one (play the son's clip, a recording; open History) and "Reset to the start of this scene". "Say it on stage" holds the honesty lines, one short line each; Phones shows the two QR codes (with `PUBLIC_URL` set). Reset to any scene, AI reading on/off, the rush of reports, the partner moment and the recorded clips are under **More controls**, next to Show it under load and Show a partner system. The duty officer sees the same script read-only; the controls stay with the Demo admin.

- **Where:** `/demo` (linked from Incidents for the System admin) and `POST /v1/demo/*`. **Local listener only**, **DEMO_MODE only**, refused if Cloudflare's `CF-Connecting-IP` is present, and **System admin only** (tested: the public listener gets 403, every other role 403). Every control is an audit event.
- **Two windows, two sign-ins:** the desk on `http://localhost` as the EOC Duty Officer, the demo page on `http://127.0.0.1/demo` as System admin. They are different addresses to the browser, so each keeps its own sign-in.
- **Reset to a scene** (`make demo-reset SCENE=<id>` or the page): seeds the database with times relative to now (`make demo-reset` alone = the start, **3.4–3.7 s**), then **replays every earlier scene through the real API as the person who does it on stage**, from `data/scenarios/BR/demo.yaml`:

  | Scene (time in the run) | Starts with |
  |---|---|
  | `son` 0:00 The son in Mumbai | the seed only |
  | `merge` 0:50 Never doubled | the son's case: the recorded clip played through the voice pipeline from the son's (synthetic) phone |
  | `sheet` 1:15 The volunteer sheet | + the neighbour's forward (it names Ramesh Das) merged by the officer, the case checked, "Rajesh Das, 5 log…" refused |
  | `stale` 1:45 Never stale | + the 300-row sheet imported |
  | `rescue` 2:30 The rescue | + SDRF Boat 2 assigned, "Acknowledged on radio · VHF · ETA 15", overdue, escalated, reassigned to Fire & Rescue Boat 5 |
  | `receipts` 3:05 The receipts | + trip 1 (4 taken, someone still there), trip 2 (2 taken, nobody left), rescued 6 of 6, the family's yes |

  - **Two things a reset does outside the API, both on the record.** It runs the queued jobs itself so the next step sees the case. For "Never stale" it moves Boat 2's deadline to now instead of waiting out the ×60 demo clock: an event, "Demo reset: SDRF Boat 2's ETA has passed (moved to now instead of waiting)".
  - **A reset point waits for the presenter.** A live assignment the replay made (Boat 5, offered at the end of "Never stale") goes onto the real clock, with what was left of its window scaled back up. It is an event, and the timeline says so. Without this it would be "Contact overdue" seconds after the reset. Anything the presenter does after the reset is live, on the ×60 demo clock.
  - Every open screen reloads itself after a reset (the event log starts a new chain, whose genesis event records the scene). Existing sign-ins survive (ids are reseeded identically).
  - An unknown scene is refused before anything is wiped (tested). A failed step stops the reset and names the step.
- **Language model off/on** (F-C14): the page says plainly when no language-model key is set ("the keyword rules read every report either way") and which STT providers have keys. It shows names only, never a key.
- **Surge:** `POST /v1/demo/surge` runs `app/surge.py` in the background (50/s for 60 s by default; one at a time; a reset is refused while it runs). Watch `/surge`.
- **Play a recorded clip** (§16.4 fallback): sends a clip from `data/scenarios/BR/clips/` through **the reporter page's own voice path** (`_register_voice`: transcode, caps, evidence, the `live_voice` lane), from the son's phone. The shipped clip is **a synthetic espeak-ng voice**, labelled so in the file name, the page and the timeline ("Played by the demo control from clips/son-line.synthetic.ogg (a synthetic voice), through the same voice pipeline"). Without an STT key, its transcript is the text given to the synthesizer, and the receipt says **Fixture · recorded transcript (not a live STT call)**. The humans should record real clips (STATUS).
- **QR codes** (`GET /v1/demo/qr?target=reporter|son`, SVG by segno, BSD, pure Python): the reporter page, and **the son's status page as his phone**. Only `PUBLIC_URL` pages, because a phone can't reach localhost.
  - After a reset the son's report comes from a synthetic device (`demo-son-phone-0001`), and only the reporting device is asked the family's question. The QR link carries that device id in the URL fragment. The status page takes it **only when the server says DEMO_MODE** (`"demo": true` on the public status), then removes it from the address bar. Outside DEMO_MODE the fragment is ignored. A stranger's phone sees only the steps (checked in Chromium).
