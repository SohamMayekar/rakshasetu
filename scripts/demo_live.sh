#!/usr/bin/env bash
# Run RakshaSetu with live provider keys and perform the whole demonstration through the real API.
#
#   make demo-live GROQ_API_KEY=gsk_…                  # one key: Groq is the STT fallback + the LLM primary
#   make demo-live SARVAM_API_KEY=… GROQ_API_KEY=…     # the full chain: Sarvam → Groq (speech), Groq → Gemini (facts)
#   ./scripts/demo_live.sh --scene son                 # stop at a reset point (son|merge|sheet|stale|rescue|receipts)
#
# In order:
#   1. saves any *_API_KEY given here into .env (the file every process reads; values are never echoed)
#   2. starts the native stack (api, worker, ticker, web, proxy) or restarts it when a key changed
#   3. provider-check: one tiny live call per provider whose key is set (OK / BLOCKED / FAILED)
#   4. plays the demonstration: app.modules.demo.scenes --scene receipts — every step of docs/DEMO.md through
#      the same API the app uses, so the clip goes to the real speech-to-text and the reports to the real
#      language model when the keys are there. It re-seeds the demo database, so the previous state is wiped
#      (that is what a reset is; the honesty rules: say so once if an audience is watching).
#   5. prints the receipts: which reports a provider read and which the word rules did
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SCENE=receipts
while [ $# -gt 0 ]; do
  case "$1" in
    --scene) SCENE="${2:?--scene needs one of: son, merge, sheet, stale, rescue, receipts}"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1 (try --scene <id>)" >&2; exit 2 ;;
  esac
done

PY="$ROOT/services/api/.venv/bin/python"
[ -x "$PY" ] || { echo "no venv at services/api/.venv (see native/README.md, one-time setup)" >&2; exit 1; }
[ -f .env ] || { cp .env.example .env && echo "created .env from .env.example"; }

