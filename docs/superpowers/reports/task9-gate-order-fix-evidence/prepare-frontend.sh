#!/bin/bash
set -eu
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
OWN=/tmp/m3-task9-gate-order-fix
EVIDENCE="$ROOT/docs/superpowers/reports/task9-gate-order-fix-evidence"
test ! -e "$OWN/frontend"
mkdir -p "$OWN/frontend"
rsync -a --exclude=node_modules --exclude=dist --exclude=test-results \
  --exclude=playwright-report "$ROOT/frontend/" "$OWN/frontend/"
# Copy dependency bytes; never point Vite config bundling back at M3.
rsync -a --exclude=.vite-temp --exclude=.vite \
  "$ROOT/frontend/node_modules/" "$OWN/frontend/node_modules/"
cp "$EVIDENCE/execution-config/vite.config.ts" "$OWN/frontend/vite.config.ts"
cp "$EVIDENCE/execution-config/playwright.config.ts" "$OWN/frontend/playwright.config.ts"
cp "$EVIDENCE/playwright.live.config.ts" "$OWN/frontend/playwright.live.config.ts"
mkdir -p "$OWN/frontend/live-e2e"
cp "$EVIDENCE/live.spec.ts" "$EVIDENCE/gate-tie.spec.ts" "$OWN/frontend/live-e2e/"
