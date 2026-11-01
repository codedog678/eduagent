# M3 Task8: Health Gates and Transactional Rollback

## Independent Acceptance

更新日期：2026-11-02。代码冻结 `5c38e26` 的完整 Task8 已通过新的独立
SPEC 与 CODE。规格审查独立 692 项矩阵和 32 项探测通过；代码审查独立
完整后端 1607 项、310.45 秒与 32 项探测、16.08 秒通过，均无失败、
错误或跳过。实际范围、失败探测修正、摘要和限制见
[规格记录](2026-11-01-m3-task8-spec-review.md)、
[代码记录](2026-11-01-m3-task8-code-review.md)及
[独立完整报告](2026-11-02-m3-task8-code-recovery.md)。
Task9 可启动；Task10、正式模型资格与整体项目完成仍须另行验证。
下方所有冻结时的待审状态与历史失败按原文保留。

## Cleanup Cause Correction Freeze

最新独立结论是 **SPEC FAIL**，不是新的 CODE FAIL 或独立验收通过。
`e432812` 异常退出修复后，独立审查
`arun_6ae7343451536906a07381f9` 复现 cleanup 包装异常的硬原因链被覆盖；
父侧 docs-only `59b529e15fd16cb7b229c7ea6170fa8bf0f85695` 已归档该失败。
有效执行权内，真实 SQLite ATTACH、范围外标记提交和实际 capability check
产生 `ConfirmedPermissionViolation`，memory-stop/Harness-close 再包装为
RuntimeError。旧合并代码把包装异常的 cause 换成普通执行失败，candidate
错误重试或保存普通最后一次失败，Shadow 保存普通失败；实际晋级和 Active
PASS 仍成功。本节只冻结修复实现与测试，独立 fresh SPEC 再 fresh CODE 尚待进行。
下方全部旧失败、审查与实现冻结记录原样保留，不代表当前验收状态。

本轮 Task8 清单：

- [x] 读取批准计划 Task8、设计 health/security、历史记录与最新 SPEC P1。
- [x] 先保存真实 wrapped cleanup RED，修正窗口键断言后保存第二轮 RED。
- [x] 仅修复 executor 清理合并，不覆盖硬 cause 链；原失败类型保存为 note。
- [x] 验证 candidate 重试/最后一次、Shadow、晋级拒绝与迟到 Active 回滚。
- [x] 冻结聚焦、完整影响矩阵和全后端实际 PostgreSQL/Redis 测试及摘要。
- [x] 清理独占数据库与本轮 pytest 临时目录，暂存精确自有路径，新提交交接。
- [ ] 父侧顺序启动独立 fresh SPEC、fresh CODE；Task9/10 未实施。

### Runtime and Regression Scope

运行代码仅修改 `python/core/distributed/executor.py` 一处：清理错误的 cause
链已有硬诊断且原失败非硬诊断时，用 `add_note()` 保存原失败的类型，
不再赋值 `exc.__cause__`。直接硬异常、嵌套包装及底层硬异常的 cause 均保持
原值；已经优先保存的执行硬违规不被后续清理替换。只记录异常类型，不记录
异常正文或私有载荷。初始/成功/异常退出检查、BaseException/取消处理、
独立清理步骤、Shadow 最后包装与用量传播均不改变。

无新 permission/caller flag、权限通道、Worker/fencing/执行权或发布锁改写。
`a4691bf` 四项规格修复与 `4c9b204` 共享 head/已消费因果链修复保持不变。
既有两套 exceptional-exit 测试文件也未修改。

新增 `python/tests/distributed/test_executor_cleanup_cause.py` 共 124 项：

- 72 项直接 executor 回归覆盖 primary/Shadow、ValueError/CancelledError、
  stop/close/database/usage、直接硬异常和 1/3 层包装、逐节点 cause 身份、
  原失败 note、已有执行硬异常优先、普通清理对照及后续清理独立尝试。
  Shadow 不执行 primary usage callback，相关参数验证其原失败仍保留，
  不把未发生的通知当作越权。
- 48 项真实 Worker 回归覆盖 candidate `max_attempts=1/3` 和 Shadow，
  四种清理阶段、直接/单层/三层硬异常与普通对照。candidate 即使可重试次数
  未耗尽也只保存一次非重试硬终态；Shadow 保持 stable 父结果且清理锁/目录。
  真实终态观测拒绝实际晋级、health FAIL；普通失败保持 not_applicable/isolated
  与 unknown-cost HOLD。真实 Harness `run()` 导出零模型/工具/判定计数，
  实际 usage 持久化；费用仍未知，不伪造 provider 费用。
- 4 项 stop/close 三层包装迟到回归先省略终态通知，消费原有 passing gates
  进入 Active 并确认 PASS，再通过实际 recovery 补录硬终态，确认新 FAIL
  窗口与事务回滚。恢复幂等，旧已受理 candidate 保持固定，新 Run 使用 stable。

硬异常都来自真实 SQLite ATTACH、提交 marker 和实际
`assert_open_store_capability()`；另一个连接复读 marker，不手工构造权限诊断。
stop/close 使用尚未关闭的 Harness 连接；database/usage 位于 Harness 关闭后，
测试用同一固定路径的新真实连接产生其清理检查异常，专门验证合并与诊断
传播，不声称 executor 新增了关闭后的检查。已有执行硬违规与第二个清理硬
违规的优先级对照也使用不同真实连接，避免重复 ATTACH 同名别名。

既有回归继续验证异常源 cause、初始 wrong-store、构造失败、不可查询连接、
外部 executor 取消、锁排空、重复取消与接管。durable 证明均在有效租约内完成。
取消外层 Worker、Shadow 截止或外部取消后的 drain 仍可能丢弃 executor 诊断，
本轮不保证这些路径产生持久权限终态；恢复不能补造不存在的终态。
过期/fenced Worker 不因发现硬违规恢复执行权。直接取消探测只证明 executor
关闭前报告，不证明强制终止 SDK 或过期 worker 持久诊断。

### Frozen Evidence

| 轮次 | 结果和 pytest 用时 | XML 用时 | 自有证据后缀 |
| --- | --- | --- | --- |
| 首轮 RED，运行代码未修改 | 54 fail / 34 pass，7.50 s；含 4 项错误窗口键断言 | 7.496 s | `cause-red` |
| 校正/扩展 RED，运行代码仍未修改 | 75 fail / 45 pass，19.31 s；无错误/跳过 | 19.306 s | `cause-repro-red` |
| 冻结聚焦 GREEN | 195 pass，28.44 s；新增 124 + 原异常退出 71 | 28.435 s | `cause-focused` |
| 冻结完整影响矩阵 GREEN | 692 pass，128.12 s；21 文件 | 128.117 s | `cause-targeted` |
| 冻结全后端 GREEN | 1607 pass，301.44 s | 301.418 s | `cause-full` |

