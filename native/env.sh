#!/bin/bash
# Native (no-Docker) environment for RakshaSetu on this laptop.
# Sources the repo .env (shared secrets) and overrides the compose-only values:
# everything connects to the local Homebrew Postgres 17 on localhost:5432.

if [ -f "./.env" ]; then ROOT="$PWD"; else ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"; fi
cd "$ROOT"

set -a
source "$ROOT/.env"
set +a

export DATABASE_URL="postgresql+psycopg://rakshasetu_app:${APP_DB_PASSWORD:-rakshasetu-app}@localhost:5432/rakshasetu"
export OWNER_DATABASE_URL="postgresql+psycopg://rakshasetu_owner:${OWNER_DB_PASSWORD:-rakshasetu-owner}@localhost:5432/rakshasetu"
export DEMO_OWNER_DATABASE_URL="$OWNER_DATABASE_URL"
export TEST_DATABASE_URL="postgresql+psycopg://rakshasetu_app:${APP_DB_PASSWORD:-rakshasetu-app}@localhost:5432/rakshasetu_test"
export TEST_OWNER_DATABASE_URL="postgresql+psycopg://rakshasetu_owner:${OWNER_DB_PASSWORD:-rakshasetu-owner}@localhost:5432/rakshasetu_test"
export DEMO_MODE="${DEMO_MODE:-true}"
export API_ORIGIN="http://localhost:8000"

export ROOT
