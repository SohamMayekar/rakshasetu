#!/bin/bash
# Stop the natively running RakshaSetu processes (api, worker, ticker, web).
cd "$(dirname "$0")/.."
for name in api worker ticker web proxy; do
  if [ -f "var/log/$name.pid" ]; then
    pid="$(cat var/log/$name.pid)"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" && echo "$name stopped (pid $pid)"
    else
      echo "$name not running"
    fi
    rm -f "var/log/$name.pid"
  fi
done
# Free the ports even if an earlier orphan survived its parent (e.g. next-server outliving npm).
for port in 3000 3100; do
  for pid in $(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null); do
    kill "$pid" && echo "orphan on :$port stopped (pid $pid)"
  done
done
