#!/usr/bin/env bash
# Checks the two Caddy listeners from outside (rule R18). Exit code 1 on the first surprise.
set -u
L=${LOCAL_URL:-http://127.0.0.1:${LOCAL_PORT:-80}}
P=${PUBLIC_URL_LOCAL:-http://127.0.0.1:${PUBLIC_PORT:-8080}}
fail=0
check() { # name expected-status url [curl args...]
  local name=$1 want=$2 url=$3; shift 3
  local got; got=$(curl -s -o /dev/null -w '%{http_code}' "$@" "$url")
  if [ "$got" = "$want" ]; then echo "ok   $name ($got)"; else echo "FAIL $name: wanted $want, got $got"; fail=1; fi
}
check "local: web app"                      200 "$L/"
check "local: api health"                   200 "$L/healthz"
check "local: demo status"                  200 "$L/v1/demo/status"
check "local: demo refused via tunnel hdr"  403 "$L/v1/demo/status" -H "CF-Connecting-IP: 203.0.113.9"
check "public: api health"                  200 "$P/healthz"
check "public: demo route absent"           404 "$P/v1/demo/status"
check "public: spoofed listener header"     404 "$P/v1/demo/status" -H "X-RS-Listener: local"
check "public: desk page absent"            404 "$P/"
check "public: body cap (3 MB)"             413 "$P/v1/ingest/reports" -X POST --data-binary @<(head -c 3000000 /dev/zero)
exit $fail
