# How to pitch RakshaSetu

*For the team. Read once, rehearse twice, keep the "what not to claim" list in your pocket.*

## The one thing a judge should remember
> **One command layer for every emergency.** Every report becomes one case with one accountable team, followed with its
> evidence until the people are confirmed safe. Never lost. Never doubled. Never stale.

If they remember only three words: **one case, one owner, confirmed safe**.

## The problem, in the brief's own words
Emergency information is scattered across calls, messaging apps, spreadsheets, dashboards and departmental systems.
"The challenge is not building another dashboard; it is creating a workflow that preserves **provenance, uncertainty
and responsibility** while the situation changes rapidly."

| The brief's word | Our answer, in one line | Show it |
|---|---|---|
| **Provenance** | Every fact sits beside the exact words it came from; evidence is kept by fingerprint | open a case → Facts (the quote), Timeline & evidence |
| **Uncertainty** | A place is an honest circle, not a pin; a match shows its reasons and can be undone; "not merged" is shown | the circle on the map; the match with reasons |
| **Responsibility** | One owner per case; a quiet team is raised to a person, never reassigned silently; the family confirms | assign → let it go overdue → Alerts |

## Before you go on stage (15 minutes)
1. `make env && make up` then **choose a path**:
   - **Live build (recommended, shows nothing is hard-coded):** `make seed`. The platform is empty with one admin.
   - **Rehearsal / safety net:** `make seed-demo` (four sample packs) and `make demo-reset SCENE=son`.
2. Open the desk on the projector, sign in with **Control room** (one tap, the national admin).
3. Phone A: open `<tunnel address>/r`. Phone B: `<tunnel address>/responder`. No phones? two narrow browser windows.
4. Optional keys in `.env`: `SARVAM_API_KEY`, `GROQ_API_KEY` for live speech and AI reading. Without them everything still works from word rules (say so).
5. Run `make verify` once so the audit check is green, and have `make telemetry-demo` ready in a terminal.

## The 3-minute version (the default)
| Time | Say | Do |
|---|---|---|
| 0:00 | "In a disaster, help fails in the gaps between calls, teams and spreadsheets. This is one command layer for every emergency." | Landing page, hero |
| 0:20 | "Here is the whole product in 20 seconds." | Scroll to **The whole product in 20 seconds**, let it play |
| 0:45 | "This is not a flood app. An incident is a form." | Desk → **Incidents** → *New incident* (name, centre, a district). Create it. |
| 1:10 | "Teams are any agency with any capabilities." | **Teams** → *Add a team*: pick capabilities (fire, hazmat, ambulance…), add the lead |
| 1:35 | "A family asks for help, in their own language, no login." | Phone A: speak or type, add a number. It lands on the desk |
| 1:55 | "Rules rank it and show why. AI only turned speech to text and pulled facts with their quotes." | Open the case: priority reason, the quote, the circle |
| 2:15 | "One owner. The team's phone accepts and counts who came out." | Send the team → Phone B accepts → records 4 of 6 → desk shows *2 still there* |
| 2:40 | "The family confirms. Nothing is closed on a guess." | Phone A: "Is that right?" → Yes |
| 2:55 | "Everything is on a tamper-evident trail." | History → *Check nothing was changed* |

## The 5-minute version (adds the three convergence beats)
Insert after 2:40:
- **Sensors (IoT):** `make telemetry-demo`; open **Sensors**. "Partner instruments report signed readings beside the families. They are *simulated* by our script, and labelled so. A reading never changes a priority; it is context for a person."
- **No signal:** open `/mesh`. "A request is saved on the phone and sent by itself. The phone-to-phone relay is designed and shown here as a labelled simulation; it needs a native app."
- **Dozens at once:** `make surge RATE=50`. "The queue stays a short list of what needs a person, and it never re-sorts under your cursor."

## The answer to "AI prioritizes events"
> "We deliberately kept the ranking out of the model. In an emergency you must be able to ask *why*. AI does two jobs:
> speech to text and pulling out facts with their exact quotes. Rules rank, and every reason is on the screen. A person
> decides. With no AI keys at all, every case is still created."

