#!/bin/bash
set -eu
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
OWN=/tmp/m3-task9-gate-order-fix
EVIDENCE="$ROOT/docs/superpowers/reports/task9-gate-order-fix-evidence"
PY=/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python
LABEL="$1"
shift
export PYTHONPYCACHEPREFIX="$OWN/pycache"
export npm_config_cache="$OWN/npm-cache"
export OPS_SCREENSHOT_DIR="$EVIDENCE/screenshots"
export PLAYWRIGHT_JUNIT_OUTPUT_FILE="$EVIDENCE/$LABEL.xml"
"$PY" "$EVIDENCE/provenance.py" snapshot "$LABEL-before"
trap '"$PY" "$EVIDENCE/provenance.py" snapshot "$LABEL-after"' EXIT
cd "$OWN/frontend"
set +e
npm exec --yes --package=node@20.19.5 -- node -e '
const {spawnSync} = require("node:child_process");
const {dirname, realpathSync} = require("node:path");
const fs = require("node:fs");
console.log("Node", process.version, "node_modules_symlink", fs.lstatSync("node_modules").isSymbolicLink(),
  "node_modules_realpath", fs.realpathSync("node_modules"));
const args = process.argv.slice(1);
const env = {...process.env, PATH:dirname(process.execPath)+":"+process.env.PATH};
const r = args[0] === "build"
  ? spawnSync("npm", ["run", "build"], {stdio:"inherit", env})
  : spawnSync(process.execPath, ["node_modules/@playwright/test/cli.js", ...args], {stdio:"inherit", env});
process.exit(r.status ?? 1);
' "$@" >"$EVIDENCE/$LABEL.log" 2>&1
RESULT=$?
tail -n 24 "$EVIDENCE/$LABEL.log"
exit "$RESULT"
