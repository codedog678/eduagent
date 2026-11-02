#!/bin/bash
set -eu
OWN=/tmp/m3-task9-fix-48fc04af-9228-4c6b-90bb-bb7109644afa
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
mkdir -p "$OWN/frontend"
rsync -a --exclude=node_modules --exclude=dist "$ROOT/frontend/" "$OWN/frontend/"
rsync -a --exclude=.vite --exclude=.vite-temp "$ROOT/frontend/node_modules/" "$OWN/frontend/node_modules/"
