#!/bin/bash
set -eu
OWN=/tmp/m3-task9-spec-feca62c7-189a-4708-b334-5456f6d79d93
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
mkdir -p "$OWN/frontend"
rsync -a --exclude=node_modules --exclude=dist "$ROOT/frontend/" "$OWN/frontend/"
rsync -a --exclude=.vite --exclude=.vite-temp "$ROOT/frontend/node_modules/" "$OWN/frontend/node_modules/"
