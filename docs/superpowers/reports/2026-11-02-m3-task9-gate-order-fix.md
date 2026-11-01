# Task9 Gate 排序窄修与重新冻结

日期：2026-11-02。角色：SPEC FAIL 后已授权修复实现者，**不是 Task9 验收者**。
本轮完成实现与工程复验；Task9 尚未接受。父侧必须重新 fresh 全 Task9 SPEC，
只有 PASS 后才 fresh CODE。Task10 未启动，Agent50 继续暂停。

## 1. 范围与事实

- 唯一写源码 worktree：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
- 分支：`feature/m3-trusted-policy-promotion`。
- 起点/父提交：`38f48d763b4a9599aa215f98a2cba1b32003b1e7`，起点 clean。
- primary `eduagent` 只读，HEAD `2ff803c968d64741d149e5a1ce88a823d4d32422`。
- 沿用原 design、Task9 六步与 `/tmp/m3-task9-gate-order-fix-brief.md` 的已批准修复授权。
- 原独立权威结论为 F1/P2 SPEC FAIL，全文原样留在
  `task9-gate-order-fix-evidence/independent/m3-task9-spec-review-result.md`。
- 本报告在 NEW commit 前写入，避免 commit 自引用；完整 frozen commit、父提交、
  manifest/report SHA 和提交后核验写盘到 `/tmp/m3-task9-gate-order-fix-result.md`。
- 不修改原 `task9-ops-evidence/` 和原 Task9 报告，不升级依赖，不改主 `.venv`，
  不安装 Docker、不请求真实模型、不扩展 Task10 或已验收晋级语义。

## 2. F1 原因与修复

发布 authority `_bound_gate_receipts` 按
`issued_at DESC, created_at DESC, receipt_id DESC` 选最新绑定 gate；
原 Ops 漏掉 `created_at DESC`。同 issued_at 的旧 passed UUID 较大、
后追加 failed/unknown UUID 较小时，发布权威正确拒绝，Ops 却可能展示旧 passed。

产品只改 `python/core/distributed/ops_queries.py` 一行：补入 `created_at.desc()`。
不调用 CommandService、不改门禁资格、不放开 policy/protocol/runtime/source 绑定，
不改 API 合同或 UI。前端继续展示后端真实投影，没有 route mock 修饰 F1。

测试只扩展 `python/tests/distributed/test_promotion_ops_api.py`，新增 9 项：

- failed/unknown × created_at/receipt_id tie，共 4 项；同 issued_at，
  created_at 分支故意让旧 passed 为 `ffffffff-ffff-ffff-ffff-ffffffffffff`，
  新非 passed 为 `00000000-0000-0000-0000-000000000001`。
- 每项先核对发布 authority missing formal_holdout、accepted 空，再核对 GET detail；
  随后追加 created_at 更晚但 UUID 更小的 passed，核对 authority 与 Ops 均恢复。
- policy/protocol/runtime/source 错绑定与 future issued_at 共 5 项，
  证明较新错误/未来 pass 不会在 Ops 成为当前 pass。
- `_bound_gate_receipts` 私有 helper 自身不筛 future issued_at，未来签发测试仅核对
  Ops 既有过滤；不把 helper 扩大解释为完整发布服务资格校验。

所有测试回执标为 `test_fixture`、`release_eligible=false`。
工程 PG/HTTP/browser 证据不代表真实模型、正式 holdout 或学生学习效果。

## 3. RED、GREEN 与本轮复验

以下计数均重新解析 raw XML 的 suite/testcase/F/E/S 子节点，不靠摘要转述。

