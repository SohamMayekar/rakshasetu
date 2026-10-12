# Real-time events (PRD §11.3)

Every event a screen receives is a row of the hash-chained `events` table (rule R1). Nothing reaches a screen unless it is in the audit chain.

**Transport:** `WS /v1/ws?incident=<code>&since=<seq>` (desk and responder) · `GET /v1/events?since=<seq>` (backfill and polling fallback). Ping every 25 s. Reconnect with the last `seq` you saw.

**Envelope**

```json
{"seq": 1284, "type": "case.updated", "incident_id": 1, "at": "2026-10-12T16:25:00+05:30", "data": {"case_id": 214}}
```

**Control messages** (not events, no `data`): `hello` (subscribed; `seq` is your cursor) · `ping` (every 25 s) · `reset` (the log was reset by a demo reset or a reseed and restarted from a new genesis; your cursor no longer means anything: reload from scratch).

Phone numbers are always masked (`98xxxxxx21`). Events are filtered per subscriber by the same `Scope` the REST API uses: a team lead receives only events about cases its team holds and its own team.

| Area | Types |
|---|---|
| Reports | `report.received` · `report.needs_review` |
| Cases | `case.created` · `case.updated` · `case.merged` · `case.unmerged` · `merge.suggested` · `merge.refused` |
| Assignments | `assignment.created` · `assignment.acknowledged` · `assignment.contact` · `assignment.overdue` · `assignment.reassigned` · `assignment.released` · `team.status` |
| Escalation and rescues | `escalation.raised` · `escalation.acked` · `rescue.recorded` · `rescue.partial` · `rescue.confirmed` · `rescue.disputed` |
| Imports | `import.uploaded` · `import.mapped` · `import.progress` (about once a second, with the counts) · `import.completed` (with the summary line) |
| Chain | `chain.genesis` (a demo reset starts a new chain) |
| Computed (not stored) | `metrics.promises` every 2 s |

`case.updated` is coalesced to at most one per case per second on the wire; clients batch renders into 1-second frames (F-C5).
