#!/bin/bash
set -eu
OWN=/tmp/m3-task9-spec-feca62c7-189a-4708-b334-5456f6d79d93
NODE=/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node
export PATH="$(dirname "$NODE"):$PATH"
export npm_config_cache="$OWN/npm-cache"
export OPS_SCREENSHOT_DIR="$OWN/screenshots"
export TMPDIR="$OWN/tmp"
export TZ=UTC
LABEL="$1"
shift
export PLAYWRIGHT_JUNIT_OUTPUT_FILE="$OWN/$LABEL.xml"
mkdir -p "$OWN/screenshots"
{
  date -u
  "$NODE" --version
  if [ "$1" = build ]; then
    npm run build
  else
    "$NODE" node_modules/@playwright/test/cli.js "$@"
  fi
} > "$OWN/$LABEL.log" 2>&1
tail -n 25 "$OWN/$LABEL.log"
