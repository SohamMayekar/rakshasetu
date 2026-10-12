# RakshaSetu partner contract card (one page)

*For a partner team at CodeAstra 2.0. Integrate in under an hour. Adding you is one row in our `config/partners.yaml`, not code.*

**What we are:** the district control room's rescue-request desk. Reports become one case per household, with one owner.

## 1. Send us a report → `POST /v1/ingest/reports`
Body: **Canonical Report v1** (`report.v1.schema.json`). If you already extracted fields, put them in `structured` (shape: `extraction.schema.json`, every field with its quote) and we skip our language model.

## 2. Tell us something about an existing thing → `POST /v1/partners/annotations`
`kind` is one of `credibility` (about one evidence item) · `priority` (a suggestion an officer accepts or ignores) · `identity` · `anchor_receipt` (you countersigned our audit head). **Our rules decide the effect.** A credibility mark never blocks or delays a dispatch and never lowers priority.

## 3. Subscribe to our webhooks (we sign them the same way)
`report.created` (structured fields, pin, radius, time: **no phone, no names**) · `evidence.created` (15-minute signed URL) · `case.updated` · `audit.head` (`{seq, hash, at}`, also at `GET /v1/audit/head`).

## Signing (both directions)
- Headers: `X-RakshaSetu-Timestamp: <unix seconds>` and `X-RakshaSetu-Signature: v1=<hex HMAC-SHA256(secret, timestamp + "." + raw_body)>`
- Computed over the **raw bytes** of the body; compared in constant time.
- Requests more than **300 s** out of date are rejected (401).
- **`Idempotency-Key` header is required on every POST.** A replay returns the original result with `Idempotent-Replay: true`. Your keys live in your own namespace (`partner:<id>`), so they can't collide with anyone else's.
- Each partner has its own secret, scopes and rate cap, and a kill switch.

```bash
BODY='{"schema_version":"1","idempotency_key":"inc_19","channel":"partner","incident_hint":"BR","content":{"text":"6 log chhat par, Benibad"},"source":{"system":"team-ai1","ref":"inc_19","simulated":false}}'
TS=$(date +%s)
SIG=$(printf '%s.%s' "$TS" "$BODY" | openssl dgst -sha256 -hmac "$PARTNER_SECRET" -hex | sed 's/^.* //')
curl -sS https://<public-url>/v1/ingest/reports \
  -H "Content-Type: application/json" -H "Idempotency-Key: inc_19" \
  -H "X-RakshaSetu-Partner: team-ai1" -H "X-RakshaSetu-Timestamp: $TS" -H "X-RakshaSetu-Signature: v1=$SIG" \
  --data-binary "$BODY"
```

**Simulated data:** if your signals are simulated (no IoT team here), set `source.simulated: true`; we label them on screen.