| 本轮材料 | Tests | Failures | Errors | Skip | 解释 |
| --- | ---: | ---: | ---: | ---: | --- |
| red-gate-order.xml | 9 | 5 | 0 | 0 | 初轮含 1 项错误的 future-helper 假设，完整保留，不把该项算产品缺陷 |
| red-gate-order-valid.xml | 9 | 4 | 0 | 0 | 有效 RED：2 项同 issued_at 假 passed；2 项后续恢复排序失败 |
| green-gate-order.xml | 9 | 0 | 0 | 0 | 相同有效回归，只改产品一行后 GREEN |
| all-api.xml | 96 | 0 | 0 | 0 | Task9 原 68 + 新增 9 + 既有 Ops 19 |
| full-backend.xml | 1684 | 0 | 0 | 0 | 完整 backend，322.62s，1 个既有 TestAgent collection warning |
| independent-probes.xml | 8 | 0 | 0 | 0 | 原独立 7 项 probe + 原 F1 PG/API probe，全部重跑 |
| ui-40.xml | 40 | 0 | 0 | 0 | 原 desktop/mobile 完整浏览器回归 |
| live-failed.xml | 6 | 0 | 0 | 0 | 原真实 PG live 4 项 + failed F1 两个 viewport |
| live-unknown.xml | 2 | 0 | 0 | 0 | unknown F1 两个 viewport |
| build.log | 不适用 | 不适用 | 不适用 | 不适用 | 实际 Node20 `npm run build`，tsc + Vite production PASS |

有效 RED 的 Ops 源字节等于起点 38f48d7；有效 RED 与 GREEN 的全部
351 个 tracked Python/frontend 源文件之间，仅 `ops_queries.py` 不同。
每次关键 run 保留 `*-before.json`/`*-after.json`，源摘要、原 Task9 bytes、
primary HEAD/status/source、保护目录 mtime 在该 run 前后均一致。
首轮 RED 到清理终态也核对 primary/原证据/保护 mtime 一致。

- 初轮 RED 源摘要：`099415d61a8c457bbb0d9adc80fa469038ac4e740f0217737d49117bec886bf1`。
- 有效 RED 源摘要：`2e9cc3f0455eae9f78a601f97a2d6b2e60035830282ed64c22a75bdcb40907e2`。
- GREEN/全部复验源摘要：`8561cf7f84c2ed1f30e548ccb5adba0ed891cca2b9efef3d9c0ad40bb91ea582`。
- 算法：路径到 SHA-256 映射，按路径排序 compact ASCII JSON，再 SHA-256；
  source 只含 tracked `python/` 与 `frontend/`，不含 report/evidence。

## 4. 执行命令

命令在 M3 中执行，pytest runner 自行进入 `M3/python`。这些是本轮运行命令留档；
**不能直接重跑覆盖冻结证据**。后续 reviewer 必须使用新的独占目录/DB/port，
调整 runner 输出目录后执行。RED 是历史未修复源证据，不应在冻结源上反向编辑重跑。

```bash
E=/Users/bytedance/Documents/trae_projects/eduagent-m3/docs/superpowers/reports/task9-gate-order-fix-evidence
OWN=/tmp/m3-task9-gate-order-fix
PY=/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python

# 以下三次分别在初轮测试、修正未来 helper 假设、产品一行修复后执行。
bash "$E/pytest-runner.sh" red-gate-order tests/distributed/test_promotion_ops_api.py \
  -k 'gate_tie_order or gate_order_excludes' -q -s
bash "$E/pytest-runner.sh" red-gate-order-valid tests/distributed/test_promotion_ops_api.py \
  -k 'gate_tie_order or gate_order_excludes' -q -s
bash "$E/pytest-runner.sh" green-gate-order tests/distributed/test_promotion_ops_api.py \
  -k 'gate_tie_order or gate_order_excludes' -q -s
bash "$E/pytest-runner.sh" all-api tests/distributed/test_promotion_ops_api.py \
  tests/distributed/test_ops_api.py -q
bash "$E/pytest-runner.sh" full-backend tests -q
bash "$E/pytest-runner.sh" independent-probes -c pyproject.toml \
  "$E/independent/test_independent.py" "$E/independent/test_gate_tie.py" -q

bash "$E/node-runner.sh" build build
bash "$E/node-runner.sh" ui-40 test e2e/ops.spec.ts --reporter=line,junit \
  --output="$OWN/playwright-ui"

# 各 server 在独立终端启动，startup complete 后运行 browser。
bash "$E/live-runner.sh" failed
env FIX_GATE_STATUS=failed bash "$E/node-runner.sh" live-failed \
  test --config=playwright.live.config.ts --reporter=line,junit \
  --output="$OWN/playwright-live-failed"
# 对 OWN/live-runner.pid 中本轮 PID 发 TERM，观察退出143和 EXIT dropdb 后：
bash "$E/live-runner.sh" unknown
env FIX_GATE_STATUS=unknown bash "$E/node-runner.sh" live-unknown \
  test live-e2e/gate-tie.spec.ts --config=playwright.live.config.ts --reporter=line,junit \
  --output="$OWN/playwright-live-unknown"
# 同样 TERM 本轮 runner，等待清理完成。

env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/capture-isolation.py" frontend
env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/provenance.py" snapshot cleanup-check-before
env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/capture-isolation.py" cleanup
env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/provenance.py" snapshot cleanup-check-after
env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/provenance.py" manifest
# 正常 NEW commit 后只读核验，不再更新冻结目录：
env PYTHONDONTWRITEBYTECODE=1 "$PY" "$E/verify-freeze.py"
```

