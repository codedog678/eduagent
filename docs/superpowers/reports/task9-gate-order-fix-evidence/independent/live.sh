#!/bin/bash
set -eu
PG=/opt/homebrew/opt/postgresql@16/bin
OWN=/tmp/m3-task9-spec-independent
LABEL="${1:-baseline}"
DB="m3_t9_spec_live_$(date +%s)_$$_${RANDOM}"
"$PG/createdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"
trap '"$PG/dropdb" -h 127.0.0.1 -p 55432 -U postgres "$DB"' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export PYTHONPATH=/Users/bytedance/Documents/trae_projects/eduagent-m3/python
export PYTHONPYCACHEPREFIX="$OWN/pycache"
export TZ=UTC
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python "$OWN/live_server.py" >"$OWN/live-server-$LABEL.log" 2>&1
