#!/bin/bash
set -eu
OWN=/tmp/m3-task9-code-20261102-5TNycP
NODE=/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node
LABEL="$1"
shift
export PATH="$(dirname "$NODE"):$PATH"
export npm_config_cache="$OWN/npm-cache"
export OPS_SCREENSHOT_DIR="$OWN/screenshots"
export PLAYWRIGHT_JUNIT_OUTPUT_FILE="$OWN/$LABEL.xml"
export TMPDIR="$OWN/tmp"
export TZ=UTC
set +e
{
  "$NODE" --version
  if [ "$1" = build ]; then
    npm run build
  else
    "$NODE" node_modules/@playwright/test/cli.js "$@"
  fi
} > "$OWN/$LABEL.log" 2>&1
RESULT=$?
tail -n 30 "$OWN/$LABEL.log"
exit "$RESULT"
