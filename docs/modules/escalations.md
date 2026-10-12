# escalations · the ticker turns silence into one clear ask

- **What it does:** the separate `ticker` process (same image, its own container) calls `tick()` every 5 s (`app/modules/escalations/ticker.py`), so an import or a slow model call can never delay an escalation. Timers live in Postgres: a restart loses nothing. One ticker at a time (advisory lock).
- **Contact overdue:** one conditional UPDATE marks assignments past `next_contact_due` as `overdue` (`assignment.overdue`, actor = system). **The case stays with the team** — boat teams lose network for hours while still working, and an automatic reassign sends two boats to one roof. The team turns **overdue**, so dispatch greys it out ("contact overdue: greyed until heard from") until it's heard from.
- **One escalation per team, not per case** (unique partial index): "Fire & Rescue Boat 5 overdue · 2 cases · no contact since 14:20. Radio them, then Extend or Reassign." Routed to the **EOC Duty Officer role**; if nobody acknowledges within 10 min it **rises to the EOC In-charge**. Two officers acknowledging the same one: the second gets **409 "Already acknowledged by R. Das at 14:22:05"** (T7).
- **No alarm floods:** when P1s wait past 5 min and **no team in the district has room**, one capacity-gap header: "P1 without owner · 41 · 0 teams free · ask SEOC for ≈ 21 boats (assuming 2 cases a boat)". RakshaSetu never requisitions anyone.
- **Self-resolving:** an escalation resolves when its cause is gone (the team was heard from; P1s got owners or teams freed up).
- **Heartbeats** (`POST /v1/teams/me/heartbeat`) set "last seen" only: 61 minutes of heartbeats with no deliberate contact still goes overdue (T6, tested).
- **Measured:** live stack, a demo-clock P2 (10 s to acknowledge): escalation opened **0.21 s** after the deadline (one run; the worst case is one tick, 5 s).

## Radio contact, Extend, Reassign (m42)

- **"Heard from Boat 5" is team-level** (`POST /v1/teams/{id}/contact {channel, new_eta?}`, officers, local): one log refreshes **every** live assignment the team holds (each to its phase's window: acknowledge, ETA + grace, or on-scene), clears overdue, returns the team to dispatch, resolves its escalation ("heard on VHF by R. Das"), and acknowledges any stand-down it owed. Each case's timeline says "Heard from Fire & Rescue Boat 5 on VHF by R. Das · new ETA 15 min". A channel is required (VHF · HAM · satellite · phone).
- **Extend** on an escalation is the same radio log. **Reassign** moves one case to another team (never an overdue one): the old assignment ends as `reassigned`, and the old team shows **"stand-down not acknowledged"** until its next contact. The escalation resolves when no cases are left in it.
- **T7:** a second officer extending or reassigning an escalation someone already resolved gets **409 "Already resolved: heard on VHF by R. Das at 14:22:05"**.
- `GET /v1/teams?incident=` lists the district's teams with status, load, last contact, last seen (display only) and stand-downs owed.
