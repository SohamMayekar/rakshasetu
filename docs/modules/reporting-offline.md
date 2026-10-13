# reporting and the offline box

- **What it does:** the no-login help page (`/r`) takes voice or text with an optional call-back number; if there is no signal, `lib/reportBox.ts` keeps the request on the phone (IndexedDB) and sends it by itself.
- **Key rule:** the report's own id is its idempotency key, so a retry or the same report arriving by two routes is counted once; the time it was written is kept as a label (`written_at`), never used for timers.
- **Voice:** adaptive silence detection, a clear message for each failure, transcripts cleaned of noise and hallucinations; a clip is always sent and the server decides if it is empty.
- **The relay:** a phone-to-phone Bluetooth relay is *designed* and shown as a labelled simulation at `/mesh`; it needs a native app.
- **Tests:** `tests/test_other_disasters.py` covers reading; the box is exercised by turning on airplane mode on `/r`.