Python 3.11.17，PG16 `127.0.0.1:55432`；每次 pytest/live 新建唯一
`m3_t9_fix_*` 数据库，仅 `DISTRIBUTED_TEST_DATABASE_URL`，EXIT dropdb。
Redis 使用测试服务 `127.0.0.1:56379/0`；fixture/failover 使用 UUID stream，
原测试 finalizer 删除本轮 stream，不 FLUSH。

node-runner 内部精确执行 `npm exec --yes --package=node@20.19.5 -- node -e ...`，
build 分支 `spawnSync("npm", ["run","build"])`，用当前 Node 所在目录优先 PATH。
实际日志为 Node `v20.19.5`、Vite `7.3.7`；chunk-size warning 保留，不升级依赖。
缓存前缀均在 OWN；浏览器 skill 已先读取，再使用 Playwright/Chromium。

## 5. 真实 PG 生产页面与隔离

复用并窄调原 reviewer live harness：真实迁移后的 PG append-only 表、
真实 evaluator/rollback 事务、FastAPI OpsQueries、Starlette production dist。
没有 API route mock，不启动业务 worker/model。failed/unknown 两个 server lifecycle
均在 GET 和 desktop/mobile 页面显示新 UUID 的非 passed；发布 authority 都拒绝。
脚本先断言 authority，再保存 fixture，browser 再通过实际 HTTP 请求与 DOM 核对。

API 回归 NOW 为 2026-10-30；live 沿用 health helper NOW=2026-11-01，
仍是同 issued_at、相差 60 秒 created_at、反 UUID 的同一 F1 条件。
`live-fixture-failed.json`/`live-fixture-unknown.json` 留有 gate_projection、
missing/accepted、旧/新 Run 和 deployment/hash 对照。
failed/unknown 的全页及 detail desktop/mobile 共 8 张 F1 截图已逐张视觉检查：
failed 红色、unknown 灰色，不再显示旧绿色 passed。
常规 live 另外验证真实 rollback/health/audit、旧 Run pin、分页/filter reset 等。

前端验证副本使用 **实体** node_modules，未链接到 M3；外部依赖 symlink 数为 0。
除两个执行配置外，其余 29 个 tracked frontend 文件逐字节匹配 M3，
含 source/e2e/package/lock；配置仅改自有 cacheDir 和 33190 专用 port。
live 配置使用 33191；已保留修改后的 `execution-config/` 和 live 脚本。
原锁 SHA：`90dbc9aae2e41ba3fe968254330755f3e183959a735a64132ad7f3c9b2b55bb5`。
`frontend-isolation.json` 记录 6 个 dist 文件逐项 SHA：
combined `dee1c3dbd3260679fa5c5caaf53e0f4f9cd3fde47fccbed80ee976fefa58060f`。
dist/dependency 副本已清理；仅保留 dist 哈希和依赖位置检查，不声称保留依赖字节。
`prepare-frontend.sh` 是清理后恢复实体验证副本的配方，后续重跑必须另改输出目录。

