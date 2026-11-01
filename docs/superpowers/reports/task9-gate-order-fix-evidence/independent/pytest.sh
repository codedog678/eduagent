#!/bin/bash
set -eu
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
OWN=/tmp/m3-task9-spec-independent
PG=/opt/homebrew/opt/postgresql@16/bin
LABEL="$1"
shift
DB="m3_t9_spec_${LABEL}_$(date +%s)_$$_${RANDOM}"
mkdir -p "$OWN"
"$PG/createdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
trap '"$PG/dropdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH="$ROOT/python"
export TZ=UTC
export PYTHONPYCACHEPREFIX="$OWN/pycache"
cd "$ROOT/python"
set +e
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest "$@" \
  -o cache_dir="$OWN/pytest-cache" --junitxml="$OWN/$LABEL.xml" >"$OWN/$LABEL.log" 2>&1
RESULT=$?
tail -n 24 "$OWN/$LABEL.log"
exit "$RESULT"