两轮 RED 退出码 1；三轮 GREEN 退出码 0，均无失败/错误/跳过。
首轮错误使用 `hard_failures` 查询当前部署窗口；修正为已有 `candidate` 键，
没有修改 health 实现。校正 RED 扩大到全部清理阶段和 candidate 最后一次/
允许重试两种设置；75 项失败均为 cause 被改写、note 缺失或硬分类丢失。
新增四项 Active 恢复回归及 Worker fixture 抽取在修复后、聚焦 GREEN 前完成。
聚焦/定向/全后端三轮之间没有运行代码或测试修改。全后端只保留已有
`TestAgent` 带构造函数的 collection warning。

所有原始 `.log`/`.xml` 字节保留于
`python/tests/distributed/evidence/2026-11-01-m3-task8-<suffix>`，不重写 RED。
父侧已独立解析前四轮 XML 计数/用时并核验哈希；全后端由本实现者解析核验，
不声称父侧重复跑过。其旧独立 568 pass/114.73 s、新探测 8 fail/16 pass/
6.37 s、取消边界 3 pass/2.21 s 仍是原 SPEC FAIL 的证据，不被本轮绿灯覆盖。

每次 pytest 在单独 zsh shell 创建唯一 `task8_cause_<round>_` 数据库，使用
PostgreSQL 16 `127.0.0.1:55432`、postgres 无密码、Homebrew createdb/dropdb，
EXIT trap 清理。最终 catalog 查询 `task8_cause_%` 返回零行。Redis 为
`redis://127.0.0.1:56379/0`，fixture 独占流在 teardown 清理。
完整运行命令 ID 为 `515b4f9c1867063d3e240e778c56dd58`，已结束、退出码 0。

冻结定向命令，工作目录 `eduagent-m3/python`：

```bash
zsh -c 'set -o pipefail
DB="task8_cause_targeted_$(date -u +%Y%m%d%H%M%S)_${RANDOM}"
/opt/homebrew/opt/postgresql@16/bin/createdb -h 127.0.0.1 -p 55432 -U postgres "$DB" || exit
trap '\''/opt/homebrew/opt/postgresql@16/bin/dropdb -h 127.0.0.1 -p 55432 -U postgres "$DB"'\'' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH=/Users/bytedance/Documents/trae_projects/eduagent-m3/python
export TZ=UTC
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest \
  tests/distributed/test_policy_health.py \
  tests/distributed/test_policy_health_corrections.py \
  tests/distributed/test_policy_health_publication.py \
  tests/distributed/test_instrumentation.py tests/distributed/test_worker.py \
  tests/distributed/test_shadow_worker.py tests/distributed/test_shadow_usage.py \
  tests/distributed/test_policy_assignment.py \
  tests/distributed/test_promotion_schema_upgrade.py \
  tests/distributed/test_promotion_repository.py \
  tests/distributed/test_expert_engine.py tests/distributed/test_expert_repository.py \
  tests/distributed/test_expert_cli.py tests/distributed/test_runtime_schema_startup.py \
  tests/distributed/test_schema_migration.py tests/distributed/test_promotion_contracts.py \
  tests/distributed/test_executor.py tests/distributed/test_policy_pinning.py \
  tests/distributed/test_executor_exception_health.py \
  tests/distributed/test_executor_exception_lifecycle.py \
  tests/distributed/test_executor_cleanup_cause.py -q --tb=short \
  --junitxml=tests/distributed/evidence/2026-11-01-m3-task8-cause-targeted.xml \
  2>&1 | tee tests/distributed/evidence/2026-11-01-m3-task8-cause-targeted.log'
```

全后端使用相同设置的新 `task8_cause_full_` 数据库，测试列表改为 `tests`，
证据后缀 `cause-full`。聚焦为新 suite 加两套原 exceptional-exit suites。
两轮 RED 仅新 suite；首轮 `--tb=short`，校正 RED `--tb=line`。
环境变量为 `DISTRIBUTED_TEST_DATABASE_URL`，不是 `DATABASE_URL`。

### Freeze Identity

实际提交父版本：
`59b529e15fd16cb7b229c7ea6170fa8bf0f85695`。
精确 NEW 提交 SHA 在提交后的交接消息给出，不在正文自引用。
两个自有 Python 文件按 repository-relative 路径排序，组合 SHA-256：
`c97e321cac16d8948ea4025c86b694d320dc8549ce629155202b03da5a54dd22`。

```bash
shasum -a 256 \
  python/core/distributed/executor.py \
  python/tests/distributed/test_executor_cleanup_cause.py | shasum -a 256
```

| Python 文件 | SHA-256 |
| --- | --- |
| `python/core/distributed/executor.py` | `a94715b44f881fd29b6cfae5b439579937292a07872b93fb73b663d2df932b65` |
| `python/tests/distributed/test_executor_cleanup_cause.py` | `f75287ea05df8391c9dfe2c0abfb66ba60c907ef5ecba69ec58971e051fc0f1e` |

| 后缀 | XML SHA-256 | Log SHA-256 |
| --- | --- | --- |
| `cause-red` | `ed48003bd503b2c88d8e294cb73edee6a79bec69c64383fdaa01833020532795` | `f303438b563847c6d2feaf02cbaaaa9ac492d09b0b06e3f283b9252f865dd18b` |
| `cause-repro-red` | `fa44a78b78dfe183b183cc430f2984701bd071236ec149467ba640f3f15443ba` | `2d5b9433b4c9e2cab0c587913805b0ea34ea824288dadec4d91037f451f84f3e` |
| `cause-focused` | `b042f22c2996d37f4ccf26b7d7a339b43a7dbd46eec972fa77a34c45d40f5f1c` | `d455cb250b2d948178cef9011b369c53d03827876f76e735eb81ca213f338477` |
| `cause-targeted` | `02a619d7f7877da5b0072a52f24d7a0f6a1374bf952874d55eb54264b90f4c5d` | `9df1e5a3d14ac8f36b4a48c79713e534c2fb45ce8f674a689d7cc477e5d106e1` |
| `cause-full` | `4936a8ed2d8442483d0f6ef408983be7600cbfd9785a74e16a25ef61d09ab86f` | `1f8686ae34703af470c10ae31c79c67666377acb3e309c597c051d2826a9d6f4` |

自有提交范围仅 executor、新测试、本报告顶部追加及十份新证据，共 13 文件。
父侧 SPEC/CODE/index 报告不编辑、不暂存；primary 工作树只读，保持 clean
`2ff803c968d64741d149e5a1ce88a823d4d32422`。最终核验 AST、源码/报告空白、
内容摘要、XML 和提交路径。原始 RED log/XML 的尾随空白保留为采集事实。
无安装、Docker、外部模型调用、环境/密钥输出、amend、push、Task9/10、
其它实现者或主分支写入。测试是 fixture、非正式发布资格、非 OS 沙箱，
不证明学生效果。下方为完整保留的历史记录。

## Exceptional Exit Correction

Current independent verdict remains **CODE FAIL**. Review
`arun_6ae72e3051536906a0738117` reproduced an actual SQLite ATTACH outside write
followed by ValueError through both primary candidate and Shadow workers.
The successful-return control detected the violation, but exceptional exits
skipped the capability check. Promotion and subsequent Active PASS succeeded.
Parent archived this new failure in docs-only `7a6966a`; all historical reviews
and failures below remain preserved. This correction does not grant acceptance.

