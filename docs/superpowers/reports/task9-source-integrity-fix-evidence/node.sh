#!/bin/bash
set -eu
OWN=/tmp/m3-task9-fix-48fc04af-9228-4c6b-90bb-bb7109644afa
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
test ! -e "$OWN/$LABEL.log"
printf '%s\n' "$*" > "$OWN/$LABEL-node-command.txt"
{
  date -u
  "$NODE" --version
  if [ "$1" = build ]; then
    npm run build
  else
    "$NODE" node_modules/@playwright/test/cli.js "$@"
  fi
} > "$OWN/$LABEL.log" 2>&1
date -u >> "$OWN/$LABEL.log"
tail -n 25 "$OWN/$LABEL.log"
