# responder · the boat's phone

- **m70:** each card in My cases has its one big next action ("I've reached them", "Record the rescue"), and shows its last taps ("Accepted · ETA 15 min · Sent 22:31"). A new case still takes the whole screen: "Accept: we'll be there in 15 / 30 / 60 min". On the case screen, Call is under More with Hand back.

- **What it is:** `/responder` (reachable through the public tunnel; the team lead signs in with username + password). Built for **Android Chrome** (the Vibration API isn't on iOS).
- **My cases** (`GET /v1/teams/me/cases`): each case with its check-in ring, phase ("new · on the way · on scene") and straight-line distance from the team's last known position.
- **A new assignment takes the whole screen:** priority, people, needs, place, distance, the *because*, and **one tap on an ETA chip (15 / 30 / 60 min) acknowledges**. It arrives over the WebSocket with a vibration and a short tone. Measured: **1.3 s** from the officer's Assign to the card on the phone (one run).
- **The case screen** (one screen, no tabs): a map strip with the circle (never a bare pin; "the place is approximate: search the circle" when it isn't High), **the caller's own words first, in their script**, then the summary, **Navigate** (the phone's map app via `geo:`), **Call · on site** (`POST /v1/cases/{id}/reveal-contact`: the assigned team's reveal is logged automatically; the event keeps only the masked number), "You own this · check-in due", and **one state-driven button**: Acknowledge (ETA chips) → **Reached** → Record rescue (m45). **More** holds Release (with a reason).
- **Every tap** gets its own id (the Idempotency-Key) and the time it really happened, is kept on the phone ("Saved on phone · sending in 10 s" with **Undo**, no confirm dialogs), then sent and retried until accepted ("Sent 03:39"). Buttons are ≥ 64 px, full width, in the bottom third.
- **"Last seen"** is sent every 10 s while the app is open and is **display only**; the screen says so.
- **A case that isn't this team's** shows the server's **403** plainly ("Not assigned to your team"), with what to do.
- **Not yet:** the rescue sheet (m45), install manifest / wake lock / offline copy (P1 #7).
