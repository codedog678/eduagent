#!/bin/bash
set -eu
OWN=/tmp/m3-task9-code-20261102-5TNycP
PY=/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python
PG=/opt/homebrew/opt/postgresql@16/bin
DB="m3_t9_code_live_$(date +%s)_$$_${RANDOM}"
export PYTHONPATH="/Users/bytedance/Documents/trae_projects/eduagent-m3/python:$OWN"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$OWN/pycache"
export TMPDIR="$OWN/tmp"
export REVIEW_OWN="$OWN"
export TZ=UTC
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
"$PY" "$OWN/snapshot.py" live-before > "$OWN/live-before.log"
"$PG/createdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
cleanup() {
  "$PG/dropdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
  printf 'dropped %s\n' "$DB" > "$OWN/live-cleanup.log"
  "$PY" "$OWN/snapshot.py" live-after > "$OWN/live-after.log"
}
trap cleanup EXIT
"$PY" "$OWN/live_server.py" > "$OWN/live-server.log" 2>&1 &
PID=$!
stop() { kill -TERM "$PID" 2>/dev/null || true; }
trap stop TERM INT
printf '%s\n' "$PID" > "$OWN/live.pid"
set +e
wait "$PID"
RESULT=$?
if kill -0 "$PID" 2>/dev/null; then
  wait "$PID"
  RESULT=$?
fi
exit "$RESULT"
