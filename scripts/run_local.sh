#!/usr/bin/env bash
# RakshaSetu local runner without Docker.
# Runs PostgreSQL check, API, Worker, Ticker, Web (Next.js), and Caddy reverse proxy.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Starting RakshaSetu (Local - No Docker) ==="

# 1. Check PostgreSQL
if ! pg_isready -h 127.0.0.1 -p 5432 >/dev/null 2>&1; then
    echo "ERROR: PostgreSQL is not accepting connections on 127.0.0.1:5432"
    echo "Please ensure PostgreSQL service is running."
    exit 1
fi
echo "✓ PostgreSQL is ready on 127.0.0.1:5432"

# 2. Check virtualenv and node_modules
if [ ! -f "$ROOT/services/api/.venv/bin/python" ]; then
    echo "ERROR: Python virtualenv not found at services/api/.venv"
    exit 1
fi

if [ ! -d "$ROOT/apps/web/node_modules" ]; then
    echo "ERROR: node_modules not found in apps/web. Run 'npm --prefix apps/web install' first."
    exit 1
fi

# 3. Create required directories
mkdir -p "$ROOT/var/files" "$ROOT/var/logs"

# 4. Load .env if present
if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$ROOT/.env"
    set +a
fi

# 5. Export environment variables
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://rakshasetu_app:${APP_DB_PASSWORD:-rakshasetu-app}@127.0.0.1:5432/rakshasetu}"
export DEMO_OWNER_DATABASE_URL="${DEMO_OWNER_DATABASE_URL:-postgresql+psycopg://rakshasetu_owner:${OWNER_DB_PASSWORD:-rakshasetu-owner}@127.0.0.1:5432/rakshasetu}"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql+psycopg://rakshasetu_app:${APP_DB_PASSWORD:-rakshasetu-app}@127.0.0.1:5432/rakshasetu_test}"
export TEST_OWNER_DATABASE_URL="${TEST_OWNER_DATABASE_URL:-postgresql+psycopg://rakshasetu_owner:${OWNER_DB_PASSWORD:-rakshasetu-owner}@127.0.0.1:5432/rakshasetu_test}"
export DEMO_MODE="${DEMO_MODE:-true}"
export SECRET_KEY="${SECRET_KEY:-dev-only-change-me}"
export PHONE_HASH_KEY="${PHONE_HASH_KEY:-dev-only-phone-hmac-key}"
export PARTNER_DEMO_SECRET="${PARTNER_DEMO_SECRET:-dev-only-partner-secret}"
export DATA_DIR="${ROOT}/data"
export FILES_DIR="${ROOT}/var/files"
export CONTRACTS_DIR="${ROOT}/packages/contracts"
export PYTHONPATH="${ROOT}/services/api"

PY="$ROOT/services/api/.venv/bin/python"
UVICORN="$ROOT/services/api/.venv/bin/uvicorn"

PIDS=()
cleanup() {
    echo ""
    echo "Shutting down RakshaSetu services..."
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" >/dev/null 2>&1; then
            kill "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
    echo "All services stopped."
}
trap cleanup SIGINT SIGTERM EXIT

# 6. Start API (FastAPI) on :8000
echo "Starting API on 127.0.0.1:8000..."
(
    cd "$ROOT/services/api"
    exec "$UVICORN" app.main:app --host 127.0.0.1 --port 8000
) > "$ROOT/var/logs/api.log" 2>&1 &
PIDS+=($!)

# 7. Start Worker
echo "Starting Worker process..."
(
    cd "$ROOT/services/api"
    exec "$PY" -m app.worker
) > "$ROOT/var/logs/worker.log" 2>&1 &
PIDS+=($!)

# 8. Start Ticker
echo "Starting Ticker process..."
(
    cd "$ROOT/services/api"
    exec "$PY" -m app.ticker
) > "$ROOT/var/logs/ticker.log" 2>&1 &
PIDS+=($!)

# 9. Start Web App (Next.js) on :3000
echo "Starting Web app (Next.js) on 127.0.0.1:3000..."
(
    cd "$ROOT/apps/web"
    exec npm run dev
) > "$ROOT/var/logs/web.log" 2>&1 &
PIDS+=($!)

# 10. Start Caddy reverse proxy (:80 and :8080)
echo "Starting Caddy reverse proxy (Local :80, Public :8080)..."
(
    exec caddy run --config "$ROOT/infra/caddy/Caddyfile.local"
) > "$ROOT/var/logs/caddy.log" 2>&1 &
PIDS+=($!)

# Wait for services to be ready
echo "Waiting for services to become healthy..."
until curl -s http://127.0.0.1:8000/healthz >/dev/null 2>&1; do
    sleep 0.5
done
echo "✓ API is healthy at http://127.0.0.1:8000"

until curl -s http://127.0.0.1:80/healthz >/dev/null 2>&1; do
    sleep 0.5
done
echo "✓ Local Caddy listener is healthy at http://localhost (port 80)"

until curl -s http://127.0.0.1:8080/healthz >/dev/null 2>&1; do
    sleep 0.5
done
echo "✓ Public Caddy listener is healthy at http://localhost:8080"

echo ""
echo "=========================================================="
echo " RakshaSetu is running locally!"
echo " - Local Desk (projector / officer): http://localhost"
echo " - Public Portal (reporter / responder): http://localhost:8080"
echo " - Direct Next.js Dev: http://localhost:3000"
echo " - Direct API: http://localhost:8000"
echo " Logs are streaming in var/logs/"
echo " Press Ctrl+C to stop all services."
echo "=========================================================="
echo ""

# Keep running and wait for background processes
wait "${PIDS[0]}"
