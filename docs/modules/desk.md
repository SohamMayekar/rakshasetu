# desk · queue, map, drawer, live

- **Simplified (m67):** the desk shows three things: the **three promises** as one plain sentence each ("Nobody lost: 343 reports → 252 families" · "No family counted twice: 91 repeats merged" · "Nobody forgotten: every urgent family has a team"; a broken one turns ink and says what broke), **Needs you now** (each row: place · people, then the priority word, case number and waiting time, and one button in plain words), and the **map**. The sums behind each promise and the filters are under **Show details**; New report and Add a sheet sit quietly in the list's header; an alert is one line and one "Open BR-199" button with the radio buttons under More.

- **What it does:** `/desk/<incident>` (local listener) — the call-taker's and officer's screen. Left: the case column (m34 makes it "Needs you now"). Centre: the map. Right: the case drawer, titled with the PS's words (Assignment · Facts · Timeline & evidence · Audit). `/login` is the demo's "sign in as…" picker (DEMO_MODE + local only; elsewhere it asks for a password).
- **Live:** the page reads `/v1/cases?incident=` and the response's `X-Event-Seq` header (the event cursor, read *before* the list), then opens `WS /v1/ws?since=<seq>`. Events are gathered into **1-second frames**; the cases they name are re-read with `/v1/cases?ids=…` (scoped in SQL), so a case that leaves the user's scope simply disappears. On a dropped socket the header says "Live updates paused since 14:05" and it reconnects from the last seq it saw, so nothing is lost.
- **The map:** MapLibre GL JS + OpenFreeMap Positron (free, no key; attribution "© OpenStreetMap contributors" always shown). Every case is a **circle of its honest radius** — never a bare pin — dashed when Low, its stroke in the priority's hue. If the tile server can't be reached (venue network), the map falls back to **plain paper** after 6 s and says "Map tiles unavailable: circles only", so the projector never shows a blank map.
- **In a surge** (more than 300 placed cases) the map clusters below zoom 11, keeps lone cases as true-size circles, and follows the cases every 5 s; the queue reads one at a time and renders 80 rows at a time (D14, `docs/modules/surge.md`).
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

## The call-taker's form (m37)

- **New report** (top of the left column, `report.submit`): type the call or paste a forwarded message. As they type, `POST /v1/ingest/desk/preview` (rules only, nothing stored) shows what the keywords read as chips — "6 people · on the roof · water inside · medicine · elderly · दुर्गा मंदिर temple · bridge · Thave" — labelled **Rule · keywords, as you type**, and prompts "Ask: how many people · where?" when those are missing.
- **Save** writes the report through `POST /v1/ingest/desk` (the same `intake.accept()` as every channel). The form's own id is the idempotency key, so a double click can't make two reports. The column then says "Report saved · reading it…" and, when the pipeline's `case.created` arrives, "→ BR-199, a new case" or "→ folded into BR-214 (the same household)", and opens that case.
- **A forward** is marked as one ("the sender may not be there"); its relation is `forwarder`.
- **Measured (one run each, keyword path, local stack):** the demo's report typed (Hindi at the time, m38) → its case open on the desk **2.2 s** after Save; the son's pasted forward → "Likely same household as BR-199 (strong): same village (Thawe) · circles overlap (0 m apart) · same landmarks (Thawe durga mata mandir, bridge) · same headcount (6)" in **1.8 s**.
- **Demo reset while a desk is open:** the hub notices the log's new genesis and sends `{"type": "reset"}`; the desk reloads. (Found in m37: before this, live updates silently stopped after a reseed until the API restarted.)

## Ownership on the desk (m43)

- **Assignment section:** with no owner, the **three suggested teams with their reasons** ("2.6 km straight-line · position 6 min old · boat, medical · 0 active") and **Assign** on each (the first is primary); other teams and the greyed ones (with why) fold below. With an owner: "Assigned to **Fire & Rescue Boat 5** · acknowledged · ETA 30 min · by R. Das", the **check-in ring** counting down ("check-in due 0:38", "radio check due" for radio-only teams, "demo clock ×60" when it applies), "Contact overdue 0:06" in ink once late, and **Heard on radio** (channel + optional ETA), **Acknowledged on radio**, **Release** (reason), and **Reassign** when overdue (the suggestions, excluding the silent team; it then owes a stand-down).
- **Escalations** sit above the queue for officers: "Fire & Rescue Boat 5 overdue · 1 case · no contact since 03:23. Radio them, then Extend or Reassign." with the case ids, **I'm on it**, and **Heard · ETA 15 / 30 / 60** on a chosen channel (giving an ETA also counts as the team's acknowledgement).
- **One click from the queue:** an officer's "Assign → Fire & Rescue Boat 5 · 2.6 km · boat, medical" assigns that team at once.
- **The check outlives the status:** an owned P1 that nobody checked stays in the queue as "unchecked P1" until a person checks it.
- **Measured (one run, live stack, Chromium):** Assign → owner and ring on screen **0.58 s**; a demo-clock P1 nobody acknowledged → its escalation on screen **10.4 s** after Assign (5 s to acknowledge + ≤ 5 s tick + the 1 s frame); **Heard · ETA 30** → escalation gone, the case "handled" in place, ring reset.
