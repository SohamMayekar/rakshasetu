# Simplify plan (m63–m72)

*Written at m63, 12 Oct 2026, before any screen changed. The product works (415 API tests, the golden path end to end); the problem is that it is hard to understand in a few minutes. This plan only **removes, hides, merges and renames**. No feature is added, no backend rule changes (priority, merge, ownership, closure, the hash chain), and every one of the PS's 9 required components stays reachable within 2 clicks of where the golden path shows it.*

## The test for every screen
1. **5 seconds:** a judge can say what the screen is for and what to click next. One screen, one job, one obvious primary button.
2. **About 7 things** compete for attention. Everything else goes behind "Show details", a collapsed section or a second click. Hide, don't delete.
3. **Plain English** an Indian college student understands (the glossary below).
4. **Three people** to sign in as, not twelve.
5. **Keep the soul:** the three promises as three short sentences on the desk; the honesty lines ("synthetic people", "the demo clock runs 60× faster", "simulated partner", "recorded clip"), one short line each.
6. CLAUDE.md §7 never-say words, colour means priority only, zero budget, synthetic people only.

## How the counts were measured

| Screen | Before at 1366×768 (controls + texts) | Before at phone 390×844 |
|---|---|---|
| `/` signed out | 1 + 2 = 3 | 1 + 2 = 3 |
| `/login` | 9 + 3 = 12 (12 profiles, 9 visible) | 10 + 3 = 13 |
| `/` signed in (Incidents) | 8 + 28 = 36 | 6 + 23 = 29 |
| `/desk/BR` | 18 + 53 = **71** | 10 + 49 = 59 |
| case panel (`/desk/BR?case=BR-199`) | 27 + 78 = **105** | 19 + 90 = 109 |
| `/audit` | 8 + 115 = **123** | 6 + 56 = 62 |
| `/partners` | 7 + 15 = 22 | 5 + 7 = 12 |
| `/surge` | 8 + 46 = 54 | 5 + 38 = 43 |
| `/demo` (admin) | 17 + 34 = 51 | 11 + 22 = 33 |
| `/r` | 2 + 6 = 8 | 2 + 6 = 8 |
| `/s/BR-199` | 0 + 12 = 12 | 0 + 12 = 12 |
| `/responder` (Boat 5, a new case on screen) | 5 + 11 = 16 | 5 + 11 = 16 |
| `/responder/case/58` | 5 + 9 = 14 | 6 + 9 = 15 |

## After (m72)
The same measure on the final code, same state: see `docs/VERIFICATION.md` §9.

| Screen | 1366×768 before → after | phone before → after |
|---|---|---|
| `/` signed out (front door) | 3 → 8 (two big choices + the team link) | 3 → 5 |
| `/login` | 12 → **6** (3 profiles) | 13 → **6** |
| `/` signed in | Incidents 36 → the duty officer goes straight to the desk; the Demo admin's All incidents 58 | 29 → desk; 43 |
| `/desk/BR` | 71 → **62** | 59 → **45** |
| case panel (`?case=BR-199`) | 105 → **76** | 109 → **59** |
| `/audit` → History | 123 → **76** | 62 → **48** |
| `/partners` (inside Demo) | 22 → 20 | 12 → 11 |
| `/surge` (inside Demo) | 54 → **36** | 43 → **30** |
| `/demo` (Demo admin) | 51 → **37** | 33 → **22** |
| `/r` | 8 → 10 (the text box and Send are on screen, not behind "Type instead") | 8 → 10 |
| `/s/BR-199` | 12 → 14 (one sentence, the steps folded) | 12 → 14 |
| `/responder` (a new case on screen) | 16 → 18 (each card has its next action) | 16 → 18 |
| `/responder/case/58` | 14 → 14 | 15 → 14 |


## Route by route

