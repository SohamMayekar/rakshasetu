"""Surge generator (PRD F-C5): synthetic, PRE-STRUCTURED partner reports at a fixed rate, with deliberate
duplicates, across all three incidents. It exercises ingest, de-duplication and real-time delivery without
calling any language model (the facts arrive structured, with quotes, as a partner system would send them).
Say so on stage.

    make surge                    (50 reports/s for 60 s, from inside the api container)
    python -m app.surge --rate 50 --duration 60 [--base http://caddy:8080]

Each request is HMAC-signed as the `surge-generator` partner (config/partners.yaml) and marked `simulated`, so
it queues in the `surge` lane behind live voice, partners and imports. The script prints client-side latency
(p50/p95/p99); the server's own ingest p95 is on the surge screen (/surge, from /v1/metrics/surge).
It goes through the PUBLIC listener (caddy:8080), the way a partner's system would.
All people and phone numbers are synthetic.
"""

import argparse
import asyncio
import hashlib
import hmac
import json
import os
import random
import statistics
import time
import uuid

import httpx

PARTNER = "surge-generator"

# Real places from the committed BR gazetteer, with a landmark that resolves to a Medium pin there (m31), and
# district-level places for the thin packs (they have no gazetteer: those cases are honest "district only").
BR = [("Kalu Chhapra", "school ke paas", "school"), ("Bhore", "aspatal ke paas", "hospital"),
      ("Katiya", "aspatal ke peeche", "hospital"), ("Barauli", "station ke paas", "railway_station"),
      ("Mirganj", "station ke paas", "railway_station"), ("Kuchaikote", "station ke paas", "railway_station"),
      ("Meera Chhapra", "school ke paas", "school"), ("Hathua", "hospital ke saamne", "hospital"),
      ("Uchkagaon", None, None), ("Dewapur", None, None), ("Nawadah", None, None), ("Nautan", None, None)]
THIN = {"OD": ["Jagatsinghpur", "Kendrapara", "Puri"], "HP": ["Kullu", "Mandi"]}
SITUATIONS = [("trapped_on_roof", "chhat par fase hain"), ("water_entering", "ghar mein paani ghus gaya"),
              ("trapped_inside", "ghar ke andar fase hain"), ("cut_off", "rasta kat gaya hai")]
NEEDS = [("medicine", "dawai chahiye"), ("food", "khana nahi hai"), ("drinking_water", "peene ka paani nahi"), (None, None)]
VULN = [("elderly", "ek buzurg hain"), ("child", "bachche hain"), (None, None), (None, None)]
# Synthetic names (most real reports name the family; a repeat report names the same one). 40 × 12 = 480
# combinations, so two different families in one village sometimes share a name, as they do in life.
GIVEN = ["Ramesh", "Suresh", "Mahesh", "Dinesh", "Rajesh", "Mukesh", "Umesh", "Ganesh", "Rakesh", "Naresh",
         "Sunita", "Anita", "Savita", "Kavita", "Rekha", "Meena", "Geeta", "Seema", "Pooja", "Neha",
         "Ram", "Shyam", "Mohan", "Sohan", "Gopal", "Kishan", "Hari", "Shiv", "Raju", "Bablu",
         "Lalita", "Shanti", "Kamla", "Sarita", "Usha", "Asha", "Radha", "Sita", "Gita", "Manju"]
FAMILY = ["Yadav", "Kumar", "Prasad", "Singh", "Mahto", "Paswan", "Ram", "Sah", "Devi", "Manjhi", "Rai", "Thakur"]


