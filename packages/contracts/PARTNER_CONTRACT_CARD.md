# RakshaSetu partner contract card (one page)

*For a partner team at CodeAstra 2.0. Integrate in under an hour. Adding you is one row in our `config/partners.yaml` (your id, team name, secret's env var, scopes, subscriptions, incidents, webhook URL's env var, rate cap, `enabled` kill switch), not code. Every example below was run against the stack (m61).*

**What we are:** the district control room's rescue-request desk. Reports become one case per household, with one owner.

## 1. Send us a report → `POST /v1/ingest/reports`
Body: **Canonical Report v1** (`report.v1.schema.json`). If you already extracted fields, put them in `structured` (shape: `extraction.schema.json`, every field with its quote) and we skip our language model. Answer: `202 {"report_id": …, "replay": false}` (stored, with its receipt; read moments later); the same key again: `200`, `"replay": true` and `Idempotent-Replay: true`.

## 2. Tell us something about an existing thing → `POST /v1/partners/annotations`
Body (`annotation.schema.json`): `{"idempotency_key", "kind", "target", "value", "confidence"?, "explanation"?}`. **Our rules decide the effect:**

| `kind` | `target` | what happens on our side |
|---|---|---|
| `priority` | `{"case": "BR-199"}`, value `P1`–`P4` | a card on the case: "*your team* suggests P1 · 0.78 · *your explanation*"; an officer **accepts** (it becomes their call, with your reason) or **ignores** it |
| `credibility` | `{"evidence_sha256": "<sha256 from evidence.created>"}` | a chip on **that evidence item**. It never blocks or delays a dispatch and never lowers a priority |
| `anchor_receipt` | `{"seq": 232, "head_hash": "<hash from audit.head>"}` | our Audit screen shows "✓ Head #232 anchored by *your team*" while our chain still matches, ✗ if it ever doesn't |
| `identity` | — | not yet: `422` |

Answer: `201 {"annotation_id", "kind", "effect"}`. Everything you send is stored, audited and, when it is about a case, kept on that case as hashed evidence.

## 3. Hear from us → webhooks to your URL (signed the same way)
`POST <your URL>` with `X-RakshaSetu-Event: <topic>`, `X-RakshaSetu-Delivery: <id>`, `X-RakshaSetu-Timestamp`, `X-RakshaSetu-Signature`. Body (`webhook.schema.json`): `{"id", "topic", "sent_at", "data"}`.
- `report.created`: a report has been read. Its facts (people, hazards, needs, vulnerable), the case id, status, priority, the place name and the **circle** (`lat`, `lng`, `radius_m`, `confidence`), times. **No phone, no names, no words.**
- `evidence.created`: a **media** item (audio) with `sha256`, `mime` and a `url` that works for **15 minutes**. Text records never leave.
- `case.updated`: a case's state after a change (one per case version). `audit.head`: `{seq, head_hash, at}` every 5 min, also at `GET /v1/audit/head`.
- Answer **2xx** within 5 s. Anything else is retried with backoff (after 2, 4, 8, 16 and 32 s: 6 tries in all), so **dedupe by the delivery id**. You only hear about your incidents, from the moment you are switched on (never a replay of history or a demo reset).
- A receiver in 40 lines that checks all of this: `services/api/app/webhook_sink.py` (`make webhook-sink`).

## Signing (both directions)
- `X-RakshaSetu-Timestamp: <unix seconds>` and `X-RakshaSetu-Signature: v1=<hex HMAC-SHA256(secret, timestamp + "." + raw_body)>`, over the **raw bytes**, compared in constant time. More than **300 s** out of date → `401`.
- Your calls also carry `X-RakshaSetu-Partner: <your id>` and **`Idempotency-Key`** (on annotations it must equal the body's `idempotency_key`). Keys live in your own namespace (`partner:<id>`).
- Each partner has its own secret, scopes and rate cap. **Every call, refused or not, is in our partner log** with the signature result, latency and body hash; a replayed request shows as "401 · Stale timestamp: replay rejected".

```bash
BODY='{"idempotency_key":"ann-0001-'$RANDOM'","kind":"priority","target":{"case":"BR-199"},"value":"P1","confidence":0.78,"explanation":"river gauge G-03 rising (simulated sensor)"}'
KEY=$(printf '%s' "$BODY" | sed 's/.*"idempotency_key":"\([^"]*\)".*/\1/')
TS=$(date +%s)
SIG=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$PARTNER_SECRET" -hex | sed 's/^.* //')
curl -sS https://<public-url>/v1/partners/annotations \
  -H "Content-Type: application/json" -H "Idempotency-Key: $KEY" \
  -H "X-RakshaSetu-Partner: <your-id>" -H "X-RakshaSetu-Timestamp: $TS" -H "X-RakshaSetu-Signature: v1=$SIG" \
  --data-binary "$BODY"
# → {"annotation_id":…,"kind":"priority","effect":"a suggestion an officer accepts or ignores"}
```
A report is the same recipe to `/v1/ingest/reports` with a Canonical Report body, e.g. `{"schema_version":"1","idempotency_key":"inc-19","channel":"partner","incident_hint":"BR","content":{"text":"In Mirganj village, near the station, 5 people are stuck on the roof"},"source":{"system":"<your-id>","ref":"inc-19","simulated":true}}`.

**Simulated data:** if your signals are simulated (no IoT team here), say so (`source.simulated: true`, or in an annotation's `explanation`); we label them on screen. All people and phone numbers in our demo are synthetic.
