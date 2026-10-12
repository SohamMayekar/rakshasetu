#!/bin/sh
# Runs once, on the first start of an empty data volume (postgres image convention), as the superuser.
# Two login roles (rule R9):
#   rakshasetu_owner  owns every table and runs migrations (and, in DEMO_MODE only, the demo reset)
#   rakshasetu_app    used by api, worker and ticker; owns nothing; INSERT + SELECT only on `events`
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<SQL
CREATE ROLE rakshasetu_owner LOGIN PASSWORD '${OWNER_DB_PASSWORD}';
CREATE ROLE rakshasetu_app LOGIN PASSWORD '${APP_DB_PASSWORD}';
CREATE DATABASE rakshasetu OWNER rakshasetu_owner;
CREATE DATABASE rakshasetu_test OWNER rakshasetu_owner;
SQL
for db in rakshasetu rakshasetu_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d "$db" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON DATABASE $db FROM PUBLIC;
GRANT CONNECT ON DATABASE $db TO rakshasetu_app;
SQL
done