Approved Task8-only implementation checklist:

- [x] Read the approved Task8 plan, health/security design, preserved SPEC/CODE
  failures, executor, worker diagnostics, usage and publication paths.
- [x] Preserve RED using real SQLite ATTACH/write then ValueError through both
  workers, with successful outside-write and clean-failure controls.
- [x] Reuse the existing opened-store check on exceptional exits before close;
  preserve confirmed diagnostics through cancellation, cleanup and usage.
- [x] Verify promotion rejection and late consumed-source Active FAIL/rollback,
  recovery, pinning and the complete Task8/full backend regression matrices.
- [x] Archive owned evidence, digest, cleanup and actual parent; new commit only.
- [ ] Parent performs fresh SPEC then fresh CODE after freeze; Task9/10 untouched.

### Runtime Boundary

Only `python/core/distributed/executor.py` changes at runtime. The existing
initial and successful-return checks remain unchanged. The shared exception
handler now catches BaseException, including cancellation, and checks the actual
opened connection with the same `assert_open_store_capability()` before stopping
the memory worker or closing the Harness. A confirmed mismatch retains the
source exception/cancellation as its explicit cause. If the connection cannot
be queried, the original exception survives; unavailable capability is not
turned into a permission violation. Constructor failure with no Harness is safe.

Cleanup attempts memory-worker stop, Harness close, orchestrator database close,
and primary usage recording independently. Cleanup failures cannot replace an
existing execution failure/cancellation or confirmed hard diagnostic; their
exception types are retained as notes without logging bodies. A cleanup-only
failure still fails execution. Any confirmed diagnostic in a cleanup cause
chain takes precedence over an ordinary failure. Shadow wraps the retained
Exception only after cleanup, carrying its usage and explicit cause; a clean
CancelledError is not wrapped. Existing Worker/ShadowWorker classification,
non-retryable hard failures, fenced usage and observation recording are reused.
No worker, health, promotion, schema or Task7 authority mechanism was rewritten.

The four SPEC corrections in `a4691bf` and shared-head publication/consumed
causal inheritance in `4c9b204` are unchanged. The targeted/full suites retain
their coverage. No new permission flags, caller diagnostics, parallel permission
mechanism or OS sandbox claim is introduced.

### Regression Proofs

Two owned suites contain 71 new cases. Real SQLite ATTACH creates an outside
database and commits a marker on the opened Harness connection; an independent
connection reads the marker after exit. The actual Harness `run()` failure and
finally usage paths execute with zero model/provider calls. Its HTTP wrapper is
unwrapped in the fixture to reproduce the reviewed ValueError exactly.

- Real Redis primary Worker and PostgreSQL attempts record one terminal,
  non-retryable `ConfirmedPermissionViolation` for outside write then ValueError.
  Actual ShadowWorker records the same typed diagnostic without changing its
  stable parent. Both preserve complete no-model usage counters with unknown
  provider cost, rather than inventing charges or structured decisions.
- Successful outside-write controls still reject promotion. Clean-store
  ValueError remains ordinary (`ValueError` primary, `execution_failed` Shadow),
  with `not_applicable`/`isolated` permission outcomes and honest unknown-cost
  HOLD rather than a fabricated hard FAIL.
- Both stages reject actual promotion after a committed exceptional-exit
  observation. If notification is deliberately omitted, the actual passing
  Shadow/Canary gates may be consumed before recovery. The successor Active
  first passes; real recovery then publishes the hard source terminal and the
  next evaluation invalidates PASS and rolls back. Recovery retries are
  idempotent. Accepted old Active Runs retain candidate binding after rollback;
  new Runs use stable. This tests the existing causal/publication fix unchanged.
- Stop cancellation, Harness-close failure, orchestrator cleanup failure and
  primary usage-notification failure cannot erase the hard terminal or persisted
  counters. Source cancellation also records the hard violation through both
  live, authorized workers.
- Direct executor probes verify initial-check rejection, constructor failure,
  unavailable connection, ordinary exception/cancellation identity through
  cleanup, exact cause preservation, and check-before-close ordering. External
  executor-task cancellation with a live outside attachment surfaces the hard
  violation; clean external cancellation remains the same CancelledError.

Authority limit: these new durable worker proofs complete within valid leases.
Cancelling the enclosing primary Worker retains its existing cancellation
handler; Shadow deadline/external-cancellation cleanup retains its existing
`gather(return_exceptions=True)` drain. This correction does not add a terminal
publication route for results discarded by those worker paths. In particular,
an expired/fenced worker cannot regain terminal authority merely because its
executor detects a hard violation during drain. Such a result is not guaranteed
to become a durable permission terminal, and SQL recovery cannot fabricate one
from an absent terminal. The direct cancellation probes prove executor reporting
before close, not persisted expired-worker diagnostics or forced SDK termination.
Existing lock-drain, repeated-cancellation and takeover regressions still pass.

### Frozen Evidence

| Round | Result | XML Time | Evidence Suffix |
| --- | --- | --- | --- |
| Initial RED, no runtime edits | 15 fail / 2 pass, 7.67 s; includes two overly strict success-control key assertions | 7.659 s | `exception-red` |
| Corrected RED, no runtime edits | 29 fail / 14 pass, 7.64 s; both success controls and clean/initial controls pass | 7.640 s | `exception-repro-red` |
| Initial focused GREEN | 43 pass, 7.61 s; before expanding clean cleanup/external cancellation probes | 7.609 s | `exception-focused` |
| Frozen targeted GREEN | 568 pass / 0 failure/error/skip, 111.24 s | 111.233 s | `exception-targeted` |
| Frozen full backend GREEN | 1483 pass / 0 failure/error/skip, 279.66 s | 279.636 s | `exception-full` |

All five raw `.log`/`.xml` pairs remain preserved under
`python/tests/distributed/evidence/2026-11-01-m3-task8-<suffix>`.
Both RED runs exited 1; all GREEN runs exited 0. No runtime/test edits occurred
between frozen targeted and full runs. Full retains the existing `TestAgent`
constructor collection warning. These are engineering fixtures, not independent
review approval, formal JudgeV3 release qualification or student-effect evidence.

Each pytest invocation created a new unique `task8_exception_<round>_` database
using PostgreSQL 16 at `127.0.0.1:55432`, no password, and the Homebrew
createdb/dropdb binaries. Every invocation ran in its own zsh shell with an EXIT
cleanup trap. Final catalog query found zero `task8_exception_%` databases.
Redis was `redis://127.0.0.1:56379/0`; the real broker fixture uses unique streams
and cleans them at teardown. No parent databases/processes were managed.

Frozen targeted invocation, working directory `eduagent-m3/python`:

```bash
zsh -c 'set -o pipefail
DB="task8_exception_targeted_$(date -u +%Y%m%d%H%M%S)_${RANDOM}"
/opt/homebrew/opt/postgresql@16/bin/createdb -h 127.0.0.1 -p 55432 -U postgres "$DB" || exit
trap '\''/opt/homebrew/opt/postgresql@16/bin/dropdb -h 127.0.0.1 -p 55432 -U postgres "$DB"'\'' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH=/Users/bytedance/Documents/trae_projects/eduagent-m3/python
export TZ=UTC
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest \
  tests/distributed/test_policy_health.py \
  tests/distributed/test_policy_health_corrections.py \
  tests/distributed/test_policy_health_publication.py \
  tests/distributed/test_instrumentation.py tests/distributed/test_worker.py \
  tests/distributed/test_shadow_worker.py tests/distributed/test_shadow_usage.py \
  tests/distributed/test_policy_assignment.py \
  tests/distributed/test_promotion_schema_upgrade.py \
  tests/distributed/test_promotion_repository.py \
  tests/distributed/test_expert_engine.py tests/distributed/test_expert_repository.py \
  tests/distributed/test_expert_cli.py tests/distributed/test_runtime_schema_startup.py \
  tests/distributed/test_schema_migration.py tests/distributed/test_promotion_contracts.py \
  tests/distributed/test_executor.py tests/distributed/test_policy_pinning.py \
  tests/distributed/test_executor_exception_health.py \
  tests/distributed/test_executor_exception_lifecycle.py -q --tb=short \
  --junitxml=tests/distributed/evidence/2026-11-01-m3-task8-exception-targeted.xml \
  2>&1 | tee tests/distributed/evidence/2026-11-01-m3-task8-exception-targeted.log'
```

Full used the same setup in a new shell with `task8_exception_full_`, test list
`tests`, and suffix `exception-full`. Earlier two RED rounds and focused GREEN
used only the new suites (initial RED only the health suite).

New freeze parent is `7a6966ac6e03a747d6fc6a9c93de0463904c5d63`; the exact NEW
commit is supplied at handoff, not self-referentially embedded here. Three owned
Python files, sorted repository-relative paths, have combined SHA-256
`151452b68ffaa4c720f371d27c62367dd05a4bf7d42ebdaa7bf3fed54907c654`.

```bash
shasum -a 256 \
  python/core/distributed/executor.py \
  python/tests/distributed/test_executor_exception_health.py \
  python/tests/distributed/test_executor_exception_lifecycle.py | shasum -a 256
```

| Suffix | XML SHA-256 | Log SHA-256 |
| --- | --- | --- |
| `exception-red` | `b795c2ca51bb2758aacf2db2ec14c56ea14aaf3ea3f05cf42637765b900237dd` | `db283ffbe45b2c01a08e4e028d7b6d1a0c985495104e8d3c61af3ed0c93f8485` |
| `exception-repro-red` | `dd4377d99a78ab9e2bd7a0e6d3ff676d3ebfe40c419e47734a4bbf07d50b8849` | `e741d65d105b96e7761b08a6a19483369d43963611f1678d7813f45c97378bde` |
| `exception-focused` | `f73b93505e24e05a3a50dd889e9aa68d3c23ddcb32a53a29dfd83e8959cda67d` | `36617709c69e392822781fa7241f84c578ecabbc9cbe341c07cfb3bc29bfca44` |
| `exception-targeted` | `12932ea23977bde59ba14e4d196f39283bd74f8c84dd1279d26b36e9b26aa5e8` | `42a92e7206af447fce93cdcede87b6a8c01e6e0f576c6214a97b33dd88e774d9` |
| `exception-full` | `744dbb27873b65ef365dd0efcb8413880c69f669413db1c62e7adb94e4e205ee` | `e43e510bd4c5d89262efa40c589cdd5370ca273fa000cf3cc0a62465c87842b3` |

Only the executor, two new test suites, this report and ten owned evidence files
belong to this commit. Parent review reports and interview-readiness index were
not edited or staged. Primary remains read-only, clean at
`2ff803c968d64741d149e5a1ce88a823d4d32422`. Both worktrees are checked for
cleanliness after commit. No installs, Docker, external model calls, secrets/env
dumps, amend, push, main writes, Task9 or Task10 work occurred.

AST parsing of all three owned Python files and staged source/test/report
whitespace checks pass. The unrestricted staged whitespace check reports 30
trailing-whitespace lines in the two raw RED log/XML pairs. Those captured bytes
are intentionally preserved with their hashes, not reformatted as source.

The following sections are preserved historical implementation freezes, not the
current correction identity or a replacement for the parent-owned CODE FAIL.

## CODE P1 Correction Freeze

Current independent verdict is **CODE FAIL** despite historical SPEC PASS and
457 targeted / 1400 backend passes. The independent real PostgreSQL probe
published an actual candidate permission terminal after the gate query but
before Active creation; activation succeeded and later Active evaluation passed.
This section supersedes earlier freeze claims; all historical evidence remains.
Correction base is parent docs-only `07293a2`, following `6e55434`.
Implementation verification is complete below; the current independent verdict
remains CODE FAIL until the parent performs fresh SPEC then CODE review. This
implementation report does not replace the parent-owned review records/index.

Approved Task8-only correction plan:

- [x] Read Task8, design 9.1-9.3, original SPEC FAIL/four corrections/PASS,
  independent CODE P1 and terminal completion/publication lock ordering.
- [x] Archive RED: actual typed server store-boundary terminal, transaction
  pause after gate query, PostgreSQL blocking PID barrier, late Active PASS.
- [x] Serialize all recorder inserts on the server-derived environment head.
  Recorder must not acquire health advisory after head, nor hold terminal
  Run/Shadow completion locks while waiting for publication.
- [x] Inherit hard events only through the immutable validated consumed
  promotion predecessor chain, not arbitrary historical policies/head versions.
- [x] Verify focused and full real-service backend matrices, archive GREEN,
  freeze digest, stage owned paths and create a new commit without amend/push.
- [ ] Parent launches fresh SPEC then CODE reviews; Task9 remains unstarted.

### Publication and Causality

`PolicyObservationRecorder._insert()` resolves the immutable deployment's
environment from PostgreSQL and locks that environment head `FOR UPDATE` before
inserting and assigning database `created_at`. All direct Run, direct Shadow,
and recovery publication routes use this boundary. Identity/outcome still come
from persisted Run/attempt/Shadow rows, not caller policy/cohort/permission flags.
No source terminal row is locked by publication. Worker completion/failure
transactions finish before recorder calls, so publication waits do not retain
Run/attempt/lease/Shadow locks or their expiring execution authority.

Promotion, registration, admission freeze, and health CAS already lock the same
head. Health keeps its existing advisory-then-head ordering; publication takes
head only and never acquires the health advisory. If publication commits first,
the transition's subsequent locked gate query rejects the hard event. If the
transition holds head first, publication blocks until that transition commits.
Rechecking a gate without shared synchronization is not used as the fix.

