#!/bin/bash
set -eu
OWN=/tmp/m3-task9-health-fix-20261102-xtfx61
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
PY=/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python
PG=/opt/homebrew/opt/postgresql@16/bin
LABEL="$1"
shift
DB="m3_t9_hfix_${LABEL}_$(date +%s)_$$_${RANDOM}"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPYCACHEPREFIX="$OWN/pycache"
export TMPDIR="$OWN/tmp"
mkdir -p "$TMPDIR"
"$PY" "$OWN/snapshot.py" "$LABEL-before" > "$OWN/$LABEL-before.log"
"$PG/createdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
cleanup() {
  "$PG/dropdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
  printf 'dropped %s\n' "$DB" > "$OWN/$LABEL-cleanup.log"
  "$PY" "$OWN/snapshot.py" "$LABEL-after" > "$OWN/$LABEL-after.log"
}
trap cleanup EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH="$ROOT/python:$OWN"
export TZ=UTC
export REVIEW_OWN="$OWN"
set +e
"$PY" -m pytest "$@" -p safety -o cache_dir="$OWN/pytest-cache/$LABEL" \
  --basetemp="$OWN/tmp/$LABEL" --junitxml="$OWN/$LABEL.xml" > "$OWN/$LABEL.log" 2>&1
RESULT=$?
tail -n 30 "$OWN/$LABEL.log"
exit "$RESULT"
