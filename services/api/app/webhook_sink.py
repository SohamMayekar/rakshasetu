"""A partner's webhook receiver, in 40 lines: what a partner team runs to hear from us, and what the demo uses to
show signed webhooks arriving (PRD §11.4). It checks the timestamp window and the signature exactly as our own
partner endpoints do, answers 200 once per delivery id (a retry gets 200 again, and nothing new happens), and
prints one line per delivery. Copy it; it is the reference in packages/contracts/PARTNER_CONTRACT.md.

    make webhook-sink        (inside the api container, on :9009; set DEMO_PARTNER_WEBHOOK_URL=http://api:9009/hook)
"""

import hashlib
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SECRET = os.environ.get("PARTNER_DEMO_SECRET", "")
SEEN: set[str] = set()


def verified(headers, raw: bytes) -> str | None:
    """None if the delivery is genuine and fresh, else why not."""
    ts, sig = headers.get("X-RakshaSetu-Timestamp", ""), headers.get("X-RakshaSetu-Signature", "")
    if not ts.isdigit() or abs(time.time() - int(ts)) > 300:
        return "stale or missing timestamp"
    want = "v1=" + hmac.new(SECRET.encode(), ts.encode() + b"." + raw, hashlib.sha256).hexdigest()
    return None if hmac.compare_digest(sig, want) else "bad signature"


class Hook(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802 (http.server's name)
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        why = verified(self.headers, raw)
        if why:
            self.send_response(401); self.end_headers(); self.wfile.write(why.encode())  # noqa: E702
            print(f"refused: {why}", flush=True)
            return
        d = json.loads(raw)
        first = d["id"] not in SEEN
        SEEN.add(d["id"])
        self.send_response(200); self.end_headers()  # noqa: E702
        data = d["data"]
        what = data.get("case") or data.get("seq")
        print(f"{'✓' if first else '↺ repeat'} {d['topic']:<16} {what} · signature ✓ · {d['id'][:8]}", flush=True)

    def log_message(self, *_):   # the line above is the log
        pass


if __name__ == "__main__":
    if not SECRET:
        raise SystemExit("PARTNER_DEMO_SECRET is not set")
    print("listening on :9009/hook (signed RakshaSetu webhooks; Ctrl-C stops)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 9009), Hook).serve_forever()