The successor still inherits a late hard event from its causal predecessor.
Active's Canary source reuses the exact immutable activation approval,
audit, consumed receipt, and fully replayed passing window validator. Canary's
Shadow source requires the immediately preceding matching deployment and
immutable Shadow-to-Canary audit, stable/candidate identities, thresholds,
assignment salt and previous-stable deployment. The hard-event query is bounded
to the deployment plus at most two predecessors, freezes one earliest typed
hard key, and remains lifetime-wide rather than last-50 limited. Missing Active
source evidence continues to HOLD. Ordinary Active baseline logic and all four
prior SPEC corrections are unchanged.

On the next current-head evaluation a committed inherited hard event creates
a distinct FAIL window with `hard_failures`, preventing reuse of an existing
Active PASS, and uses the existing atomic CAS/audit/Outbox rollback. A genuinely
old unrelated chain only receives historical FAIL windows. The new regressions
re-register the *same* artifact in another chain and prove neither a new Active
head nor a frozen stable-serving head is moved by the old Canary event.
Hash equality alone is not accepted as causal lineage.

### Regression Evidence

The new 12-case suite extends the real registration -> Shadow -> Canary ->
Active fixture. It opens an actual wrong server-selected SQLite store through
`LearningTaskExecutor`; the real Worker/ShadowWorker emits and persists
`ConfirmedPermissionViolation`, with no fabricated diagnostic or caller flags.
Model/provider responses remain fixtures and this is not release qualification.

- Four direct/recovery barriers pause a real promotion transaction after its
  gate query while head is locked, observe the actual blocker backend PID via
  live `pg_locks`/`pg_blocking_pids`, and check database clock chronology.
  Publication must block, then the successor must inherit FAIL and roll back.
- Two committed-first controls reject promotion and keep one rejected audit.
- Two publication-first barriers hold an uncommitted real observation/head
  transaction while promotion and advisory-locked health wait. The live PID
  dependency chain includes PostgreSQL waiter queuing; all finish without
  deadlock and terminal publication retries remain idempotent.
- Two late predecessor cases prove both consumed Shadow and consumed Canary
  events invalidate a previously passing Active window.
- Two unrelated same-policy chains prove historical evaluation cannot move
  a newer Active or frozen stable-serving head.

| Round | Result | Evidence Suffix |
| --- | --- | --- |
| Initial RED, before runtime edits | 7 fail, 5.21 s; five feature reproductions plus two incorrect expected exception types | `p1-red` |
| Fixture-corrected RED, before runtime edits | 5 fail / 2 pass, 3.78 s; four publications escaped locked gate/head transaction; late Canary reused Active PASS | `p1-repro-red` |
| Development | 213 pass / 4 fail, 63.82 s; observer `pg_stat_activity` transaction snapshot hid actual blocking | `p1-dev` |
| Scoped development | 9 pass / 2 fail, 19.58 s; direct-PID count missed queued waiter dependency | `p1-scoped` |
| Focused GREEN | 222 pass, 45.90 s; four health/promotion suites, including all 12 publication cases | `p1-focused` |
| Frozen targeted GREEN | 469 pass / 0 failure/error/skip, 101.43 s; XML time 101.424 s | `p1-targeted` |
| Frozen full backend GREEN | 1412 pass / 0 failure/error/skip, 270.88 s; XML time 270.868 s | `p1-full` |

All `.log`/`.xml` files are preserved under
`python/tests/distributed/evidence/2026-11-01-m3-task8-<suffix>`.
Development failures were test-observer issues, not counted as successful
verification. The final barrier polls live locks, not cached activity or a
fixed sleep to infer contention. The full run retains the pre-existing
`TestAgent` constructor collection warning.

Each invocation used a new unique database with PostgreSQL 16
`127.0.0.1:55432`, Redis `127.0.0.1:56379/0`, the existing main-worktree venv,
absolute m3 `PYTHONPATH` and `TZ=UTC`. Createdb/dropdb use
`/opt/homebrew/opt/postgresql@16/bin` and an EXIT trap. Catalog verification
after the final run found zero databases matching this task's `task8_p1_%`
prefix. Parent databases/processes were not managed.

Frozen execution commands from `eduagent-m3/python`:

```bash
set -o pipefail
DB="task8_p1_targeted_$(date -u +%Y%m%d%H%M%S)_${RANDOM}"
/opt/homebrew/opt/postgresql@16/bin/createdb -h 127.0.0.1 -p 55432 -U postgres "$DB"
trap '/opt/homebrew/opt/postgresql@16/bin/dropdb -h 127.0.0.1 -p 55432 -U postgres "$DB"' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH=/Users/bytedance/Documents/trae_projects/eduagent-m3/python
export TZ=UTC
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest \
  tests/distributed/test_policy_health.py \
  tests/distributed/test_policy_health_corrections.py \
  tests/distributed/test_policy_health_publication.py \
  tests/distributed/test_instrumentation.py tests/distributed/test_worker.py \
  tests/distributed/test_shadow_worker.py tests/distributed/test_shadow_usage.py \
  tests/distributed/test_policy_assignment.py \
  tests/distributed/test_promotion_schema_upgrade.py \
  tests/distributed/test_promotion_repository.py \
  tests/distributed/test_expert_engine.py tests/distributed/test_expert_repository.py \
  tests/distributed/test_expert_cli.py tests/distributed/test_runtime_schema_startup.py \
  tests/distributed/test_schema_migration.py tests/distributed/test_promotion_contracts.py \
  tests/distributed/test_executor.py -q --tb=short \
  --junitxml=tests/distributed/evidence/2026-11-01-m3-task8-p1-targeted.xml \
  2>&1 | tee tests/distributed/evidence/2026-11-01-m3-task8-p1-targeted.log
```

Full invocation used the same setup in a separate shell and new database prefix
`task8_p1_full_`, replacing the test list with `tests`, and both evidence suffixes
with `p1-full`. No runtime/test edits occurred between the frozen runs.

### Freeze Identity

New commit is the commit containing this report, parent `07293a2`; its exact
hash is supplied at handoff rather than self-referentially embedded here.
Four owned Python files, sorted repository-relative paths, content digest:
`9785e3347d5bbb50aed170e8946831c7f263b892731bd2b1b71748056a57e4f3`.

```bash
shasum -a 256 \
  python/core/distributed/policy_health.py \
  python/core/distributed/promotion_repository.py \
  python/tests/distributed/test_policy_health_corrections.py \
  python/tests/distributed/test_policy_health_publication.py | shasum -a 256
```

| XML Suffix | SHA-256 |
| --- | --- |
| `p1-red` | `578d8afe4d86b4c10c82a91cac15c6cffa1fbe6aab985dc8c42696b302f2371c` |
| `p1-repro-red` | `ccb9416c9c5cd3bf1cdb330ea1d3ae7391fb75c2db2b51c6ed260d82c14f7781` |
| `p1-dev` | `f75a4b656946ab7c1041471db726568d2af9f957ec809af678eb725a1e64edea` |
| `p1-scoped` | `712ed158c5e1538c04e6116bfa75d50297a068c42a7cf54ec9bcf50e99069175` |
| `p1-focused` | `6cb7f5104366ea2eaa9301624c3169b8f9f24741c7fdaad8ccf697c41985d7cc` |
| `p1-targeted` | `b8707601e1402741664fd6be16388c7c6b87d019f3c925b18513afdf5b274952` |
| `p1-full` | `20877b910caa7edc5cd1fa450a1563b3383dcc0bb97dd18bb704dd9b1b00c160` |

