# 11 · Cut list: what we refuse to build

*Lead session · 12 Oct 2026. The reasons come from the specialist reports cited in brackets. Anything here returns only by a written decision that names what it replaces.*

> **Bottom line:** every item below either doesn't help the PS or the score, adds infrastructure, is hard to explain, is decorative, duplicates 112 or an existing system, is a generic hackathon feature, or costs money. Together, the cuts and deferrals free about **25 session-hours**, which is what makes the golden path buildable (00 §5.5).

---

## 1. Refused outright (CUT): not at the event, not as "extra time"

| # | Cut | Category | Why (source) | Saves |
|---|---|---|---|---|
| X1 | **LangGraph + Postgres checkpointer + `interrupt()` approval** | Buzzword, hard to explain | It changes no behaviour (approval is a DB row, timers live in Postgres). It needs a second DB driver (psycopg 3) and invites "why agentic?" next to the misrepresentation ground (08 §3, 07 A3, 02 §8) | 2–3 h |
| X2 | **The "agentic", "agent replies", "triage agents", "AI prioritises", "22 languages", "novel lease", "tamper-proof", "national command", "₹0 tonight" wording** | Misrepresentation risk | Each one is false by our own design or overstated (02 §3, 02b K5, 08 §3) | — |
| X3 | **LLM free-text `summary_en`** | Decorative, injection surface | The only AI prose on screen and the only thing a prompt injection can echo. A template line does the job (04 N34d) | 0.25 h |
| X4 | **Background-heartbeat check-ins** | False mechanism | A PWA with the screen off can't send them (VERIFIED, 06 §6). Where the app does run, an idle phone keeps a case "alive" forever (04 N11). Replaced by contact deadlines (00 C8) | — |
| X5 | **Fixed per-priority check-in cadence (P1 every 15 min, …)** | Field-wrong | It escalates a 10-hour collapse rescue every hour, and alarm fatigue kills the promise (05 F2). Replaced by per-phase deadlines that use the team's own ETA | — |
| X6 | **Case escalation to "state admin" / "national admin"; the "NDMA desk" role** | Field-wrong | No single rescue case goes to Delhi. Under IRS the district's RO decides, and the state sees resource requests (05 F3, 05b §4–5, VERIFIED) | config |
| X7 | **Any UI or wording that Sahaay "dispatches" or "requisitions" NDRF** | Field-wrong | NDRF is requisitioned by the state or the DM, then works under the Operations Section (05b I14, VERIFIED). We assign teams already deployed in the district | — |
| X8 | **`/v1/ingest/telemetry` + our own river-gauge simulator** | Fake, decorative | There's no IoT domain. A sensor we fake ourselves has no demo moment and invites "is this real?" (08 §1.4). Partner signals are labelled simulated; the honest proxy is NDMA's real CAP feed (LATER) | 1.5–2 h |
| X9 | **n8n flows** | Infrastructure, licence | Another container that duplicates the worker. Its Sustainable Use License limits use to internal or non-commercial purposes (08 §3, VERIFIED) | 3–4 h |
| X10 | **Incident timeline strip** (reports per 5 min under the map) | Dashboard widget | A histogram is exactly the "another dashboard" reflex. The case's timeline is the PS's "timeline" (06 §8, 02 §8) | 1.5 h |
| X11 | **Surge auto-enter / exit + "Surge mode" banner** | Invisible | Nobody sees a threshold. The P0 behaviours (no re-sort, "▲ new" pill, 1 s batches) and the ingest p95 on the surge screen carry the constraint (02 §8) | 1 h |
| X12 | **Shelter check-in** | Next to a non-goal | A new role and surface beside "no shelter finder" (06, 02) | 2 h |
| X13 | **In-app config viewer; team and user admin screens; admin "create incident" form** | Decorative | YAML open in the editor is more credible than a read-only screen; seeds manage teams and users; `curl` creating a 4th incident proves "no code change" (06 §8) | ~4 h |
| X14 | **Separate "Needs a human" inbox and separate Evidence tab** | Duplicate surfaces | A second inbox is ignored at 2 AM; evidence lives inline in "Timeline & evidence" (06 §3) | 1 h |
| X15 | **Per-event toasts, modals, sounds; raw model scores (0.91) in the queue** | Alert fatigue | The queue is the only alert surface; words, not floats (06 §4.4) | — |
| X16 | **Command-centre i18n** | Cost > value | Operators work in English or Hindi. i18n stays for the reporter and responder PWAs only (08 §2) | 1–2 h |
| X17 | **Digit-clip concatenation for spoken case numbers** ("A-S do-ek-chaar") | Cost > value | The case ID is on screen and shareable; one fixed recorded Hindi sentence carries the emotion (02 §8, 06) | ~3 h of human time + 1 h build |
| X18 | **A controllable fake clock for scenario tests; the outbox publisher loop** | Over-engineering | Tests set `expires_at` in the past. NOTIFY already fires on commit, and the events table *is* the outbox (07 A3) | ~1.25 h |
| X19 | **Expo native app** | Infrastructure | PWAs are "apps over websites" without a second build chain (02 §8) | — |
| X20 | **Live GPS tracking of boats; team-to-control-room chat** | Infrastructure, duplicates radio/WhatsApp | Needs a network the field doesn't have; position age + radio check-ins are honest (05 §8) | 3 h+ |
| X21 | **Team "silence scores", leaderboards, team credibility scores** | Harmful | Overdue ≠ failure (dead zones); blaming teams kills adoption (05 §8, 04) | — |
| X22 | **Medical triage tags (START), patient tracking** | Duplicates 108 / hospitals | Sahaay records the need and the hand-over; it doesn't triage patients (05 §8) | 3 h+ |
| X23 | **Generated IRS/ICS forms, incident action plans, org-chart builders** | Bureaucratic theatre | Judges see paperwork, not rescue. Mention the IRS mapping in words only (05 §8) | 3 h+ |
| X24 | **Volunteer registration and skills matching** | Sahana Eden's territory | Huge and not the PS (05 §8) | — |
| X25 | **Crisis Cleanup-style call centre with language routing; IVR; live duplex calls** | Costs money, duplicates 1070/1077 | Telephony is a non-goal (09 §6, PRD §3) | 8 h+ |
| X26 | **A flag service, runtime toggle UI, plugin framework, dual v1/v2 report handlers, form builder** | Over-engineering | Each costs more than it saves on any likely curveball (08 §2) | — |
| X27 | **The SMS `HELP <village> <people> <need>` format** | Burden on victims | Nobody on a roof should have to remember a syntax. SMS free text goes through the same extraction (08 §2) | — |
| X28 | **The demo scene "nobody tapped Accept within 15 s"** | Wrong failure mode | Teams fail by going quiet after acknowledging, not by missing a button (05 §9). Replaced by the radio-only boat whose ETA passes | — |
| X29 | **Airplane mode as the "cause" of expiry** | Proves nothing now | With the heartbeat display-only, airplane mode doesn't expire anything. The deadline does (00 C19) | — |
| X30 | **Claiming SDG 3.d** | Stretch a judge can check | Its indicators are health-regulation capacity and antimicrobial resistance (08 §3, VERIFIED) | — |
| X31 | **Integration claims with NDEM, IDRN, DRIMS or ERSS** | Unverifiable overclaim | We have no access; say "mention, don't build" (05b §2) | — |
| X32 | **Stage time comparing us with student repos or "what Ainna missed"** | Petty, wastes the pitch | Compare only with 112 ERSS, Ushahidi/Sahana, rescuekerala and Crisis Cleanup, in one line each (02, 09) | ~1 min of pitch |
| X33 | **Cyber PS 3 lockfile scan, Cloud PS 3 proxy, AI PS 3 copilot as convergence entries** | Cosmetic convergence | Outside the product or read-only (08 §1.3) | — |
| X34 | **The always-zero "0 unaccounted" as a lone number** | Looks fake | Replaced by a funnel that adds up (06, 02b) | — |

