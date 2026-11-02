# Task9 完整消费链修复：中断后的新实现者接续

你是新的实现者，只负责完成 Task9 修复、验证和 NEW freeze。
前代理 `arun_6ae7dc7051536906a0739671` 已明确 killed，不存在授权你等待它或
重复启动它的问题。用户已批准设计、fresh implementer → NEW freeze →
fresh WHOLE SPEC → PASS 后 fresh WHOLE CODE，以及 NEW commits、不 push。
不要再次询问设计、许可或执行方式。阅读 brainstorming/writing-plans，按已
批准方案接续；不得自行验收或启动 SPEC/CODE/Task10/Agent50/真实模型请求。

## 现场事实

唯一可写源码树 `/Users/bytedance/Documents/trae_projects/eduagent-m3`，
branch `feature/m3-trusted-policy-promotion`，HEAD
`85c2759d54fd55691cf69d98df91c81ad9caf65b`，parent
`c45bf55e1aa5753eb1d83ad8a3eb60487b741474`。85c 仅归档旧失败，产品仍 c45。
Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f`。
主 `eduagent` HEAD `2ff803c968d64741d149e5a1ce88a823d4d32422` 且 clean；
主源码/index/.venv 只读，不 amend/push/git config/跳 hooks 或签名。

中断保留：已修改 `python/core/distributed/ops_queries.py`，18 行 diff；
新增未跟踪 `python/tests/distributed/test_ops_complete_chain.py`。
补丁将 `_project_health_sources` 改为 classmethod，在 `_consumed_canary`
返回前复用叶校验以验证精确 Canary receipt，自身失效即断开完整依赖链。
请继承并核对，不丢弃这些代码，不假定已经通过。
新增测试覆盖 30 poison、缺/错/旧引用、合法双来源、历史/local/cutoff/
malformed latest。此前 /tmp 原始结果目录和隔离环境已丢失：
`/tmp/m3-task9-chain-fix-d3d669c4-4da2-41c0-8da8-91e9c4c92192`
与 `/tmp/eduagent-m3-patched-runtime` 均不存在，没有完整结果或 NEW commit。
不能把前代理执行宣称为你执行，不能为丢失材料补造时间、运行次数或费用。
记录中断与证据丢失边界，并保留当前补丁/新测试初始字节及摘要。

## 权威规格和失败

完整读：
- `docs/superpowers/specs/2026-10-30-trusted-policy-promotion-design.md`
- `docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md`，Task9 六步
- `docs/superpowers/reports/2026-11-02-m3-task9-chain-spec-failure.md`
- 原始目录 `docs/superpowers/reports/task9-chain-spec-failure-evidence/`
- 既有 F1/C1/S1-S3 实施与独立失败档案，不能覆盖/重写任何历史文件。

本次唯一 S1-R/P2：Active approval 精确引用无效 Canary receipt 时，leaf
Canary 已 rejected，但 Shadow 仍 passed/consumed_chain。11 种 poison
是同一根因，不是 11 个独立缺陷。原有效 integrity47=42PASS/5FAIL、
metadata-v2 17=11PASS/6FAIL、生产 referenced poison 双视口=0PASS/2FAIL。
合法 Active 双来源、合法 Canary 的独立 Shadow 历史、20/20 和
21/21 循环 Decimal 必须保留。无效引用不能替换为另一合法 latest leaf；
本地/历史/latest未知 approval 遮蔽/transition cutoff 规则维持。
Ops 仅 REPEATABLE READ READ ONLY，有界查询，不调用授权/command/evaluator
写入口或进行无界重放，不通过前端过滤掩盖根因。

原失败 archive retained-manifest SHA
`6c5abd6d891154cb090b2d17db5ea4f693df56374e2c9c650589cf3159e8d1f3`，
398 raw payload SHA
`8cb8c5a30a5e3c4c15067378585a4419f0853dbc033e0b03f02e04e0116ce962`。
原 source353 SHA
`1dd2eb166f857df67ad0b513540d7ee8e12f5e47c1f74354d2832029521baf65`。
archive 中有原安全 runner/probes/production fixture，可复制到新 UUID
目录并修改 OWN/ROOT/HEAD/labels/port/cache。禁止直接运行固定旧 runner
或向 golden archive 写入。原 0 收集和 metadata 2 个 FK fixture 失败
保留为无效尝试，不能当有效 RED/PASS。

## 环境恢复

新 UUID `/tmp` 作为自有执行目录。当前 55432/56379/36730/36731 均关闭；
旧 PG/Redis 服务也未保留。可以重建仅 loopback 的测试基础服务（不 Docker）：
- PG16 bin `/opt/homebrew/opt/postgresql@16/bin`，每 invocation 新 UUID DB，
  finally drop，只设置 `DISTRIBUTED_TEST_DATABASE_URL`，不触碰生产 URL。
- Redis `/opt/homebrew/bin/redis-server`，只清本次 exact UUID keys；
  禁 flush/prefix 删除。新的临时服务应与主/生产目录完全隔离。
- 若创建测试 PG/Redis 服务，用 `/tmp` 之外可复用的明确临时父目录仅在必要时
  保存启动说明，不把服务数据提交。如父侧需要后续审查复用，可保留明确标识
  的 loopback 服务并交接 PID/data-dir/port；本次所有 DB/key/浏览器进程须清理。
- 主 venv 是 Python3.11.17，可读 `pyvenv.cfg` 找底层解释器：
  `/Users/bytedance/.local/share/uv/python/cpython-3.11.17-macos-aarch64-none/bin/python3.11`。
  创建新的隔离项目 runtime，不修改主 venv，不向源码安装 editable 包。
  保持 pyproject/dev/build 与 requirements 交集，修复 floor：
  anyio>=4.14.2，certifi>=2026.10.18，pydantic-settings>=2.14.2，
  setuptools>=84.1.0，starlette>=1.3.1；记录实际解析依赖与 pip check。
  可恢复 `/tmp/eduagent-m3-patched-runtime` 供后续阶段用，主源码只读。
- Node20.19.5 binary 仍存在：
  `/Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node`。
  M3 `frontend/node_modules` 仍存在；实体复制到自有 frontend，不 symlink 回源。
  维持 Vite7.3.7/plugin5.2/React18.3.1/Playwright1.64.1/TS5.9.3 lock。
- Browser 前读 TRAE-browseruse。新 ports/截图/trace，不写源 Vite 缓存。
  Docker 不可用不安装，不声称 CI/容器实跑。模型零请求。

## 执行与证明

1. 开始前快照两树（tracked、全部新增 source/tests、index、主 venv、源
   Vite cache）及本次中断补丁。核验旧 archive 原字节仍一致。
2. 当前 patch 已存在，因此基线 RED 在自有 tmp 的 Git 冻结基线副本跑：
   `git archive 85c2759 -- python frontend tools` 解到自有目录；
   明确 BASELINE_REPLAY，逐文件证实产品 source353 等于原 frozen Git blob，
   不 reset/restore 工作树。复制原有效 probes 和新增回归到自有基线，
   记录额外测试路径，不冒充旧版本本来已有该测试。
   实际重跑原 integrity47/metadata-v2 17/生产引用 poison 双视口正确性
   RED，合法对照不受 fixture FK/setup错误干扰。保留所有有效/无效尝试。
3. 完成最小修复及真正 PG 完整 GET 回归。精确 receipt 自身 gate/status/
   四维/issuer/model/role/严格版本/部署/window/threshold/evidence/time/
   sample_count/Decimal cost/bounded frozen observations 全有效。
   完整 canonical command 全8字段/audit/approval/required/actor/reason 闭合。
   错/缺引用、同错误声明、另一个合法 receipt 存在不能恢复断链 green。
4. 最终独立运行 new test、integrity47、metadata-v2、完整 backend、
   关系/API、Node20 build、全 UI 双视口；真实 PG 生产 current/history/
   synthetic malformed/genuine malformed/genuine valid/referenced poison
   六场景双视口均正确性 PASS。实际看关键截图，HTTP资产逐字节匹配 dist，
   GET-only/privacy/RunTrace immutable binding/legacy NULL 保留。
5. 最终矩阵 before/after source 全集包含新增测试，并对最后 freeze Gitblob
   核验；证据不循环加入 source hash。旧失败档案保持原样，新增 raw
   XML/log/命令/UTC/runtime/protocol/threshold/source/角色/request/
   failed/interrupted/cost/manifest 可复算，重叠 suite 不加为独立样本。
   没装表 HTTP 计 unknown；新模型0/费用0，fixture cost 另标。
6. 精确资源核验：本次各 DB/key/browser/worker/cache 清理，主树与 venv
   当前 before/after 不变；不得把重建环境前后跨断点元数据声称全等。
   保留供复审用的隔离 runtime 与明确共享测试服务（如有）并交接。
7. 核对所有 staged、秘密和历史保留，stage 具体本次路径，HEREDOC
   NEW commit。禁 amend/push/git config/跳 hooks。冻结实现不是验收。
8. 完整结果先写 `/tmp/m3-task9-complete-chain-fix-result.md`，同字节报告
   与全部本次 raw（包括中断事实、有效 RED、无效尝试）归档到新 repo
   docs/evidence 目录，防下一次 /tmp 丢失；不要覆盖旧 archive。
   给实际 HEAD/parent/source count/SHA/manifest/文件清单/各 suite计数/
   命令时间/资源/环境启动交接/未执行限制，再最终回复。

父侧随后另启新的 WHOLE SPEC（Task8 acceptance 至你实际 freeze 的整个
Task9）和 PASS 后 fresh WHOLE CODE。你不能自行启动或认领它们。