def household(rng: random.Random, n: int) -> dict:
    incident = rng.choices(["BR", "OD", "HP"], weights=[8, 1, 1])[0]
    people = rng.choice([2, 3, 4, 5, 6, 7, 8])
    sit, sit_q = rng.choice(SITUATIONS)
    need, need_q = rng.choice(NEEDS)
    vul, vul_q = rng.choice(VULN)
    name = f"{rng.choice(GIVEN)} {rng.choice(FAMILY)}" if rng.random() < 0.85 else None
    name_q = f"{name} ka parivaar" if name else None
    count_q = f"{people} log"
    if incident == "BR":
        village, lm_q, lm_type = rng.choice(BR)
        lead = f"{village} gaon mein" + (f", {lm_q}" if lm_q else "")
        district = None
    else:
        village, lm_q, lm_type, district = None, None, None, rng.choice(THIN[incident])
        lead = f"{district} zila mein"
    text = ", ".join(x for x in [name_q, lead, f"{count_q} {sit_q}", need_q, vul_q] if x)
    ex = {"language": "hi", "people_count": {"value": people, "kind": "stated", "quote": count_q},
          "hazards": [{"type": sit, "quote": sit_q}],
          "needs": [{"type": need, "quote": need_q}] if need else [],
          "vulnerable": [{"type": vul, "quote": vul_q}] if vul else [],
          "location": {"village_or_locality": {"original": village, "latin": village, "quote": village} if village else None,
                       "district": district, "state": None,
                       "landmarks": [{"type": lm_type, "name": None, "relation": "near", "quote": lm_q}] if lm_type else []},
          "person_names": [{"name": name, "quote": name_q}] if name else [], "callback_phone": None, "reporter_on_site": None}
    return {"incident": incident, "text": text, "structured": ex, "phone": f"+9199{n:08d}"}


def sign(secret: str, ts: str, body: bytes) -> str:
    return "v1=" + hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rate", type=float, default=50, help="reports per second")
    ap.add_argument("--duration", type=float, default=60, help="seconds")
    ap.add_argument("--duplicates", type=float, default=0.2, help="share of reports that repeat an earlier household")
    ap.add_argument("--base", default=os.environ.get("SURGE_BASE", "http://caddy:8080"), help="the public listener")
    ap.add_argument("--secret", default=os.environ.get("PARTNER_DEMO_SECRET"))
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    if not args.secret:
        raise SystemExit("PARTNER_DEMO_SECRET is not set (see .env.example)")
    rng = random.Random(args.seed if args.seed is not None else time.time_ns())
    run = uuid.uuid4().hex[:8]
    seen: list[dict] = []
    lat: list[float] = []
    codes: dict[int, int] = {}
    total = int(args.rate * args.duration)

    async with httpx.AsyncClient(base_url=args.base, timeout=10, limits=httpx.Limits(max_connections=200)) as client:
        async def one(i: int) -> None:
            if seen and rng.random() < args.duplicates:
                h = rng.choice(seen)                    # the same household, reported again by another source
            else:
                h = household(rng, rng.randrange(10**8))
                seen.append(h)
            key = f"surge-{run}-{i}"
            body = json.dumps({"schema_version": "1", "idempotency_key": key, "channel": "partner",
                               "incident_hint": h["incident"], "reporter": {"phone": h["phone"], "relation": "unknown"},
                               "content": {"text": h["text"], "language": "hi"}, "structured": h["structured"],
                               "source": {"system": "surge.py", "simulated": True}}, ensure_ascii=False).encode()
            ts = str(int(time.time()))
            t0 = time.perf_counter()
            try:
                r = await client.post("/v1/ingest/reports", content=body, headers={
                    "Content-Type": "application/json", "Idempotency-Key": key, "X-RakshaSetu-Partner": PARTNER,
                    "X-RakshaSetu-Timestamp": ts, "X-RakshaSetu-Signature": sign(args.secret, ts, body)})
                codes[r.status_code] = codes.get(r.status_code, 0) + 1
                if r.status_code < 400:
                    lat.append((time.perf_counter() - t0) * 1000)
            except httpx.HTTPError:
                codes[0] = codes.get(0, 0) + 1

        start = time.perf_counter()
        tasks = []
        for i in range(total):   # paced: request i leaves at start + i / rate
            delay = start + i / args.rate - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            tasks.append(asyncio.create_task(one(i)))
        await asyncio.gather(*tasks)
        took = time.perf_counter() - start

    lat.sort()
    q = statistics.quantiles(lat, n=100) if len(lat) >= 2 else [0] * 99
    print(json.dumps({"sent": total, "seconds": round(took, 1), "per_second": round(total / took, 1),
                      "status_codes": codes, "accepted": len(lat), "households": len(seen),
                      "client_p50_ms": round(q[49], 1), "client_p95_ms": round(q[94], 1), "client_p99_ms": round(q[98], 1)},
                     indent=2))


if __name__ == "__main__":
    asyncio.run(main())