## 2. Never building (standing non-goals, re-confirmed)

Other teams build these, and they dilute the pitch (BRIEF §6, PRD §3):
- citizen SOS app with GPS and login
- shelter finder
- relief logistics or inventory
- broadcast alerts (SACHET exists)
- payment gateway
- route optimisation
- flood prediction or any other prediction
- AI that assigns, merges, closes or prioritises on its own
- anything that costs money

- direct integration with 112 / 1070 / 1077 / NDEM (roadmap wording only)
- any claim of DPDP compliance or government approval

## 3. Deferred (LATER): not at the event unless P0 + P1 #1–4 are green

These are good ideas, ranked in 00 §9 for extra time. **They are not to be started by a build session on its own initiative.** On stage, each one is a prepared Q&A answer, not a feature.

| Deferred | The Q&A line instead |
|---|---|
| NDMA SACHET CAP alert layer | "There's no IoT team here, so we don't fake sensors. NDMA's public CAP feed is the honest source; it's next." |
| WhatsApp chat-export import | "The Groups API is closed to us. A volunteer can upload the group's export, and it goes through the same pipeline as the sheet." |
| Team strip; ad-hoc team creation | "Team status is in the seed; the officer logs radio contact per team in one click." |
| Site (same place, different households) | "We refuse the merge, as you saw. Linking them as a site that sums headcounts is designed, not built." |
| Quarantine a source; hold-don't-reject | "Every case knows its source, so containing a poisoned import is one query." |
| Full offline responder mode; late-sync conflict alert | "Every tap already carries its own ID and the time it happened; the offline queue is the next step." |
| Cyber identity credentials | "Our Cyber partner anchors the chain head; credential verification is the next integration." |
| "Still stranded?" callback | "Silence never closes or escalates a case; the callback runs inside WhatsApp's free 24-hour window." |
| Sub-case split for large groups; drop-off point; unlisted rescues | "Partial rescues loop back with the original time. Splitting a school across three boats is designed, not built." |
| Field-ops pause at night or landfall; shift-handover screen | "Escalations bind to roles, not people, so a new shift inherits them. A pause flag is a one-hour addition." |
| Role-shaped queues; keyboard shortcuts; Web Push; config-profile switch | — |
| Gazetteer scan; release-reason enum; `not_found_limit`; relay-phone prompts | Covered by the ladder, a human pin and officer decisions in the prototype |
| SitRep CSV export; IDRN import; ERSS two-way link; real SMS via a DLT header; OpenTimestamps | Roadmap lines only |

**The rule for future sessions:** if an item isn't in 00 §5.1 (P0) or §5.2 (P1), it isn't built before freeze. If it's in this file, it isn't built at all without a written swap.
