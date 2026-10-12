# realtime · one LISTEN, many screens

- **What it does:** the API holds one `LISTEN ev` connection (`app/modules/realtime/hub.py`). Each NOTIFY carries only a seq; the hub reads `events WHERE seq > cursor` and sends each envelope `{seq, type, incident_id, at, data}` to every WebSocket subscriber allowed to see it.
- **Key table:** `events` (the same rows as the audit trail: nothing reaches a screen unless it is in the chain).
- **The tricky rule:** a subscriber is registered first, back-filled from the table, then caught up again before going live, so a reconnect with `?since=<last seq>` loses nothing. `case.updated` is coalesced to one per case per second.
- **Fallback:** `GET /v1/events?since=` returns the same envelopes (polling, and the status page's model). A 25 s ping keeps tunnels from closing idle sockets.
- **How to show it:** open the desk twice, act in one; or `websocat ws://localhost/v1/ws?since=0` and run `make seed`.