Limits: no installation, Docker/Compose, push/amend, external model calls,
frontend work, Task9/10 implementation or independent approval. Actual store
boundary checks are not OS sandboxing. Health process availability still
governs automatic rollback timing; this correction ensures a committed causal
hard event cannot produce/reuse a PASS, not that publication itself rolls back.
Model credentials are not the missing prerequisite; formal JudgeV3
qualification evidence remains absent. Fixture costs are not provider charges.
Staged source/report whitespace checks pass. The unrestricted staged diff check
reports six trailing-whitespace lines in raw pytest RED `.log`/`.xml` output;
those captured evidence bytes and their hashes are intentionally preserved.

## Fresh SPEC Corrections and Current Freeze

This section supersedes the original implementation freeze below. The independent
SPEC review failed despite the original 407/1350 green tests; those tests did not
cover recovery starvation, legitimate Active baselines, full receipt/window
consumption validation, or unequal-count proportional windows. The original
review file and qualification-prerequisite report are parent-owned and unchanged.
This correction is Task8 only, not Task9, Task10, or independent review approval.

- Implementation base: `b9924dc`; approved correction follows docs-only parent
  `172bcb9` (including `e52c05d` and `86ceca2`).
- Recovery SQL excludes SQL/JSON-null bindings before the bounded limit, for
  both primary and Shadow. Unknown legacy hashes remain non-executable; no
  binding, usage, or release eligibility is fabricated. The regression creates
  205 old unbound terminals, performs two actual PostgreSQL migrations including
  unknown-hash artifact backfill, and proves newer valid terminals recover
  without repeated zero-persistence polls.
- Canary compares the last 50 candidates against a stable pool bounded to 50.
  It selects the largest qualified exact-proportion baseline deterministically,
  choosing newest rows within each rehearsal/operation bucket. Integer
  cross-multiplication enforces equal distributions, not equal sample counts.
  50/20 one-bucket and 40/10 versus 16/4 two-bucket samples qualify. Missing
  buckets, incompatible proportions, or fewer than 20 stable Runs hold.
- Active never accepts stable observations assigned to the Active deployment.
  It uses only stable keys from the passing predecessor Canary window actually
  consumed by the immutable activation approval. It replays receipt/window
  evidence and checks predecessor environment, candidate/stable policies,
  thresholds, audit/approval binding, rehearsal/operation/contract and observed
  and persisted chronology before activation. No global historical or
  production-stable query substitutes for this evidence.
- Receipt consumption requires an existing persisted passing window, complete
  canonical identity and evidence hashes, exact keys, aggregates, gate cohort,
  artifact protocol/runtime/source, version, thresholds, sample count and cost.
  It reloads bounded observations, recomputes aggregates/decision, and checks
  identity and chronology. The latest non-pass window and lifetime confirmed
  permission event still block consumption. Shadow retains strict paired parents.
- Real command-chain fixtures exercise healthy Canary-to-Active and strict
  equal-threshold latency rollback under 100% Active candidate assignment,
  including old candidate pinning and new stable assignment after rollback.
- Unknown cost/decisions, lifetime hard events, immutable pinning, lock fencing,
  typed actual SQLite permission diagnostics, schema checks/read-only startup
  and bounded metrics are unchanged and covered by the final targeted matrix.

Correction content digest (four owned Python files, sorted repository paths):
`d4e4f774402a8e9249f0623e544f9e28498a0ce461bf2e38b1759a41fb96dd91`.

```bash
shasum -a 256 \
  python/core/distributed/policy_health.py \
  python/core/distributed/promotion_repository.py \
  python/tests/distributed/test_policy_health_corrections.py \
  python/tests/distributed/test_promotion_repository.py | shasum -a 256
```

| Correction Round | Observed Result | Evidence |
| --- | --- | --- |
| Initial RED probe | 19 pass / 21 fail, 14.97 s; exit 1 | `2026-11-01-m3-task8-corrections-red.xml` / `.log`; includes fixture NULL-constraint, pending-delete flush and UUID setup errors, not all feature reproductions. Preserved unchanged. |
| Fixture-corrected RED | 19 pass / 21 fail, 14.83 s; exit 1 | `2026-11-01-m3-task8-corrections-repro-red.xml` / `.log`; recovery repeats `[200,200,200]` primary or `[400,400,400]` primary/Shadow with zero persisted. Active admission still encountered incompatible fixture fixed-components. |
| Active feature RED | 0 pass / 2 fail, 1.48 s; exit 1 | `2026-11-01-m3-task8-active-repro-red.xml` / `.log`; after fixing the artifact fixture, legitimate healthy and threshold-failing Active windows both hold against unchanged production code. |
| Development impact | 193 pass / 7 fail, 37.64 s | Original 40 correction cases green; older command-test helper still assumed receipt-only evidence. Fixture helper now creates real persisted windows; validator not weakened. |
| Scoped GREEN | 200 pass, 36.14 s; exit 0 | Correction, health and promotion suites; development result before ten additional edge cases. |
| Frozen targeted GREEN | 457 pass / 0 fail/error/skip, 91.68 s; exit 0 | `2026-11-01-m3-task8-corrections-targeted.xml` / `.log`; XML time 91.676 s. Includes all 50 new correction cases. |
| Frozen full backend GREEN | 1400 pass / 0 fail/error/skip, 258.60 s; exit 0 | `2026-11-01-m3-task8-corrections-full.xml` / `.log`; XML time 258.590 s. Same pre-existing `TestAgent` collection warning. |

No runtime/test edits occurred between the frozen targeted and full runs. Each
run used a new unique database, PostgreSQL 16 at `127.0.0.1:55432`, Redis
`127.0.0.1:56379/0`, the existing main `.venv/bin/python`, absolute m3 Python
`PYTHONPATH`, and `TZ=UTC`. The database variable was
`DISTRIBUTED_TEST_DATABASE_URL`, not `DATABASE_URL`. Each invocation created
and dropped its own database with the PostgreSQL 16 Homebrew executables and
an `EXIT` trap. Final catalog verification found no databases for any correction
run prefixes. No parent processes/databases were managed.

Final targeted command is the original 15-file matrix below plus
`tests/distributed/test_policy_health_corrections.py`; output names have suffix
`corrections-targeted`. Full command remains `python -m pytest tests -q
--tb=short`, with suffix `corrections-full`. Evidence remains under
`python/tests/distributed/evidence/`.

