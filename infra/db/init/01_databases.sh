#!/bin/sh
# Runs once, on the first start of an empty data volume (postgres image convention).
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<SQL
CREATE DATABASE rakshasetu;
CREATE DATABASE rakshasetu_test;
SQL
for db in rakshasetu rakshasetu_test; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" -d "$db" <<SQL
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL
done
