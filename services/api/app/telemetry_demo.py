"""A SIMULATED partner's instruments (the brief's "IoT supplies live telemetry"): our own script playing a sensor
network, signed as `demo-partner`, through the public listener. Every sensor it creates is labelled Simulated
on the desk. It is not a real instrument and must be called what it is.

    make telemetry-demo                 (or: python -m app.telemetry_demo --ticks 20 --every 2)

Each sensor rises through its "rising" line and then its "danger" line, so the desk shows the state change
land on the audit trail. Re-running it only adds newer readings.
"""

import argparse
import json
import os
import sys
import time
import uuid

import httpx

from app.channels.partner import sign

PARTNER = "demo-partner"

# (incident, code, name, kind, unit, lat, lng, warn_at, danger_at, start, end)
SENSORS = [
    ("MH", "MH-G1", "River gauge, Kurla (simulated)", "water_level", "m", 19.0726, 72.8845, 3.0, 3.8, 1.8, 4.2),
    ("MH", "MH-R1", "Rain gauge, Bandra (simulated)", "rainfall", "mm/h", 19.0596, 72.8295, 40, 65, 12, 72),
    ("BR", "BR-G1", "Gandak gauge, Gopalganj (simulated)", "water_level", "m", 26.47, 84.44, 3.5, 4.2, 2.4, 4.6),
    ("OD", "OD-W1", "Wind sensor, Erasama (simulated)", "wind", "km/h", 20.2, 86.4, 90, 120, 40, 130),
    ("HP", "HP-G1", "Beas gauge, Kullu (simulated)", "water_level", "m", 31.96, 77.11, 2.8, 3.4, 1.5, 3.6),
]


def _send(client: httpx.Client, secret: str, body: dict) -> httpx.Response:
    raw = json.dumps(body, ensure_ascii=False).encode()
    stamp = str(int(time.time()))
    return client.post("/v1/ingest/telemetry", content=raw, headers={
        "Content-Type": "application/json", "X-RakshaSetu-Partner": PARTNER, "X-RakshaSetu-Timestamp": stamp,
        "X-RakshaSetu-Signature": sign(secret, stamp, raw), "Idempotency-Key": body["idempotency_key"]})


def run(ticks: int = 12, every: float = 2.0, base: str | None = None, secret: str | None = None) -> list[str]:
    base = base or os.environ.get("PARTNER_DEMO_BASE", "http://caddy:8080")
    secret = secret or os.environ.get("PARTNER_DEMO_SECRET", "")
    if not secret:
        raise RuntimeError("PARTNER_DEMO_SECRET is not set (see .env.example)")
    out: list[str] = []
    skipped: set[str] = set()
    with httpx.Client(base_url=base, timeout=15) as client:
        for t in range(ticks):
            for inc, code, name, kind, unit, lat, lng, warn, danger, start, end in SENSORS:
                if inc in skipped:
                    continue
                value = round(start + (end - start) * (t / max(1, ticks - 1)), 2)
                r = _send(client, secret, {
                    "idempotency_key": f"telemetry-{uuid.uuid4()}", "incident": inc, "simulated": True, "value": value,
                    "sensor": {"code": code, "name": name, "kind": kind, "unit": unit, "lat": lat, "lng": lng,
                               "warn_at": warn, "danger_at": danger}})
                if r.status_code == 404:   # that scenario isn't loaded here
                    skipped.add(inc)
                    out.append(f"{inc}: no such incident, skipped")
                elif r.status_code >= 400:
                    out.append(f"{code} → {r.status_code} {r.text[:120]}")
                else:
                    out.append(f"{code} {value} {unit} → {r.json().get('state')}")
            if t < ticks - 1:
                time.sleep(every)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticks", type=int, default=12)
    ap.add_argument("--every", type=float, default=2.0)
    args = ap.parse_args()
    try:
        for line in run(args.ticks, args.every):
            print(line)
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
