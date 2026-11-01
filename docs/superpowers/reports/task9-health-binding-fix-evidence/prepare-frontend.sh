#!/bin/bash
set -eu
OWN=/tmp/m3-task9-health-fix-20261102-xtfx61
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
mkdir -p "$OWN/frontend" "$OWN/screenshots"
rsync -a --exclude=node_modules --exclude=dist --exclude=test-results --exclude=playwright-report "$ROOT/frontend/" "$OWN/frontend/"
rsync -a --exclude=.vite --exclude=.vite-temp "$ROOT/frontend/node_modules/" "$OWN/frontend/node_modules/"
test ! -L "$OWN/frontend/node_modules"