### `/` (the front door) · m64
- **Before:** signed out, a card with the name, the tagline and "Sign in". Signed in, the Incidents screen (a greeting, a card per incident with its three promise lines, an India map) for everyone.
- **On top:** two big choices only. **"I need help"**: the phone app for people in danger and their families (→ `/r`). **"Control room dashboard"**: for the district duty officer (→ `/login`). The tagline above them, one line.
- **Behind a click:** the rescue-team app, a small link under the two cards ("Rescue team? Open the team app"), not a third card.
- **Removed from this route:** nothing is deleted. Signed in, `/` takes each person to their own screen: the duty officer to their desk, the rescue team to its app; the **Demo admin** (who sees all three incidents) keeps the Incidents screen with its India map, renamed "All incidents" (component #1's "three incidents" lives there).

### `/login` · m65
- **Before:** 12 synthetic people (call-taker, two duty officers in two districts, in-charge, two state officers, the SEOC viewer, the system admin, four team leads).
- **On top:** exactly 3 profiles, each with one plain line: **Duty officer** (R. Das, runs the control room desk), **Rescue team** (Fire & Rescue Boat 5, the team's phone app), **Demo admin** (resets the demo scenes, QR codes).
- **Behind a click:** nothing. The other 9 stay **seeded but hidden** from the picker: the permission and IDOR tests use them (one test per PRD §4.2 row needs a call-taker, an in-charge, a SEOC viewer, an officer of another district and a team lead of another team). Rewriting ~60 tests to use fewer users would risk weakening them for no gain on screen (D20). They can still sign in with a username and password.
- **Removed:** the role jargon in labels ("EOC Duty Officer" → "Duty officer", "System admin" → "Demo admin").

### `/desk/[incident]` · m67
- **Before (71):** the header, three promise cards each with a sub-label (provenance · uncertainty · responsibility) and a 5-part equation, New report + Import sheet, a counted list of every row, each row with a P-code, a chip, a 2-line summary and a long button ("Assign → SDRF Boat 2 · 2.2 km · boat, rope"), the "On it · rescued, closing · closed" footer, the map, an escalation card with 8 controls.
- **On top:**
  1. the incident name, Live, the time;
  2. **the three promises, one plain sentence each:** "Nobody lost: 343 reports → 252 families", "No family counted twice: 91 repeats merged, 8 to check", "Nobody forgotten: every urgent family has a team" (or, broken, "2 urgent families have no team for 5 min", in ink);
  3. **Needs you now**: about 5 visible rows, each: the priority as a word ("Urgent"), the place, people, waiting time, and **one** action button in plain words ("Send SDRF Boat 2");
  4. an alert, when a team has gone quiet: one line + one button ("Open BR-199");
  5. the map;
  6. "New report" and "Add a sheet", quiet, at the list's top.
- **Behind "Show details":** the full equations, the refused count, "oldest waiting", the queue filters (click a number), the "On it / closing / closed" counts, the rest of the rows ("Show all 35"), the escalation's radio buttons.
- **Removed:** the three sub-labels (provenance · uncertainty · responsibility) and the long dispatch detail in the row's button (the distance stays, the kit list moves to the case panel).

### Case panel (`/desk/BR?case=…`) · m68
- **Before (105):** the priority well, ID, two status chips, the facts line, a "because" line, Check, Move pin, Change priority…, Close or cancel…, then four open sections: Assignment (suggestions with reasons), Facts (each value with a ●/○ mark and a method chip), Timeline & evidence (every event, report card, receipt, evidence with sha256), Audit.
- **On top, a summary card:** who (the people line: "6 people · on the roof · water inside · medicine · elderly"), where with the honest circle ("Thawe · within 150 m: the Durga temple and the bridge"), how many people, the status in plain words ("Waiting for a team · 3 min", "SDRF Boat 2 has it · check-in due 12:40", "Rescued 6 of 6"), and **one** next-step button (the same rule as the queue's action: send a team, heard on radio, fix the place, review the repeat, mark checked).
- **Collapsed below it, titled with the PS's words:** Assignment · Facts · Timeline & evidence · Audit. One click opens each; a queue action opens the section it needs.
- **Behind "More":** Move pin, Change priority, Close or cancel.
- **Removed:** the duplicate "not checked yet" chip.

### `/audit` → "History" · m69 (rename) and m66 (words)
- **Before (123):** a long table with seq, time, role code, event code (`assignment.acknowledged`), entity, reason, hash.
- **On top:** one sentence ("Every change is written down in order; each entry is locked to the one before, so an edit to the past is caught"), **one** button "Check nothing was changed" → "✓ 1,874 events verified: nothing was changed". The list: time, who, what happened in words, the reason.
- **Behind "Show details":** the sequence numbers and the hashes; partner anchors.
- **Removed:** nothing.

### `/partners` → inside Demo as "Show a partner system" · m69
- **Before (22):** the partner log in the sidebar for every officer.
- **On top (when opened):** "A partner system is another team's app that sends us notes, signed. This one is simulated by us." Then the log.
- **Behind a click:** the route stays; its sidebar item goes; it is linked from Demo.

### `/surge` → inside Demo as "Show it under load" · m69
- **Before (54):** in the sidebar; six rows with percentiles, lanes, the promise equations per incident.
- **On top (when opened):** "Reports a second", "Time to say received", "Waiting to be read", "Nobody lost" and the integrity check, in plain words; lanes and percentiles behind "Show details".
- **Behind a click:** the route stays; its sidebar item goes; it is linked from Demo.

### `/demo` · m71
- **Before (51):** six "Reset here" rows with paragraphs, then the language model, surge, partner moment, recorded clip and QR codes, each a card with a paragraph.
- **On top:** a numbered walk-through: 1 The son · 2 Never doubled · 3 The volunteer sheet · 4 Never stale · 5 The rescue · 6 The receipts; the current scene in big type with one line of what to do, a big **"Next scene"** button, the two QR codes, and the honesty lines (one short line each).
- **Behind "More controls":** reset to any scene, AI reading on/off, the recorded clip, the partner moment, the surge. Links: "Show it under load" (/surge), "Show a partner system" (/partners).
- **For the duty officer** (signed in on the projector): the same scene list read-only, the two "Show…" links, and one line on where the controls are (127.0.0.1/demo as Demo admin).

### `/r` (the reporter) · m70
- **Before (8):** the mic button, "Type instead", the 112 line; after sending, the case number, the reply, "See status", an optional call-back number form, "Report another".
- **On top:** one big microphone button, one text box, one Send button, the 112 line.
- **The confirmation asks for nothing:** "We have your report. You don't need to remember anything." + the case number to show, never to type; "See status". The optional call-back number moves behind a small link.
- **Removed:** the "Type instead" toggle (the box is just there).

### `/s/[id]` (the family's status page) · m70
- **Before (12):** the case number, a 4-step tracker, last update, the 112 note.
- **On top:** **one sentence**: "We have your report. The control room is finding a team." / "A rescue team has been assigned." / "The rescue team has reached the place." / "The team says people were rescued." Then the last update time; the family's optional question when there is one.
- **Behind "Show all steps":** the tracker.

### `/responder` (the team app) · m70
- **Before (16):** a full-screen New case with ETA chips; My cases cards with the ring.
- **On top:** My cases, each card with **one big next action** ("I've reached them", "Record the rescue"), the check-in time. A new case still takes the whole screen with "Accept: there in 15 / 30 / 60 min".
- **Behind "More":** release, the long note about "last seen".

### `/responder/case/[id]` · m70
- **Before (14):** map strip, the caller's words, the summary, place, Navigate, Call, the ring, one state button, More.
- **On top:** the caller's words, the place, Navigate, and the one big state button.
- **Behind "More":** Call (the number reveal is logged), release.

## Glossary (applied everywhere in m66; `make copy-check` refuses the jargon)
| Jargon (never on screen) | Plain words |
|---|---|
| P1 · P2 · P3 · P4 (alone) | **Urgent · High · Medium · Low** (the shape and colour stay; "P1" only in a tooltip) |
| provenance · uncertainty · responsibility (sub-labels) | removed; each promise is one plain sentence |
| household | family |
| case created | new case |
| possible duplicate · likely duplicate | maybe a repeat (same family) |
| merge suggestion · match | possible repeat |
| refused (merge) | kept apart |
| unchecked P1 | Urgent · not checked yet |
| check (button) | Mark checked |
| assign → team | Send *team* |
| dispatch suggestions | nearest suitable teams |
| acknowledged · ETA 15 | accepted · there in 15 min |
| reassign | send another team |
| release | hand back |
| escalation | alert |
| contact overdue (kept: CLAUDE.md copy) | contact overdue · not heard from since 10:29 |
| EOC · EOC Duty Officer | control room · Duty officer |
| SEOC · SEOC viewer | state control room · State viewer |
| System admin | Demo admin |
| ingest · intake · pipeline | receive · reading it |
| fixture · recorded transcript | a recording (not live) |
| STT · speech-to-text | speech to text |
| LLM · language model | AI reading (facts with their quotes) |
| method chip AI · Rule · Human | AI · Rule · Person |
| annotation | partner note |
| webhook | message to a partner system |
| partner log | partner system |
| hash chain · hash-chained · sha256 | locked history · fingerprint |
| Verify chain | Check nothing was changed |
| ✓ matches the audit log | ✓ unchanged |
| integrity: 0 problems | all checks pass |
| surge | under load (a rush of reports) |
| lane | queue |
| ×60 | the demo clock runs 60× faster |
| IDOR · scope · idempotency | never on screen |

## The three profiles (m65)
| On the sign-in screen | Seeded user | Lands on | Sees |
|---|---|---|---|
| **Duty officer** · runs the control room desk | `rdas`, R. Das | `/desk/BR` | Bihar (BR) only: Desk · History · Demo |
| **Rescue team** · Fire & Rescue Boat 5's phone app | `boat5` | `/responder` | its own assigned cases only |
| **Demo admin** · resets the demo, QR codes | `admin` | `/demo` | all three incidents (BR, OD, HP): All incidents · History · Demo |

The 9 others (`priya`, `asinha`, `mkumar`, `spatra`, `nthakur`, `seoc`, `ndrf03`, `amitra`, `boat1`) stay in `data/scenarios/users.yaml` and the database for the permission and IDOR tests, off the picker.

## The 9 required components: where each stays reachable
| # | Component | Where the golden path shows it | After |
|---|---|---|---|
| 1 | Incident lifecycle | the case panel's status | the summary's status line (0 clicks); the steps in Timeline & evidence (1 click) |
| 2 | Role/permission | the 403 on the team's phone; who can do what | unchanged; 3 profiles show 3 surfaces |
| 3 | Event ingestion | voice, forward, sheet, surge, partner | New report / Add a sheet on the desk (0); surge and partner from Demo (1–2) |
| 4 | Map/timeline | the circle and the timeline | the map (0), the summary's circle line (0), Timeline & evidence (1) |
| 5 | Task assignment | Send a team | the row's button (0); Assignment section (1) |
| 6 | Escalation | contact overdue → one alert | the alert above the list (0); Assignment (1) |
| 7 | Evidence | 7 items ✓ | Timeline & evidence (1) |
| 8 | Audit trail | ✓ events verified | History → Check nothing was changed (2); the case's Audit section (1) |
| 9 | Real-time | the desk and phones update | unchanged (0) |

## Order of work
m64 front door → m65 three profiles → m66 plain words + copy-check → m67 desk → m68 case panel → m69 sidebar → m70 phone screens → m71 demo walk-through → m72 release (gate, golden screenshots, docs, STATUS with real numbers). Each branch keeps the golden path green; where a test pinned an old label it is rewritten to assert the new label while protecting the same rule, and the commit says so.
