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

## The drawer (m35)

- **Header:** priority, case id, status, the summary and its *because*; **Check** (call-taker, officer) and **Move pin** (click the map; a person's pin is a 50 m circle, saved with a logged reason).
- **Facts with receipts:** each value shows ● checked / ○ not yet / amber ○ (quote check failed), its method chip (AI · Rule · Human · Partner; "sheet column" when a spreadsheet column gave it), and **hovering it lights up its quote** in the report below. People can be corrected inline with a reason (`If-Match: version`; a stale edit gets the 409 naming who changed it). Contact is masked.
- **Timeline & evidence** (`GET /v1/cases/{id}/timeline`): every event of this case and of the cases folded into it, in order, as **plain lines from templates** ("Merged into BR-209: same phone · same village (Mirganj) · circles overlap…", "Checked by Priya Kumari"). Each report appears as a card: channel tag, time, relation, masked phone, its words in the caller's own script, its pipeline receipt, and its evidence inline — the audio player, or the spreadsheet row (file name, row number, the cells, a link to the file). Every evidence file is **re-hashed when the drawer opens**: "sha256 3f2a… ✓ matches the audit log" (the file still hashes to its name, and that hash is the one the chain recorded), or "✗ does not match".
- **Evidence files** (`GET /v1/evidence/{id}/file`) are served only when the evidence's case is in the caller's scope (in the SQL); a Muzaffarpur officer gets 404 for a Gopalganj file (tested).
- **Audit:** a link to the case's raw events (the Audit screen arrives in m48).

## Merge decisions (m36)

- **Likely duplicates** appear at the top of *Timeline & evidence*: "Likely same household as BR-180 (strong)", the rules' reasons as the *because* ("same phone · same village (Nawadah) · same headcount (5) · 4 h apart"), and the two cases side by side. **Merge** folds the newer case into the older one (reason optional); **Not the same household** blocks the pair for good. A person decides; the reasons come from the scoring rules, never a model.
- **Kept apart:** pairs the rules refused (different given names) fold into one line, "Kept apart from 3 cases: the names differ", because in a busy village most neighbours look alike on village + landmark alone. Opened, each shows the names that kept it apart ("Rajesh ≠ Ramesh") and **Merge anyway**, which needs a reason.
- **Undo:** every merge line in the timeline has **Undo merge** (reason required); undone merges say so and can't be undone twice. **Same household as another case…** merges any two visible cases by hand, with a reason.
- **After a merge** the drawer moves to the kept case.