# ---- the keys ------------------------------------------------------------------------------------------------
changed=0
for name in SARVAM_API_KEY GROQ_API_KEY GEMINI_API_KEY GOOGLE_MAPS_API_KEY; do
  value="$(printf '%s' "${!name:-}" | tr -d '[:space:]')"
  [ -n "$value" ] || continue
  case "$value" in *"#"*) echo "$name contains '#': .env values can't carry an inline comment" >&2; exit 2 ;; esac
  if [ "$(sed -n "s/^$name=//p" .env | tail -1)" = "$value" ]; then
    echo "· $name already in .env"
    continue
  fi
  # One line, replaced in place (or appended): Compose and every native process read this file.
  awk -v n="$name" -v v="$value" '$0 ~ "^" n "=" { print n "=" v; seen = 1; next } { print } END { if (!seen) print n "=" v }' \
    .env > .env.new && mv .env.new .env
  echo "✓ $name saved to .env (${#value} characters)"
  changed=1
done

keys=0
for name in SARVAM_API_KEY GROQ_API_KEY GEMINI_API_KEY GOOGLE_MAPS_API_KEY; do
  if [ -n "$(sed -n "s/^$name=//p" .env | tail -1)" ]; then keys=$((keys + 1)); fi
done
if [ "$keys" = 0 ]; then
  echo
  echo "!! no provider keys: the demonstration will run the no-key fallback (recorded transcript + word rules)."
  echo "   add one:  make demo-live GROQ_API_KEY=gsk_…"
fi

# ---- the stack -----------------------------------------------------------------------------------------------
if command -v docker >/dev/null && docker ps --format '{{.Names}}' 2>/dev/null | grep -q rakshasetu; then
  echo "the Docker stack is running: 'make down' first — this runner runs the native processes" >&2
  exit 1
fi

running() {
  local n
  for n in api worker ticker web proxy; do
    [ -f "var/log/$n.pid" ] && kill -0 "$(cat "var/log/$n.pid")" 2>/dev/null && return 0
  done
  return 1
}

# A running stack keeps the environment it was started with: if .env's keys changed since, the api and the
# worker would keep the old ones, so every process restarts. A fingerprint of the three values decides.
fingerprint() {
  { for n in SARVAM_API_KEY GROQ_API_KEY GEMINI_API_KEY GOOGLE_MAPS_API_KEY; do
      printf '%s=%s\n' "$n" "$(sed -n "s/^$n=//p" .env | tail -1)"
    done; } | shasum -a 256 | cut -d' ' -f1
}
FP="$(fingerprint)"

if running && { [ "$changed" = 1 ] || [ "$(cat var/log/demo_live.fingerprint 2>/dev/null)" != "$FP" ]; }; then
  echo "· the keys changed since the stack started: restarting it so every process sees them"
  ./native/stop.sh || true   # a kill race at shutdown is harmless; the health check below is the real gate
  for _ in $(seq 1 40); do   # let the port come free before uvicorn binds it again
    curl -fsS -o /dev/null --max-time 1 http://127.0.0.1:8000/healthz 2>/dev/null || break
    sleep 0.25
  done
fi
if ! running; then
  echo "== starting the native stack =="
  ./native/start.sh
fi

echo "· waiting for the api and the local proxy"
up=0
for _ in $(seq 1 120); do
  if curl -fsS -o /dev/null --max-time 2 http://127.0.0.1:8000/healthz 2>/dev/null \
  && curl -fsS -o /dev/null --max-time 2 http://127.0.0.1:3000/healthz 2>/dev/null; then up=1; break; fi
  sleep 0.5
done
if [ "$up" != 1 ]; then
  echo "the stack did not answer on :8000/:3000 — see var/log/{api,web,proxy}.log" >&2
  exit 1
fi
echo "✓ api :8000 and the local proxy :3000 answer"
printf '%s\n' "$FP" > var/log/demo_live.fingerprint   # these keys are the ones the running stack sees

# ---- one live call per provider ------------------------------------------------------------------------------
echo
echo "== provider check: one tiny live call per provider whose key is set =="
( source "$ROOT/native/env.sh"; cd "$ROOT/services/api"; "$PY" -m app.providers.check )

# ---- the demonstration ---------------------------------------------------------------------------------------
echo
echo "== the demonstration: docs/DEMO.md through the real API (scene: $SCENE) =="
echo "   re-seeding the demo database, then replaying the steps before '$SCENE'…"
SCENES_OUT="$( source "$ROOT/native/env.sh"; cd "$ROOT/services/api"
  DEMO_LOCAL_URL="${DEMO_LOCAL_URL:-http://localhost:3000}" "$PY" -m app.modules.demo.scenes --scene "$SCENE" )"
printf '%s\n' "$SCENES_OUT"
SON_CASE="$(printf '%s' "$SCENES_OUT" | sed -n "s/.*'son_case': '\([A-Za-z0-9-]*\)'.*/\1/p")"

# ---- what read what ------------------------------------------------------------------------------------------
echo
if [ -n "$SON_CASE" ]; then
  ( source "$ROOT/native/env.sh"; cd "$ROOT/services/api"
    "$PY" "$ROOT/scripts/demo_receipts.py" --case "$SON_CASE" )   # the son's case, even if a caller tested too
else
  ( source "$ROOT/native/env.sh"; cd "$ROOT/services/api"; "$PY" "$ROOT/scripts/demo_receipts.py" )
fi

cat <<'EOF'

------------------------------------------------------------------------------------------------
 the stack is still running — open the app:
   desk       http://localhost:3000         sign in as the Duty officer (spatil / rakshasetu)
   reporter   http://localhost:3000/r        the public phone page
   responder  http://localhost:3000/responder   sign in as the team lead (fb5 / rakshasetu)
 "Timeline & evidence" on a case names the provider that read the words, exactly like the receipts above.
 stop everything:  native/stop.sh
------------------------------------------------------------------------------------------------
EOF
