#!/bin/bash
set -eu
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
OWN=/tmp/m3-task9-gate-order-fix
EVIDENCE="$ROOT/docs/superpowers/reports/task9-gate-order-fix-evidence"
PG=/opt/homebrew/opt/postgresql@16/bin
PY=/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python
export FIX_GATE_STATUS="$1"
DB="m3_t9_fix_live_${FIX_GATE_STATUS}_$(date +%s)_$$_${RANDOM}"
export PYTHONPYCACHEPREFIX="$OWN/pycache"
"$PY" "$EVIDENCE/provenance.py" snapshot "live-server-$FIX_GATE_STATUS-before"
"$PG/createdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
PID=
cleanup() {
  if [ -n "$PID" ]; then
    kill -TERM "$PID" 2>/dev/null || true
    wait "$PID" || true
  fi
  "$PG/dropdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
  "$PY" "$EVIDENCE/provenance.py" snapshot "live-server-$FIX_GATE_STATUS-after"
}
trap cleanup EXIT
trap 'exit 143' TERM INT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export PYTHONPATH="$ROOT/python"
export TZ=UTC
"$PY" "$EVIDENCE/live-server.py" >"$EVIDENCE/live-server-$FIX_GATE_STATUS.log" 2>&1 &
PID=$!
printf '%s\n' "$$" >"$OWN/live-runner.pid"
wait "$PID"
