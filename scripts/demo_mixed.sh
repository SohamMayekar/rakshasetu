#!/usr/bin/env bash
# A small MIXED set of simulated incidents, for the universal-dashboard demo: the desk is wiped to reference
# data, then one clearly-simulated report is sent through the REAL public pipeline into each incident — so the
# platform shows different emergency types (flood, cyclone, landslide) in different places, each following the
# same workflow. Everything here is synthetic and the desk labels it so ("simulated demo data").
#
#   make demo-mixed        # wipes to reference data, then sends these through the real pipeline
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
API="${DEMO_LOCAL_URL:-http://localhost:3000}"

uuid() { printf '%s' "$(uuidgen | tr 'A-Z' 'a-z')"; }

say() { printf '%s\n' "$*"; }

send() {  # send <incident> <device> <text>
  local inc="$1" dev="$2" text="$3"
  local body
  body="$(python3 - "$dev" "$inc" "$text" <<'PY'
import json, sys, uuid
dev, inc, text = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({"device_id": dev, "session_id": str(uuid.uuid4()), "incident": inc, "text": text}))
PY
)"
  local out
  out="$(curl -fsS -X POST "$API/v1/public/text-turns" -H 'content-type: application/json' -d "$body")"
  local pid
  pid="$(printf '%s' "$out" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("public_id") or "")')"
  say "  $inc  ${pid:-sent (no id yet)}  $text"
}

say "== one simulated report per incident, through the same public pipeline =="
# The scenario reports are deliberately plain and clearly synthetic; each is a different emergency type.
send MH demo-mixed-flood-01    "Water is rising fast in Kurla West. Six people are stuck on a chawl roof; an elderly man needs medicine."
send OD demo-mixed-cyclone-01  "Cyclone winds have blown the roof off our house in Erasama. Eight people are inside, two are children."
send HP demo-mixed-landslide-01 "A landslide has buried a house near Seraj valley. Four people are trapped under the debris."
send BR demo-mixed-flood-02    "Flood water has entered our village Thawe. Five people are stranded on the roof of our house."

say
say "waiting for the pipeline to file them…"
sleep 8
say "open http://localhost:3000 — All incidents lists every scenario; each desk opens with the same workflow."
say "   Desk (flood · Mumbai):    $API/desk/MH"
say "   Desk (cyclone · Odisha):  $API/desk/OD"
say "   Desk (landslide · HP):    $API/desk/HP"
