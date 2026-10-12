# desk · queue, map, drawer, live

- **What it does:** `/desk/<incident>` (local listener) — the call-taker's and officer's screen. Left: the case column (m34 makes it "Needs you now"). Centre: the map. Right: the case drawer, titled with the PS's words (Assignment · Facts · Timeline & evidence · Audit). `/login` is the demo's "sign in as…" picker (DEMO_MODE + local only; elsewhere it asks for a password).
- **Live:** the page reads `/v1/cases?incident=` and the response's `X-Event-Seq` header (the event cursor, read *before* the list), then opens `WS /v1/ws?since=<seq>`. Events are gathered into **1-second frames**; the cases they name are re-read with `/v1/cases?ids=…` (scoped in SQL), so a case that leaves the user's scope simply disappears. On a dropped socket the header says "Live updates paused since 14:05" and it reconnects from the last seq it saw, so nothing is lost.
- **The map:** MapLibre GL JS + OpenFreeMap Positron (free, no key; attribution "© OpenStreetMap contributors" always shown). Every case is a **circle of its honest radius** — never a bare pin — dashed when Low, its stroke in the priority's hue. If the tile server can't be reached (venue network), the map falls back to **plain paper** after 6 s and says "Map tiles unavailable: circles only", so the projector never shows a blank map.
- **Deep link:** `/desk/BR?case=BR-214` opens a case's drawer (used by the Audit screen and screenshots).
- **Phone width:** the list fills the screen and the drawer opens full screen; the map is for the projector.
- **How to show it:** `make up && make seed`, open `http://localhost/login`, pick Priya Kumari (call-taker). Measured: a report typed through the API appeared on an open desk **0.84 s** after the POST (one run, local stack, keyword path).

## Needs you now (m34)

- **What it does:** `GET /v1/queue?incident=` (`app/modules/queue/`) returns only the cases that need a person, already ordered, each with **one chip**, a **two-line summary**, and **one suggested action for the viewer's role**. Healthy cases (a live owner whose check-in isn't due) leave the list and are counted under "On it · rescued, closing · closed".
- **Attention:** no live owner · contact overdue · disputed · reopened · needs location · possible duplicate · an unchecked case (the PRD's "unchecked P1" is the chip; any unchecked case still needs its check).
- **One ordering rule:** priority → broken promises before new work (contact overdue, disputed, reopened, a P1 with no owner after 5 min) → the P1 order (`p1_rank`) → longest wait.
- **One chip, ranked:** contact overdue / disputed / reopened / "no owner 12 min" > needs location > unchecked P1 > possible duplicate. ("No owner" isn't in the PRD's chip list; it's the P1-unowned broken promise, so it ranks with the other broken promises.)
- **The action:** Heard on radio (officer, overdue) · Fix pin · Review match → BR-xxx · **Assign a team** (officer, any unowned P1, even unchecked: nobody on a roof waits for paperwork) · Check (call-taker) · Open. "Check" runs straight from the row; the others open the drawer at the right section.
- **Nothing moves under the cursor:** rows already on screen keep their place and update in place; new rows wait behind "▲ 3 new: show"; rows that no longer need anyone fade where they are ("handled") until the person clicks the pill. The map colours the queue's cases and greys the rest.
- **Empty state:** "Nothing needs you. 124 households have a live owner."
