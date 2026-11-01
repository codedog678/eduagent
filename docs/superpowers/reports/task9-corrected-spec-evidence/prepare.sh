#!/bin/bash
set -eu
ROOT=/Users/bytedance/Documents/trae_projects/eduagent-m3
OWN=/tmp/m3-task9-corrected-spec-20261102
E="$OWN/evidence"
ARCH="$ROOT/docs/superpowers/reports/task9-gate-order-fix-evidence"
mkdir -p "$E/screenshots" "$E/independent" "$E/execution-config" "$OWN/frontend/live-e2e"
cp "$ARCH/pytest-runner.sh" "$ARCH/node-runner.sh" "$ARCH/live-runner.sh" "$ARCH/live-server.py" "$E/"
cp "$ARCH/independent/test_independent.py" "$ARCH/independent/test_gate_tie.py" "$E/independent/"
cp "$ARCH/execution-config/vite.config.ts" "$ARCH/execution-config/playwright.config.ts" "$E/execution-config/"
cp "$ARCH/playwright.live.config.ts" "$ARCH/live.spec.ts" "$ARCH/gate-tie.spec.ts" "$E/"
perl -pi -e 's#/tmp/m3-task9-gate-order-fix#/tmp/m3-task9-corrected-spec-20261102#g; s#EVIDENCE="\$ROOT/docs/superpowers/reports/task9-gate-order-fix-evidence"#EVIDENCE="\$OWN/evidence"#g; s/m3_t9_fix_/m3_t9_cspec_/g; s/33190/33290/g; s/33191/33291/g' "$E/"*.sh
perl -pi -e 's#/tmp/m3-task9-gate-order-fix#/tmp/m3-task9-corrected-spec-20261102#g; s/33190/33290/g; s/33191/33291/g' "$E/live-server.py" "$E/playwright.live.config.ts" "$E/execution-config/"*.ts
perl -pi -e 's#/Users/bytedance/Documents/trae_projects/eduagent-m3/docs/superpowers/reports/task9-gate-order-fix-evidence#/tmp/m3-task9-corrected-spec-20261102/evidence#g' "$E/"*.spec.ts
rsync -a --exclude=node_modules --exclude=dist --exclude=test-results --exclude=playwright-report "$ROOT/frontend/" "$OWN/frontend/"
rsync -a --exclude=.vite-temp --exclude=.vite "$ROOT/frontend/node_modules/" "$OWN/frontend/node_modules/"
cp "$E/execution-config/"*.ts "$OWN/frontend/"
cp "$E/playwright.live.config.ts" "$OWN/frontend/"
cp "$E/"*.spec.ts "$OWN/frontend/live-e2e/"
test ! -L "$OWN/frontend/node_modules"
