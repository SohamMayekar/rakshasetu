"""A SIMULATED partner (PRD §16.1 4:05, "convergence"): our own script playing another team's system, through the
public listener, signed as `demo-partner` ("Demo partner (simulated by RakshaSetu)"). Say so on stage.

    make partner-demo CASE=BR-199          (or the /demo page's "Partner moment")

It sends what a partner would, after receiving our report.created / evidence.created / audit.head:
  1. a priority suggestion for the case (an officer accepts or ignores it on the desk)
  2. a credibility note on the case's first evidence item (a chip on that item; it changes nothing else)
  3. an anchor receipt for our current audit head (Verify then checks our chain against it)
  4. request 1 again with a 15-minute-old timestamp: refused, "401 · Stale timestamp: replay rejected"
Everything shows in the partner log (/partners). The partner's "sensor" and "ledger" are simulated, and say so.
"""

import argparse
import json
import os
import sys
import time
import uuid

import httpx
from sqlalchemy import text

from app.channels.partner import sign
from app.db import get_engine

PARTNER = "demo-partner"


def _send(client: httpx.Client, secret: str, body: dict, ts: int | None = None) -> httpx.Response:
    raw = json.dumps(body, ensure_ascii=False).encode()
    stamp = str(ts if ts is not None else int(time.time()))
    return client.post("/v1/partners/annotations", content=raw, headers={
        "Content-Type": "application/json", "X-RakshaSetu-Partner": PARTNER, "X-RakshaSetu-Timestamp": stamp,
        "X-RakshaSetu-Signature": sign(secret, stamp, raw), "Idempotency-Key": body["idempotency_key"]})


def run(case: str, base: str | None = None, secret: str | None = None) -> list[str]:
    base = base or os.environ.get("PARTNER_DEMO_BASE", "http://caddy:8080")
    secret = secret or os.environ.get("PARTNER_DEMO_SECRET", "")
    if not secret:
        raise RuntimeError("PARTNER_DEMO_SECRET is not set (see .env.example)")
    with get_engine().connect() as c:   # what our evidence.created webhook would have told them
        sha = c.execute(text("SELECT e.sha256 FROM evidence e JOIN cases k ON k.id = e.case_id WHERE k.public_id = :p"
                             " AND e.sha256 IS NOT NULL ORDER BY e.id LIMIT 1"), {"p": case}).scalar()
    out = []
    with httpx.Client(base_url=base, timeout=15) as client:
        suggest = {"idempotency_key": f"demo-{uuid.uuid4()}", "kind": "priority", "target": {"case": case}, "value": "P1",
                   "confidence": 0.78, "explanation": "river overflow: gauge G-03 rising, 3 reports within 1 km (simulated sensor)"}
        r = _send(client, secret, suggest)
        out.append(f"priority suggestion → {r.status_code} {r.json().get('effect', r.text)}")
        if sha:
            r = _send(client, secret, {"idempotency_key": f"demo-{uuid.uuid4()}", "kind": "credibility",
                                       "target": {"evidence_sha256": sha}, "value": "no earlier copy found", "confidence": 0.91,
                                       "explanation": "simulated forensics check"})
            out.append(f"credibility note on {sha[:12]}… → {r.status_code} {r.json().get('effect', r.text)}")
        head = client.get("/v1/audit/head").json()
        r = _send(client, secret, {"idempotency_key": f"demo-{uuid.uuid4()}", "kind": "anchor_receipt",
                                   "target": {"seq": head["seq"], "head_hash": head["hash"]},
                                   "value": f"simulated ledger entry {uuid.uuid4().hex[:8]}"})
        out.append(f"anchor receipt for head #{head['seq']} → {r.status_code} {r.json().get('effect', r.text)}")
        r = _send(client, secret, suggest, ts=int(time.time()) - 900)
        out.append(f"the first request replayed 15 min later → {r.status_code} {r.json().get('detail', r.text)}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--case", required=True)
    args = ap.parse_args()
    try:
        for line in run(args.case):
            print(line)
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
