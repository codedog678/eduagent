#!/bin/bash
set -euo pipefail
git commit -F - <<'MESSAGE'
fix(ops): validate exact Canary before authenticating full consumed chain

Reuse bounded read-only leaf evidence checks for the exact approved receipt.
Keep independent Canary history, valid Active dual sources and cutoff rules.
Preserve inherited repair and add 47 PostgreSQL complete GET regressions.

New isolated runtime: project/dev/build and requirements constraints verified.
Frozen baseline RED and final backend 1840, API 291, UI 54, production 6x2 pass.
Implementation freeze only; fresh WHOLE SPEC then WHOLE CODE still required.
No real model requests, Task10, amendment, push or hook/signature bypass.
MESSAGE
