#!/bin/bash
set -eu
OWN=/tmp/m3-task9-spec-feca62c7-189a-4708-b334-5456f6d79d93
PY=/tmp/eduagent-m3-patched-runtime/bin/python
PG=/opt/homebrew/opt/postgresql@16/bin
SCENARIO="$1"
DB="m3_t9_spec_$(uuidgen | tr -d '-' | tr '[:upper:]' '[:lower:]')"
"$PG/createdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
printf '%s\n' "$DB" > "$OWN/live-$SCENARIO-db.txt"
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
unset DATABASE_URL
export PYTHONPATH="/Users/bytedance/Documents/trae_projects/eduagent-m3/python:$OWN"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$OWN/pycache"
export TMPDIR="$OWN/tmp"
export TZ=UTC
export SPEC_SCENARIO="$SCENARIO"
cleanup() {
  if [ -n "${CHILD:-}" ]; then
    kill -TERM "$CHILD" 2>/dev/null || true
    wait "$CHILD" || true
  fi
  "$PG/dropdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
  printf 'dropped %s\n' "$DB" > "$OWN/live-$SCENARIO-cleanup.txt"
}
trap cleanup EXIT
trap 'exit 143' TERM INT
"$PY" "$OWN/live_server.py" > "$OWN/live-$SCENARIO.log" 2>&1 &
CHILD=$!
printf '%s\n' "$CHILD" > "$OWN/live-$SCENARIO-pid.txt"
wait "$CHILD"