## Questions you will get
| Question | Answer |
|---|---|
| Is it only for floods? | No. An incident is a form; hazards include fire, gas, accidents, earthquakes, storms; teams are 20 agencies and 24 capabilities. A clean start has no city or disaster assumed. |
| Which languages? | Voice goes through Sarvam, built for Indian languages. Word rules read Hindi, Hinglish, Marathi and English; the AI path reads the rest. Screens are English for now. (Do not give a number.) |
| Is the Bluetooth mesh real? | Saving on the phone and sending later is real and works. The phone-to-phone relay is designed, with the server ready for it; it needs a native app. The page says "simulation". |
| WhatsApp? | Forwarded messages are read today. A number a family can message is designed (`docs/WHATSAPP.md`), not switched on. Groups are closed to every system; a chat export can be uploaded as a sheet. |
| Are the sensors real? | No. Our script plays a partner's instruments and every card says *Simulated*. The signed interface is real. |
| What stops a fake report? | Every report has one id; repeats merge; a person at the desk still checks and decides; partner calls are HMAC-signed with a replay window. |
| What if two officers act at once? | One owner per case is enforced by a database index; the second gets a conflict naming who acted and when. |
| What if the AI is wrong? | Every extracted fact is checked against the caller's own words; a miss turns amber and a rule cross-checks. Nothing it says changes a priority. |
| Is the audit trail blockchain? | No. It is a hash chain: tamper-evident, not tamper-proof. A partner's anchor receipt would catch a superuser re-hashing it. We say "tamper-evident". |
| How does it scale? | One Postgres with a job queue and the event log as the live stream; `make surge` sends 3,000 synthetic reports and the measured numbers are in `docs/MEASUREMENTS.md`. Honest limit: one region, one database. |
| What does it cost? | No paid service. Free tiers sit behind provider interfaces with fallbacks. |
| Who is it for? | A family, a duty officer, a national desk, a responding team, a partner. Each sees only what they need. |

## What not to claim (the repo's own rules)
- Do not say "22 languages", "agentic", "AI agent", "AI prioritises", "tamper-proof", "national command" (say *a national layer of district desks* or *national incident command layer*), "help is on the way".
- Do not say the mesh, WhatsApp or real sensors are **built**. Say *designed*, *simulated* or *planned*.
- Do not present sample data as real. Every person and number in the sample packs is synthetic.
- Do not give outcome statistics (lives saved, minutes saved). None are measured.
- Do not show a speech key's result as live if you did not set the key; the receipt says what it was.

## If something fails on stage
| Failure | Do this |
|---|---|
| No internet | Everything runs on the laptop; speech and AI fall back to word rules and the receipt says so |
| Phone cannot reach the tunnel | Use two browser windows on the laptop |
| Voice not transcribed | Type the report; say "with a speech key this is spoken" |
| Desk looks empty | `make seed-demo`, then `make demo-reset SCENE=son` (this wipes your own data) |
| A screen errors | Reload; the live stream back-fills from where it dropped |

## Slides (if you must have them): eight, one idea each
1. The problem: scattered reports (a screenshot of calls, a chat, a sheet). 2. One command layer (the landing hero).
3. One case, one owner, confirmed safe (the 20-second story). 4. Any disaster, any team (incident form + capability chips).
5. Honest AI (what it does and does not). 6. Works with no signal (save, send later; relay designed).
7. The brief, point by point (`docs/BRIEF.md` as a table). 8. What is real, what is next (built / simulated / designed).

## Roles (four people)
- **Presenter:** the story, the one-liners, the Q&A. **Officer:** the desk. **Team:** Phone B.
  **Family:** Phone A. Rehearse the handoffs; the demo is about 3 minutes.

## Practice plan
- T-24h: two full runs on the empty platform. T-3h: one run on the venue network. T-30m: `make verify`,
  charge phones, set brightness, open the tabs. Time yourself: 3:00 means 3:00.