| Correction XML | SHA-256 |
| --- | --- |
| `2026-11-01-m3-task8-corrections-red.xml` | `e4d6343ffa0ab2f93e357e17b7e3826bd02fa99ce6297fb85f5dc195f6c5369c` |
| `2026-11-01-m3-task8-corrections-repro-red.xml` | `8385bf5a2892afc166d5ec3f5cad8dd1e3b732a840a453ddb5cf715a87719fd7` |
| `2026-11-01-m3-task8-active-repro-red.xml` | `d045575dbdc75f3fc2f159609f5082105b9b2cd3b29f41b893388aa3eca1fac1` |
| `2026-11-01-m3-task8-corrections-targeted.xml` | `2d78fb32edc1bfa41b17be0ae839588ff291fca45ccbf9f8873aac39580521aa` |
| `2026-11-01-m3-task8-corrections-full.xml` | `444d6a82f721b46ac82c72c47a6eab3d816366534292c05f8b52b4dffb1d5f86` |

These are deterministic engineering fixtures: no provider/model requests,
installation, Docker verification, push, or real release qualification occurred.
The formal JudgeV3 qualification chain is missing; configured credentials in
the primary workspace are not the blocker. Parent independent fresh SPEC then
CODE reviews remain pending. Broad M3 completion is not claimed.

## Scope and Freeze Identity

Historical original implementation evidence follows; it is not the current
correction freeze or proof that the four fresh SPEC failures were absent.

- Task8 implementation only. No Task9 Ops/UI work, deployment, live model evaluation, installation or push.
- Isolated worktree: `eduagent-m3`, branch `feature/m3-trusted-policy-promotion`.
- Test-freeze starting base: `4418e66`; final integration parent: `d50b25d` (parent documentation-only commit during testing). Parent-owned demo, benchmark, interview, frontend and prior report changes are not staged.
- Approved references: plan Task8 and design sections 9.1-9.3.
- Frozen Task8 Python content digest: `f46c6276d788144531e316f5b1a58d7e40b867cfa31f1671935e2eee0efc31c4`.
- Schema version: `3`; schema contract hash: `61f768276d7b939bd66d8c55f0f0c37c373dfb6dcc20849eb47cf1403b9f361e`.
- Default frozen thresholds hash: `35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f`.

The digest covers the 23 changed/new runtime Python files and five changed/new test files, ordered by repository-relative path. After checkout of the Task8 commit, reproduce with:

```bash
git show --pretty='' --name-only b9924dc -- '*.py' | LC_ALL=C sort | xargs shasum -a 256 | shasum -a 256
```

The report and XML/log evidence are excluded from this content digest. Final commit identity is the commit containing this report; no self-referential commit hash is embedded here.

## Implemented Contracts

| Area | Authoritative behavior |
| --- | --- |
| Observation | `record_run(run_id)` accepts no caller policy/cohort identity. PostgreSQL Run, attempts and committed business step supply frozen identity, terminal outcome, latency, actual server diagnostic and cumulative attempt usage. |
| Identity | Canonical hash of `{run_id, deployment_id, cohort, metric_contract_version}`. Terminal retries create one final observation; paired Shadow and stable primary share parent Run ID but coexist. |
| Recovery | Poll PostgreSQL for missing observations using full deployment/cohort/contract identity; Redis terminal notification is not required for recovery. |
| Shadow | Stable primary and Shadow must match parent Run IDs and immutable deployment. Shadow isolation maps to `isolated`, not an invented permission grant; absent structured evidence maps to `unavailable`. |
| Canary/Active | Canary uses same-deployment stable; Active uses only the gate-pinned predecessor Canary baseline. Same stable policy, rehearsal/operation distribution and metric contract; production stable cannot substitute. Missing qualified distributions hold, not unequal counts alone. |
| Window | Sort by `(observed_at, observation_key)`, select the last 50 candidates, select bounded matched baselines and freeze exact keys, aggregates, threshold identity and deterministic window ID. |
| Arithmetic | Decimal mean cost and nearest-rank p95; relative increase uses frozen epsilon. Equal-to-maximum fails. Ordinary guardrails require at least 20 candidate and 20 matched stable Runs. |
| Missing evidence | Unknown cost or structured counts hold, never zero/pass. A separately known failure at qualified sample size still fails; confirmed permission failure is immediate regardless of missing evidence or baseline. |
| Hard failure | A bounded lifetime lookup freezes the earliest confirmed candidate permission event even if it fell outside the last 50 samples. An already committed hard event blocks old pass receipts before the next evaluator poll. |
| Receipt | Pass issues deployment/version/threshold/window-bound Shadow or Canary health receipt with the exact artifact protocol/runtime/source identity. Hold/fail issue none; existing qualification requirements remain enforced. |
| Rollback | Environment advisory lock plus head `FOR UPDATE`; recheck deployment/version/window; insert immutable failed-candidate-retaining `rolled_back` snapshot with traffic 0; CAS head, audit and Outbox in one transaction. Stable policy is unchanged. |
| Late events | Old accepted Runs retain candidate binding. New Runs use stable after rollback. Old-deployment observations create historical windows only; two evaluators of one window produce one rollback. |
| Faults | Only signed rehearsal candidate bindings allow frozen server latency or `RehearsalInjectedCommitFailure` immediately before commit transition. Persist injection separately from natural failure origin. |
| Permission | `ConfirmedPermissionViolation` is a typed server invariant diagnostic propagated through exception causes. Actual opened SQLite database metadata is checked against the frozen store capability before/after execution; ordinary request/tool denial is not a confirmed violation. |
| Metrics | Fixed-label local counters/histograms update only after committed observation/window/assignment work. Separate PostgreSQL gauges refresh at the metrics endpoint and cover cross-process persistent counts. No learner/request/Run/deployment/hash labels. |
| Startup | `policy-health` polls only when promotion is enabled. Ordinary runtime startup only checks version 3 and contract hash; explicit CLI migration performs real `ADD COLUMN`/indexes and transactional historical backfill before publishing the marker. |

`HealthDecision` preserves the existing external `rollback` enum. Internally windows store `fail`; `health_decision_from_window()` maps the wire enum without claiming that a head moved. Automatic rollback applies only to the current Canary/Active head. A failed Shadow window denies a gate but does not move the head.

## Usage and Decision Accounting

Primary execution now exports the same context evidence as isolated Shadow execution and persists it on the fenced PostgreSQL attempt. Coordinator schema decisions count real attempted parses, including invalid output. Accepted expert envelopes carry cumulative charged usage and actual structured draft/repair decisions. Inline expert usage is not counted twice.

Retry attempts are aggregated, including known charged calls and uncertain usage. Missing provider cost, missing attempt ledger, uncovered Coordinator/Tutor calls or uncertain expert usage keep cost unknown. Token counts remain independently known or unknown; no expert-only ledger is presented as a complete whole-Run bill. Unknown/invalid structured rate uses actual decision counts, not completed-Run counts.

The Task7 lock/lease protections are preserved: attempt/job/shadow blocking locks precede the final fresh database-time authorization, and Shadow cancellation drains the internal task before capability release. New usage and injection writes follow the same fenced attempt-lock discipline.

## Test Execution

All final implementation tests use the existing main-worktree Python virtual environment, not an installed replacement. PostgreSQL 16 and Redis are real local services; model/provider behavior is deterministic fixture behavior with no external model requests.