## 6. Retention 与 Provenance

新证据目录：`docs/superpowers/reports/task9-gate-order-fix-evidence/`。
`manifest.json` 是本轮完整路径/SHA/raw XML 统计/逐 run 摘要清单，
自身排除以避免循环；每个 snapshot 不用最终一次摘要替代历史证据。

原独立 FAIL 与最小充分 raw 材料共 79 文件，`independent-retention.json`
列出 original path、archive path、SHA、bytes，并再次核对仍存原件字节一致。
保留 API F1、真实 PG 两 viewport 失败 trace/截图、94/40/live4 常规证据、
最终 isolated build、有效 probes/runners/live harness/config，以及失败历史 attempts。
原 `independent-manifest.json` 原样作为**历史材料**保存，不宣称其中已经删除的
node_modules/dist/cache/source副本仍全量 retained。

原 reviewer 首轮使用 node_modules symlink，触碰 M3 ignored `.vite-temp` mtime，
随后实体副本重跑的例外已在 FAIL §7 原文披露；本轮没有改写成“从未触碰”。
本轮独立从起点记录保护目录 mtime，不回写原目录以伪造恢复。

原 38f48d7 Task9 报告/evidence 的每个工作文件与 Git frozen bytes 相同，
其 19 份 XML 另行解析核对；未格式化、覆盖或将原 FAIL 重新贴成 PASS。
本轮及归档 independent 共 18 份 XML；GREEN 不掩盖初轮坏假设和有效 RED。
提交前检查源 diff/whitespace、新增路径和标准密钥模式，trace ZIP 也检查；
不保留生产数据库、真实凭据、无关缓存。该检查不等于全面安全资格审计。

## 7. 清理、限制与下一步

- 本轮 live 两个 runner 已主动 TERM，退出 143 是预期停服；server 退出已观察，
  EXIT trap dropdb 与 after snapshot 均完成，不是功能失败。
- `m3_t9_fix_*` 最终 PG 数据库数 0；33190/33191 listener 数 0。
- 自有 frontend/node_modules/dist、npm/py/pytest/Vite/Playwright cache 与 PID 文件
  全部清理，OWN 留空；不删除原 reviewer tmp、不停止共享 PG/Redis。
- Redis 只读 audit：`test:runs:*` 292 个（291 空）、
  `test:experts:*` 0、`eduagent:test:failover:*` 29 个（均空）。
  非零 last-generated ID 均早于本轮最早测试；没有本轮之后生成的 message ID。
  共享前缀不等于所有权，zero-ID 键无法归属，不对不确定旧键 DEL/FLUSH，
  也不宣称全局 Redis 已清空。fixture/failover 清理仍按原测试 finalizer 执行。
- 首次 housekeeping 错把共享 prefix 数必须为 0，当场失败且未删除任何资源；
  `cleanup-attempt.log` 保留错误及更正说明，最终 `cleanup.json` 记录只读 audit
  和自有 tmp 删除清单，不把这次错误当产品失败或隐藏。
- primary 源摘要/HEAD/clean 与主 `.venv`、site-packages、M3 `.vite-temp` mtime
  在所有关键 run 前后及整轮首尾保持一致；NEW commit 后再核对 Gitblob/workingbytes。
- 本轮是修复实现者的工程复验，不是 fresh 独立全 Task9 SPEC/CODE。
  不认领正式 model qualification、学生效果、Task10 系统演练或依赖安全升级。
- 不 amend、不 push、不改 git config，不绕过 hook/signing；只 stage 两个自有
  Python 文件、新报告和新 evidence（ignored 材料以具体目录 `git add -f`）。

父侧以新 frozen commit 重新安排 **fresh 全 Task9 SPEC → PASS → fresh CODE**。
该顺序通过前不能认领 Task9 acceptance，不能启动 Task10。
