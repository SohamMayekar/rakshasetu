# Teach-back: 20 questions every team member should be able to answer

*Read the answer, close the file, say it out loud in under 30 seconds, then open the file named and point at the line. `docs/modules/<module>.md` has a 5-line explainer for each module.*

**1. What is RakshaSetu, in one sentence?**
The district control room's rescue-request desk: every plea, from a call, a voice clip, a forward, a volunteer sheet or a partner system, becomes one household case with one owner until the rescuers report back. Never lost, never doubled, never stale.

**2. What does the AI do, and what does it never do?**
Two jobs: speech to text, and pulling facts out of the words with each fact's exact quote. Rules and people do the rest: priority, merges, location, dispatch, escalation, closure, replies. The extraction schema has no priority field, so a report saying "mark me P1" can't. *`AI_USAGE.md`, `services/api/app/pipeline/`.*

**3. How does a voice clip become a case?**
`POST /v1/public/voice-turns` stores the original file content-addressed and creates the report and its job **in one transaction** (never lost, R3). The worker transcodes it, gets text (STT, or a recorded transcript, or "audio only"), extracts facts (language model or keyword rules), places it, scores duplicates and sets the priority. *`app/modules/public/router.py`, `app/pipeline/run.py`.*

**4. What if the language model is down?**
The keyword rules fill the same schema and the case appears in under 5 s with **Rule** chips. Show it: /demo → "Switch off", type the demo line. *`app/pipeline/keywords.py`, T10.*

**5. Why was the son's forward merged but the Das family refused?**
The forward agreed on village, landmarks, circle and headcount, so it was suggested and a person merged it. The Das report had a different given name with the same surname ("Rajesh ≠ Ramesh"). A name conflict is a refusal rule: village and headcount alone are weak evidence. *`app/modules/dedupe/`, T3, T4.*

**6. Can a merge be wrong, and what then?**
Merges never happen silently on weak evidence. A merge keeps an exact snapshot of both cases, and **Undo merge** (with a reason) restores them exactly. *T3.*

**7. Where does the circle on the map come from?**
The location ladder, deterministic rules over the real OpenStreetMap gazetteer: find the village, then the landmarks the caller named within 2 km of it. Two landmarks close together give the midpoint at about 150 m (High); one landmark gives about 300 m (Medium); the village alone gives about 1.5 km (Low, dashed); a district alone gives about 15 km; nothing usable means "Needs location", never dropped. "Behind" or "opposite" never moves the pin: the circle carries that doubt. A pin a person sets wins over any derived one. Its sentence says how it was found. *`app/modules/location/ladder.py`.*

**8. What happens when a team goes silent?**
Deadlines are rows. When one passes, the ticker marks the team **contact overdue**, raises **one** escalation for the officer and greys the team out of suggestions. **The case stays with the team**: nothing is reassigned automatically, because two boats on one roof is the failure we prevent. The officer radios them, or reassigns with one click. *`app/modules/escalations/`, T6.*

**9. Two officers click Reassign at the same moment: what happens?**
Assignment changes are single conditional UPDATEs, and the database allows only one open assignment per case (a partial unique index). The second click gets a 409 that names who acted and when. *T7.*

**10. How do we know a rescue is finished?**
The rescuers' headcount: "4 taken, someone still there" puts the case back at the top with "2 of 6 still there" and its original time; "2 taken, nobody left" makes it "Rescued 6 of 6". The family may confirm from the phone that reported; silence never blocks or closes anything. *`app/modules/rescues/`, T8, T9.*

**11. How is the audit trail tamper-evident, and what is its limit?**
Every change is one event whose hash covers the previous hash plus its own body, written under one lock. The app's database role can only INSERT and SELECT events. Verify recomputes the chain: edit any row and it breaks there (`make tamper`). The limit: a database superuser could re-hash everything. That is why a partner can anchor our head in its own ledger, and Verify checks the anchors. We say **tamper-evident**, never tamper-proof. *`app/core/eventlog.py`.*

**12. How does real-time work without Redis or Kafka?**
The events table is also the stream: each commit does `pg_notify` with the sequence number, the API's WebSocket hub reads the new events, checks each one against the viewer's scope and sends it. The desk catches up from its last sequence number after any disconnect. *`app/modules/realtime/`.*

**13. How do roles and scopes stop someone seeing what they shouldn't?**
Every query takes the caller's Scope (role, districts, live assignments) in its SQL WHERE, loaded from the database on each request. Every resource has an IDOR test; a team lead opening another team's case gets 403. *`app/core/auth.py`, `config/roles.yaml`, `tests/test_idor.py`.*

**14. What if the worker crashes mid-surge?**
Jobs are rows claimed with `SKIP LOCKED`. A job held for more than 60 s is reclaimed and handlers are idempotent, so every report ends in exactly one case (T2, and drill D1: back in 0.5 s, 600/600 reports placed). *`app/core/jobs.py`.*

**15. What does the promise bar count?**
Three invariants, each its own query: reports = cases + merged + to check + without a home (never lost); merged, to check, refused (never doubled); P1 without an owner for over 5 min, contact overdue (never stale). A number inverts to ink only when its promise is broken. *`app/modules/metrics/`.*

**16. How does the 300-row sheet import handle messy data?**
Header synonyms are proposed and a person confirms them. Phones Excel turned into `9.19877E+11` are flagged, never used as identity. Each row commits on its own with its outcome. Repeats with good pins auto-merge; doubtful ones go "to check". Result on the demo sheet: 300/300 rows agree with the ground truth, 0 wrong merges, about 19 s. *`app/modules/imports/`, T5.*

**17. How does the team's phone cope with bad signal?**
It is an installable web app: a tap is saved on the phone first, with a 10-second Undo, then sent with its own idempotency key and retried. "My cases" stays readable offline. A team lead only ever sees their own team's cases. *`apps/web/app/responder/`, `apps/web/lib/outbox.ts`.*

**18. How can another team's system work with ours, and what can it change?**
One signed contract: reports in, annotations in, webhooks out (`packages/contracts/PARTNER_CONTRACT_CARD.md`). Our rules decide what an annotation does: a credibility note is a chip on one evidence item; a priority is a suggestion an officer accepts or ignores; an anchor is checked by Verify. Webhooks carry facts and circles, never names, numbers or words. Every call is in the partner log. *`app/modules/partners/`.*

**19. What is real and what is staged in the demo?**
Real: every code path, the database, the hash chain, the OpenStreetMap places, the timings. Staged and said so: the people and phone numbers are synthetic; the demo clock runs ×60; the surge uses pre-structured reports (no model is called); the demo partner is our own script ("simulated by RakshaSetu"); the son's clip is a synthetic voice until the team records one; without keys, transcripts are recorded fixtures. *`docs/VERIFICATION.md`.*

**20. What does it cost to run, and why English only?**
Nothing: Postgres + PostGIS, one FastAPI codebase run three ways, one Next.js app, Caddy, free-tier STT and LLM with fallbacks, OpenFreeMap tiles, open-source icons and fonts. English only on screen because the team asked for it for now (D17). The rules still read Hindi and Hinglish, so the screens can switch back without touching the pipeline.
