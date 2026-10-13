# The brief, point by point

> **A clean start.** `make seed` creates an empty platform with one admin: no city, no district, no demo cases. Start your own incident, add your teams, and it is yours. `make seed-demo` loads the four sample packs for rehearsal.

*Problem statement: National-Scale Incident Command Operating Layer. This page maps each ask to what is built, where to see it, and what is honestly not there. Short on purpose: every row is something a judge can open.*

| The brief asks for | What is built | Where to see it |
|---|---|---|
| **Incident lifecycle** | draft → active → standing down → closed, each change with a reason on the audit trail. A new incident is a form (code, districts, centre) and receives reports at once, no code change | `/desk/incidents` (national admin) · `PATCH /v1/incidents/{id}` |
| **Role / permission system** | 8 roles in `config/roles.yaml`; scope applied inside every SQL `WHERE` (rule R8); a duty officer sees only their own districts, the national admin sees all; one IDOR test per resource | `make test` · sign in as a duty officer vs the admin |
| **Event ingestion API** | one canonical report; channels: voice, typed, forwarded message, volunteer sheet, signed partner API (`POST /v1/ingest/reports`), signed sensor readings (`POST /v1/ingest/telemetry`) | `docs/modules/`, `packages/contracts/` |
| **Map / timeline** | one national map of honest circles (queue, map and case panel on `/desk`); per-case timeline with the evidence behind each line | `/desk` |
| **Task assignment** | one live owner per case (database index), ranked team suggestions with reasons, acknowledge / reached / rescued from the team's phone | `/desk` · `/responder` |
| **Escalation** | a team that misses its check-in is raised to a person; the case is never reassigned automatically; two officers cannot both take it | `/desk/alerts` |
| **Evidence references** | clips, photos and messages stored by content hash and shown on the case with "unchanged since saved" | the case's *Timeline & evidence* |
| **Audit trail** | hash-chained, tamper-evident events; "Check nothing was changed" re-verifies the chain; `make tamper` shows it break | `/audit` · `make verify` |
| **Real-time updates** | one WebSocket stream, scoped per person, back-filled from `?since=` after a drop | the "Live" light on `/desk` |
| **Usable when dozens arrive together** | the queue shows only what needs a person; sheets arrive as one group row; `make surge RATE=50` | `make surge` |
| **Not hard-coded to one incident** | the desk, queue, map, alerts, teams, sheets and sensors are all national; incidents are rows | `/desk` shows MH, BR, OD, HP together |

## The convergence line

- **AI prioritizes events.** AI reads speech and extracts facts with their quotes; *rules* rank, and every reason is shown (see `AI_USAGE.md`). We kept the ranking out of the model on purpose: in an emergency you must be able to ask "why?".
- **IoT supplies live telemetry.** A partner's instruments `POST /v1/ingest/telemetry` (same signing, replay window and rate cap as every partner call). Each sensor is read against two lines; only a *change of state* goes on the audit chain; the desk shows the sensors beside the cases. **The demo's sensors are our own script (`make telemetry-demo`) and are labelled Simulated everywhere.** A reading never changes a case's priority.
- **Cybersecurity provides identity, trust and audit.** Sign-in by role; partner requests are HMAC-signed over the raw bytes with a ±300 s window; phone numbers are encrypted at rest and masked; the audit trail is tamper-evident (not tamper-proof: a database superuser could re-hash, which a partner's anchor receipt would catch).

## Teams and capabilities
A team can be any agency and carry any of 24 capabilities (`services/api/app/capabilities.py`): boat and water rescue, divers, rope and high-angle, heavy lifting, collapsed-structure search, vehicle extrication, mountain, air, animal rescue, firefighting, hazmat and gas, power isolation, first aid, ambulance, psychosocial, evacuation, shelter, food and water, relief supplies, road clearance, structural engineering, communications, drone survey, traffic and crowd control. A boat or heavy lift is *required* only where the job cannot be done without it; everything else is *preferred*, so a team that lacks it is still offered and the officer decides. The admin adds teams, and each lead's sign-in, from **Teams → Add a team**.

## Disaster types
Floods, cyclones and landslides have packs. Fires, road accidents, earthquakes and storm damage are read by the word rules in Hindi, Hinglish, Marathi and English, ranked by the priority rules and matched to teams (see `docs/modules/triage.md`). There is no demo pack for them: type a report into the desk's *New report* box to see it.

## Not there, and said so

- No live WhatsApp number (forwarded messages are read; a family-facing number is designed, see `docs/WHATSAPP.md`).
- No live phone-to-phone Bluetooth relay (the `/mesh` animation is a labelled simulation; it needs a native app).
- No real instruments: sensors are simulated by our script until a partner connects theirs.
- Live speech-to-text and language-model calls need keys; without them every case is still created from word rules.
- Screens are in English; Hindi, Hinglish and Marathi reports are read by rules. Odia, Bengali, Tamil, Telugu and other scripts need the AI keys; without them they still become a case, with no facts read.
- Real place data (gazetteer) exists for Mumbai and Bihar only; elsewhere a case is placed to its district.
