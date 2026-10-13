#!/usr/bin/env bash
# The `api`, `worker` and `ticker` processes in ONE container, for Render's free plan.
#
# On a laptop they are three compose services (infra/docker-compose.yml) so a long import or a slow
# language-model call can never delay an escalation. Render has no free background workers, so on
# Render all three run here: migrations first, then the two loops in the background, then uvicorn in
# the foreground. Same code, same processes, one container.
#
# If any one of the three dies, this script stops the other two and exits, so Render restarts the
# service instead of leaving a half-dead box (a silent worker would leave reports unread).
set -euo pipefail

cd "$(dirname "$0")"

echo "migrate: applying migrations as the owner role"
python -m app.migrate

echo "worker + ticker: starting"
python -m app.worker &
worker=$!
python -m app.ticker &
ticker=$!

echo "api: uvicorn on 0.0.0.0:${PORT:-8000}"
uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --no-access-log &
api=$!

trap 'kill "$worker" "$ticker" "$api" 2>/dev/null || true' TERM INT

# First one to exit ends the container.
wait -n "$worker" "$ticker" "$api"
echo "a process exited: stopping the container so Render restarts it"
kill "$worker" "$ticker" "$api" 2>/dev/null || true
exit 1
