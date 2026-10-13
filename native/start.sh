#!/bin/bash
# Start the RakshaSetu stack natively: api (:8000), worker, ticker, web (:3000).
# Logs land in var/log/. Stop with native/stop.sh. Database: local Postgres (brew services).
set -euo pipefail
cd "$(dirname "$0")/.."
source native/env.sh

mkdir -p "$ROOT/var/log" "$ROOT/var/files"
BIN="$ROOT/services/api/.venv/bin"

echo "== migrations =="
( cd "$ROOT/services/api" && "$BIN/python" -m app.migrate ) || true

start() {  # start <name> <cwd> <command...>
  local name="$1" dir="$2"; shift 2
  if [ -f "$ROOT/var/log/$name.pid" ] && kill -0 "$(cat "$ROOT/var/log/$name.pid")" 2>/dev/null; then
    echo "$name already running (pid $(cat "$ROOT/var/log/$name.pid"))"
    return
  fi
  # exec so the captured pid is the real process, not the wrapper shell
  ( cd "$dir" && exec nohup "$@" >>"$ROOT/var/log/$name.log" 2>&1 ) &
  echo $! >"$ROOT/var/log/$name.pid"
  echo "$name started (pid $(cat "$ROOT/var/log/$name.pid"))"
}

start api    "$ROOT/services/api" "$BIN/uvicorn" app.main:app --host 127.0.0.1 --port 8000
start worker "$ROOT/services/api" "$BIN/python" -m app.worker
start ticker "$ROOT/services/api" "$BIN/python" -m app.ticker

if [ -f "$ROOT/var/log/web.pid" ] && kill -0 "$(cat "$ROOT/var/log/web.pid")" 2>/dev/null; then
  echo "web already running (pid $(cat "$ROOT/var/log/web.pid"))"
else
  if [ ! -f "$ROOT/apps/web/.next/BUILD_ID" ]; then
    echo "== building web (first run or build missing) =="
    ( cd "$ROOT/apps/web" && npm run build ) >>"$ROOT/var/log/web.log" 2>&1
  fi
  if [ -f "$ROOT/apps/web/.next/standalone/server.js" ]; then
    # The build is "output: standalone" (the config's Docker setting): `next start` serves nothing useful for
    # it, so its own server.js runs instead — with .next/static and public copied inside, as Next asks.
    ( cd "$ROOT/apps/web"
      [ -d .next/standalone/.next/static ] || cp -R .next/static .next/standalone/.next/static
      [ -d .next/standalone/public ] || { [ -d public ] && cp -R public .next/standalone/public; } )
    start web "$ROOT/apps/web" env PORT=3100 HOSTNAME=127.0.0.1 node .next/standalone/server.js
  else
    start web "$ROOT/apps/web" npx next start -p 3100
  fi
fi

start proxy "$ROOT" node "$ROOT/native/proxy.mjs"

echo
echo "api  http://localhost:8000/healthz"
echo "web  http://localhost:3000  (proxy → dashboard; Next itself on :3100)"
echo "logs: var/log/{api,worker,ticker,web,proxy}.log"
