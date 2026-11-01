#!/bin/bash
set -eu
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
OWN=/tmp/m3-task9-gate-order-fix
EVIDENCE="$ROOT/docs/superpowers/reports/task9-gate-order-fix-evidence"
PG=/opt/homebrew/opt/postgresql@16/bin
PY=/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python
LABEL="$1"
shift
DB="m3_t9_fix_${LABEL}_$(date +%s)_$$_${RANDOM}"
mkdir -p "$OWN"
export PYTHONPYCACHEPREFIX="$OWN/pycache"
"$PY" "$EVIDENCE/provenance.py" snapshot "$LABEL-before"
"$PG/createdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
cleanup() {
  "$PG/dropdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
  "$PY" "$EVIDENCE/provenance.py" snapshot "$LABEL-after"
}
trap cleanup EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH="$ROOT/python"
export TZ=UTC
cd "$ROOT/python"
set +e
"$PY" -m pytest "$@" -o cache_dir="$OWN/pytest-cache" \
  --junitxml="$EVIDENCE/$LABEL.xml" >"$EVIDENCE/$LABEL.log" 2>&1
RESULT=$?
tail -n 24 "$EVIDENCE/$LABEL.log"
exit "$RESULT"