```bash
createdb -h 127.0.0.1 -p 55432 -U postgres "$DB"
trap 'dropdb -h 127.0.0.1 -p 55432 -U postgres "$DB"' EXIT
export DISTRIBUTED_TEST_DATABASE_URL="postgresql+asyncpg://postgres@127.0.0.1:55432/$DB"
export DISTRIBUTED_TEST_REDIS_URL=redis://127.0.0.1:56379/0
export PYTHONPATH="$PWD"
export TZ=UTC
```

Each own integration run uses a separately created database and drops it at exit. Redis test streams use unique test identities. Parent test processes/databases are not managed by this implementation task.

| Round | Result | Evidence/status |
| --- | --- | --- |
| Initial feature RED | Health module/methods absent, `ModuleNotFoundError` | Observed before implementation; development check, not release evidence. |
| Development impact runs | 163 pass / 9 fail; then 103 pass. Wider run 332 pass / 1 fail. | Old Shadow summary assertions and a lock-wait snapshot barrier were corrected; the latter now checks actual PostgreSQL blocking PIDs/locks. Old exact expert usage assertion was updated. |
| Pre-final targeted | 376 pass in 75.98 s | Earlier development snapshot, superseded by the frozen run below. |
| Latest health/executor/promotion check | 164 pass in 21.39 s | Included lifetime hard-event lookup, receipt invalidation and actual opened-store diagnostic. |
| Final-matrix RED | 395 pass / 3 fail in 73.99 s; exit 1 | `2026-11-01-m3-task8-targeted-red.xml` and `.log`: old exact Shadow summary dictionaries omitted new structured fields. |
| Parent backend RED | 707 pass / 4 fail / 56 skip / 578 deselected in 18.39 s | `2026-11-01-m3-task8-parent-backend-red.xml` and `.log`: same three assertions plus `repository=object()` in runtime wiring fixture. Not full integration qualification. |
| Scoped correction | 22 pass in 0.38 s | `test_shadow_usage.py` and `test_expert_cli.py`; production behavior was not weakened. |
| Parent health supplement | 60 pass / 0 failure/error/skip in 10.73 s | Parent-reported independent unique-DB run, provisional rather than an independent release campaign. |
| Parent expanded non-distributed GREEN | 711 pass / 56 skip / 583 deselected in 13.96 s | Parent-reported supplemental check; the skipped PostgreSQL-dependent cases mean this cannot substitute for the frozen full-services matrix. |
| Frozen targeted | 407 pass / 0 failure/error/skip in 74.75 s; exit 0 | `2026-11-01-m3-task8-targeted.xml` and `.log`; XML suite time 74.746 s. |
| Frozen full backend | 1350 pass / 0 failure/error/skip in 235.36 s; exit 0 | `2026-11-01-m3-task8-full.xml` and `.log`; XML suite time 235.346 s. One pre-existing collection warning for helper `TestAgent` with a constructor. |

Final targeted database: `task8_final_targeted_20261101_b62e`; full database: `task8_final_full_20261101_c84b`. Source/tests did not change between these final runs. Both final databases and the final-matrix RED database were confirmed absent after their exit traps.

Evidence paths are under `python/tests/distributed/evidence/`. SHA-256 identities:

| XML | SHA-256 |
| --- | --- |
| `2026-11-01-m3-task8-targeted.xml` | `7682d880591cd3938753eab60d01120449232420699b0d071831345167c70473` |
| `2026-11-01-m3-task8-targeted-red.xml` | `d430836be174334cb7ec365fabd058ce5bd4f4e643e0dd231e741cd0ffb572c8` |
| `2026-11-01-m3-task8-parent-backend-red.xml` | `4c608575d137b4ed1398c585aac462527873b1f192e391a464984be9783be1da` |
| `2026-11-01-m3-task8-full.xml` | `849e8241e224fc1d2fd6de077835f10cfc26523aac3d04cdd6d4b26a378e5d31` |

A detached shell launcher failed to start an earlier test process (empty output); it was not counted as a test pass. Final runs use a detached `subprocess.Popen` launcher with observed output/exit markers and database cleanup.

Final targeted matrix, from `python/`:

```bash
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest \
  tests/distributed/test_policy_health.py \
  tests/distributed/test_instrumentation.py \
  tests/distributed/test_worker.py \
  tests/distributed/test_shadow_worker.py \
  tests/distributed/test_shadow_usage.py \
  tests/distributed/test_policy_assignment.py \
  tests/distributed/test_promotion_schema_upgrade.py \
  tests/distributed/test_promotion_repository.py \
  tests/distributed/test_expert_engine.py \
  tests/distributed/test_expert_repository.py \
  tests/distributed/test_expert_cli.py \
  tests/distributed/test_runtime_schema_startup.py \
  tests/distributed/test_schema_migration.py \
  tests/distributed/test_promotion_contracts.py \
  tests/distributed/test_executor.py -q --tb=short \
  --junitxml=tests/distributed/evidence/2026-11-01-m3-task8-targeted.xml
```

Full backend command:

```bash
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python -m pytest \
  tests -q --tb=short \
  --junitxml=tests/distributed/evidence/2026-11-01-m3-task8-full.xml
```

## Evidence and Limits

- Data role: `test_fixture`; generated health-receipt fixture details explicitly carry `evidence_role=test_fixture` and `release_eligible=false`.
- No formally eligible JudgeV3 campaign currently exists. No eligible calibration/formal-holdout/harness qualification receipts were fabricated, and no real release was qualified.
- External model requests: 0. External model charge: USD 0. Fixture Decimal costs exercise arithmetic only; they are not measured provider expenditure. Actual Run cost remains unknown when its evidence is incomplete.
- These operational guardrails are deterministic reliability checks, not evidence of statistically significant educational improvement.
- The server diagnostic checks the known execution store boundary; it is not a claim of OS-level sandboxing or proof against every possible side effect.
- Old M3 rows lacking decision evidence remain unknown after migration. Historical immutable health windows are preserved, not rewritten into newly qualified gates.
- Process counters are process-local and restart-sensitive; authoritative persisted-count gauges are separate. Known-cost histograms omit unknown costs rather than counting them as zero.
- Docker was unavailable; no Docker or Compose runtime verification is claimed. Task8 does not add Task9 read-only Ops views or production hosting.
- Final independent spec review and code review are performed by the parent workflow after this new implementation commit. This report is implementation evidence, not those review approvals.

## Completion Checklist

- [x] Observation, matching window, deterministic evaluator and atomic rollback implemented.
- [x] Signed injection, honest usage/decision counters, real server permission hook and receipt invalidation implemented.
- [x] CLI/metrics and real explicit old-schema migration implemented.
- [x] Red evidence preserved; scoped assertion corrections pass.
- [x] Frozen targeted verified with 407 pass and no source changes.
- [x] Frozen full backend verified with 1350 pass and no source changes.
- [x] Final XML identities checked; sensitive configuration and parent-owned files excluded.
- [x] Task8-only implementation and evidence prepared for the new commit containing this report.
- [ ] Parent independent two-stage review, intentionally pending after implementation handoff.
