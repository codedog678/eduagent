# Task9 最新回执排序修复与重新冻结

这是已授权的 Task9 实现修复，不是新设计。完整设计和逐任务新实现者/
freeze/fresh SPEC/PASS后fresh CODE顺序已经批准，不再请求实现确认。
本轮只实现与冻结，父侧负责新的独立全任务复审。

## 身份与范围

- 唯一可写源码 worktree `/Users/bytedance/Documents/trae_projects/eduagent-m3`，
  branch `feature/m3-trusted-policy-promotion`，
  starting HEAD `38f48d763b4a9599aa215f98a2cba1b32003b1e7`。
- primary `eduagent`始终只读；Task10尚未启动；Agent50继续暂停，
  无真实模型请求、无Docker安装。
- 原始报告 `/tmp/m3-task9-spec-review-result.md` 全文必须读；
  原始独立证据 `/tmp/m3-task9-spec-independent/`，
  原实现交接 `/tmp/m3-task9-implementer-result.md`。
- 原冻源报告/manifest/log/XML必须保留原bytes，不覆盖或重贴通过。
  新报告+新证据目录归档本轮修复和独立FAIL。

## 已真实复现的 F1 / P2

`ops_queries.py:339–345` 按 issued_at DESC、receipt_id DESC选最新gate；
发布权威 `promotion_repository.py:935–947` 按 issued_at DESC、
created_at DESC、receipt_id DESC，因此Ops可能显示已失效旧passed。

同policy/protocol/runtime/source、同gate_type、同issued_at：

- passed receipt UUID `ffffffff-ffff-ffff-ffff-ffffffffffff`，
  created_at2026-10-30T00:00:00Z；
- 后追加failed UUID `00000000-0000-0000-0000-000000000001`，
  created_at2026-10-30T00:01:00Z。

发布 `_bound_gate_receipts` 拒绝formal_holdout，但GET detail/真实PG
production desktop/mobile都显示旧passed。该反例没有写权限绕过；
Ops可信证据表面false-positive本身足以阻塞。

## 必须完成

1. 最小修复Ops排序，与发布权威三键保持一致；不重写门禁、不调用
   CommandService、不修改已验收晋级语义或放开任何绑定。
2. 添加有意义真实PG回归：同issued_at、created_at不同、UUID反序的
   newer failed和unknown覆盖passed；与权威拒绝结果对照。
   可补同issued_at/created_at的receipt_id第三键确定性及newpassed恢复显示；
   保持future issued与错误protocol/runtime/source绑定不成为当前passed。
3. 先新回归在未修复源上跑有效RED，保留原始XML/log/源摘要；
   修复后GREEN；全Task9 API、完整backend、Node20 production build、
   desktop/mobile40 browser。无UI代码变更不豁免页面验证；
   尽量复用reviewer真实PG live harness重跑F1两个viewport，证明页面改为
   failed/unknown，不能只route-mock改fixture求绿。
4. 归档本次独立SPEC FAIL全文与最小充分原始证据（F1 PG/API和两个viewport、
   常规独立94/40/live4pass、独立build与有效探测代码/runner/liveharness/
   screenshots），保留SHA/provenance。原manifest可原样保存，但新的
   retention manifest须说明保留文件范围，不能对已经清理未保留的依赖、
   source副本或临时物主张全量retained。不要保留无关cache/node_modules。
   独立review执行隔离例外必须如实保留说明，不重写为完全未触碰ignoredmtime。
5. 新实现报告明确Task9尚未接受、F1原因/修复、exactcommands/counts/hash/
   角色/限制/cleanup。新evidence目录与原task9-ops-evidence分离。
   尽量每关键run记录source digest before/after，避免仅最终一次digest
   支撑所有历史运行；SHA不含报告/evidence循环依赖。
6. 主.venv不改，新依赖环境/CI/Task10仍下一步工作。只own必要源/回归/
   报告/证据；保持primary clean和原38f证据完整。
7. 独占DB、stream、port/cache；成功清理无关临时资源，失败材料保留。
   NEW commit，禁止amend/push/git config/hook或签名绕过。
   先git status/diff/log检查，stage具体自有路径，ignored evidence可-f。
8. 最终先写 `/tmp/m3-task9-gate-order-fix-result.md` 完整交接，frozencommit/
   parent、源与原始XML/截图manifest哈希、命令/计数/cleanup/限制；
   再通知父侧。父侧新fresh全Task9 SPEC，PASS后fresh CODE，不能自称验收。

## 本机与隔离

Python `/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python`，
PYTHONPATH=m3/python、TZ=UTC。
PG16 127.0.0.1:55432 postgres无密码，
bin `/opt/homebrew/opt/postgresql@16/bin`；每invocation新unique DB、EXIT dropdb；
只DISTRIBUTED_TEST_DATABASE_URL，不动生产DATABASE_URL。
Redis56379/0自有streams。
Node20.19.5已有：`npm exec --yes --package=node@20.19.5 -- node ...`，
browser工具先读skill。所有新cache/JUnit/screenshot写own/tmp或新证据目录。
Vite验证若用tmp副本，node_modules必须实体复制而非指向M3的symlink，
连config bundle .vite-temp也须tmp；不要改原node_modules的ignoredmetadata。
不可dump env/credentials/进程参数/未脱敏secret日志。
