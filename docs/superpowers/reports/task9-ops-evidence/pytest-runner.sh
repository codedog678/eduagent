#!/bin/bash
set -u
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
PG=/opt/homebrew/opt/postgresql@16/bin
LABEL="$1"
shift
DB="m3_t9_${LABEL}_$(date +%s)_$$"
EVIDENCE="$ROOT/docs/superpowers/reports/task9-ops-evidence"
mkdir -p "$EVIDENCE"
"$PG/createdb" -h 127.0.0.1 -p 55432 -U postgres "$DB" || exit 2
trap '"$PG/dropdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH="$ROOT/python"
export TZ=UTC
export PYTHONPYCACHEPREFIX="/tmp/m3-task9-pycache"
cd "$ROOT/python" || exit 2
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest "$@" \
  -o cache_dir=/tmp/m3-task9-pytest-cache --junitxml="$EVIDENCE/$LABEL.xml" \
  >"$EVIDENCE/$LABEL.log" 2>&1
RESULT=$?
tail -n 12 "$EVIDENCE/$LABEL.log"
exit "$RESULT"
