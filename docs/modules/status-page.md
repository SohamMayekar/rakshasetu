# status page · /s/<case id> (public listener)

- **What it does:** shows anyone with the case number one of four steps (Registered → Help assigned → Team reached → Rescued) and when it last changed. It polls `GET /v1/public/cases/{id}/status` every 3 s; no WebSocket through the tunnel.
- **Key data:** `cases.status` mapped to a step; the time of the last step-changing event in `events`.
- **The tricky rule:** it shows **nothing personal or operational**: no names, numbers (not even masked), location, priority, escalation or ETA (an API test checks the body). It says "Help assigned", never that help is on its way, because we don't know a boat is moving. When a team goes quiet the page doesn't change; only "last update" ages. A merged report shows "tracked as BR-214, together with N other reports".
- **Abuse:** lookups are rate-limited per caller (60 a minute; behind the tunnel the key is Cloudflare's client IP header).
- **How to show it:** open the link from the reporter page; assign a team on the desk and watch the step change within 3 s.
