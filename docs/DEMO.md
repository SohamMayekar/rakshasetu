# How to demo RakshaSetu to the judges

Four of us perform a real rescue in about four minutes. The judges only watch. Everything on screen is the real
app doing real work; only the people, phone numbers and the fast clock are demo values, and we say so once.

## The cast

| Who | Device | Signed in as | Opens |
|---|---|---|---|
| **Presenter** | none | none | Tells the story, one line per step (below) |
| **Duty officer** | the laptop, on the projector | Duty officer (R. Das) | `http://localhost` → the desk |
| **The son** | phone A | nobody: he is a member of the public | `<tunnel address>/r` |
| **Boat crew** | phone B | Rescue team (Boat 5): `boat5` / `rakshasetu` | `<tunnel address>/responder` |

No phones? Open the two phone pages in two narrow browser windows on a second laptop pointed at the same tunnel
address.

## Before going on stage (10 minutes earlier)

1. `make up` and `make seed` on the laptop. Then `make demo-reset SCENE=son`. Read the output: it must end without
   an error.
2. Start the tunnel: `cloudflared tunnel --url http://localhost:8080`. Write its `https://….trycloudflare.com`
   address in `.env` as `PUBLIC_URL`, then run `make up` again.
3. Open the desk on the projector and sign in as **Duty officer**. Zoom the browser to 110 % if the room is large.
4. Phone A opens `<tunnel address>/r` and leaves it on the microphone screen.
5. Phone B opens `<tunnel address>/responder` and signs in as `boat5` / `rakshasetu`. It shows "No cases".
6. Have the two texts below ready to paste (in a notes app on the laptop).

## The performance

Times are a guide. Each step: what someone does, what everyone sees, what the presenter says.

**1 · A family asks for help (0:00)**
- *The son* types on phone A (or speaks it, if a speech key is set):
  > My family is in Thawe village, behind the Durga temple, near the bridge. 6 people are stuck on the roof.
  > Water has come in, there is an elderly man, they need medicine.
  Then he taps **Send**. His phone says "We have your report."
- *The desk* shows a new row at the top within seconds: **Thawe · 6 people · Urgent**.
- *Presenter:* "A son in Mumbai asks for help for his family in Bihar. He doesn't need an app, a code or a login."

**2 · The officer understands it in one glance (0:30)**
- *Officer* clicks the row. The panel shows who, how many, where (a circle on the map, "within 150 m"), and why
  it's Urgent. Opening **Facts** and pointing at "6" lights up the son's own words.
- *Presenter:* "AI only turns speech into text and pulls out facts with the exact words. Rules set the priority;
  a person decides."

**3 · The same family, twice (0:50)**
- *Officer* clicks **New report**, pastes the neighbour's forward, ticks "This is a forwarded message", saves:
  > Ramesh Das's family is in Thawe village, behind the Durga temple, near the bridge. 6 people are stuck on the
  > roof, there is a lot of water.
- The new case says **Maybe the same family as BR-…** with the reasons. *Officer* clicks **Merge**.
- *Officer* clicks **New report** again, types `Rajesh Das, 5 people, Thawe village, near the temple, stuck on the
  roof`, phone `98765 70003`, saves. The panel shows it **kept apart: Rajesh ≠ Ramesh**.
- *Presenter:* "Same family: one case. A different family on the same street: never merged."

**4 · A volunteer's spreadsheet (1:15)**
- *Officer* clicks the sheet icon next to New report, chooses `data/scenarios/BR/sheet/volunteer_sheet.csv`,
  clicks **Confirm mapping and import**.
- In about 15 seconds: "300 rows → 188 new cases · 90 merged · 14 to check · 0 dropped".
- *Presenter:* "Three hundred rows from a volunteer's Excel. Nobody lost, nobody counted twice."

**5 · A team goes quiet (1:45)**
- *Officer* opens the son's case, opens **Assignment**, clicks **Send** next to **SDRF Boat 2** (a radio-only
  boat), then **Heard on radio** → **15 min** → **Log contact**.
- About 25 seconds later (the clock runs 60× faster) the case turns black: **contact overdue**, and an alert
  appears above the list. The case stays with Boat 2.
- *Officer* clicks **Send another team** → **Send this team** on **Fire & Rescue Boat 5**.
- *Presenter:* "A boat went silent. Nothing is taken away automatically: the officer sees it and acts."

**6 · The rescue (2:30)**
- *Boat crew*: phone B shows **New case** full screen. Tap **15 min**. Then **I've reached them**. Then **Record
  the rescue**: tap − twice (4 people), then **Yes** (someone is still there).
- *The desk* puts the case back at the top: **2 of 6 still there**. *Officer* sends Boat 5 again.
- *Boat crew*: accept, **I've reached them**, **Record the rescue**: 2, then **No**. The desk says **Rescued 6 of 6**.
- *The son*: phone A (his status page) asks "The team says 6 people were rescued. Is that right?" He taps **Yes**.
- *Presenter:* "The family confirms from the phone that asked. If they don't answer, nothing is blocked."

**7 · Proof (3:05)**
- *Officer* opens **Timeline & evidence** on the case: every item says "✓ unchanged since it was saved". Then
  **History** → **Check nothing was changed**: "✓ 1,8xx events verified".
- *Presenter:* "Every step is written down in order. If anyone edits the past, this check finds it."

## Say once, at the start or the end
- The people and phone numbers are made up; the villages and maps are real (OpenStreetMap).
- The clock runs 60× faster, so a 15-minute wait takes 15 seconds.
- Without a speech key, a voice clip can't be turned into text live; we type instead.

## If something goes wrong
`make demo-reset SCENE=<step>` puts everything back to the start of a step in under 20 seconds, and every open
screen reloads itself. The steps are `son` (1), `merge` (3), `sheet` (4), `stale` (5), `rescue` (6), `receipts`
(7). After a reset past step 1, the son's case comes from our recorded clip; say so.

## If a judge asks
| Question | Show |
|---|---|
| "What if the AI is down?" | It already is, unless a key is set: every case today was made by the word rules (the facts say **Rule**). |
| "Can someone change the record?" | `make tamper SEQ=12` in a terminal, then History → Check nothing was changed: it names the changed entry. |
| "Can it take a flood of reports?" | `make surge RATE=50 DURATION=60`: 3,000 made-up reports; the desk's numbers keep adding up. |
| "Can other teams' systems connect?" | `make partner-demo CASE=BR-199`: a simulated partner's signed note appears on the case. |
| "Who can see what?" | Phone B opens another team's case: "Not your team's case". |
