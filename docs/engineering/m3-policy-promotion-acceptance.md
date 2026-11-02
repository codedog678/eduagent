# M3 Trusted Policy Promotion Acceptance

## 当前结论

Task 10 的实现、fixture-only 验证、Compose 动态 smoke 与远程 CI 已完成工程
验收闭环。正式 rehearsal 尚未获得发布资格，原因是当前工作区没有可用的真实
`state=eligible`、Judge v3、`simulation=false` campaign，也没有为该 campaign
确认匹配的模型凭据。

这不是 Task 9 的验收结论。Task 9 仍保持未完整验收，本轮按用户授权跳过。

## 已完成证据

| 项目 | 结果 | 证据角色 |
| --- | --- | --- |
| 真实 PostgreSQL/Redis 多进程 promotion integration | 通过；含 SIGKILL、binding 保持、自动回滚、迟到 observation | `test_fixture` |
| policy-health 独立轮询配置 | 聚焦单测通过 | implementation test |
| Ops 新进程过滤 | 聚焦单测通过 | implementation test |
| rehearsal driver pre-write rejection 与七文件合同 | 聚焦单测通过 | implementation test |
| Compose/CI 动态接线 | GitHub Actions Compose smoke 通过并归档结构化证据 | `test_fixture` |
| 正式 eligible campaign rehearsal | 未执行 | blocked by external prerequisite |

fixture evidence 均必须保持 `release_eligible=false`，model calls 为 0 时不得描述为
新模型评估。

## 2026-11-02 验证矩阵

| 命令/范围 | 结果 |
| --- | --- |
| `pytest tests -m "not distributed_integration"` | 850 passed，56 skipped |
| distributed + run/expert/promotion failover | 1537 passed；JUnit `/tmp/eduagent-m3-junit.xml` |
| review-driven registry/Shadow latency 回归 | 5 passed |
| promotion driver/process/contract 聚焦测试 | 33 passed |
| `npm run build` | 通过 |
| `playwright e2e/ops.spec.ts` | 54 passed（desktop + mobile） |
| `docker-compose --profile distributed config --quiet` | 通过 |
| Compose 动态 smoke | GitHub Actions 通过；进程注册、真实 Run、Ops/Trace/Expert 查询和 worker loss 均通过 |
| `git diff --check` / Python compile | 通过 |

静态复审覆盖 19 个文件、约 2589 行变更。首轮发现的 token argv、用量来源、
分页、完整 audit chain、并发发布、CI 扫描后上传、Quick Start secret 持久化、
真实 registry 和 Shadow queue latency 测试缺口均已修复；复审后无剩余 P0-P2。

## 远程 CI 证据

- Source commit：`f8b8e3c836c00649825ceab53ce0fd50c0549de1`
- Workflow run：
  [CI #41457794154](https://github.com/codedog678/eduagent/actions/runs/41457794154)
- 执行时间：`2026-11-02T13:59:45Z` 至 `2026-11-02T14:13:51Z`
- 结论：`success`
- Jobs：`backend`、`frontend`、`package`、`compose-smoke`、
  `distributed-integration` 全部成功
- `distributed-integration` 测试步骤运行约 12 分 38 秒，随后成功生成并上传
  fixture-only promotion evidence
- Artifacts：
  - `distributed-test-evidence`，artifact id `13147604229`，22485 bytes
  - `compose-smoke-evidence`，artifact id `13147736604`，1202 bytes

上述 artifact 均来自 CI fixture/控制面验证，明确
`release_eligible=false`，不能替代正式 campaign qualification 或真实模型评估。

## 外部前置条件

1. 一个未被消费且可重新验证的正式 campaign；
2. `simulation=false`、`mode=qualification`、`state=eligible`；
3. 当前 Judge v3 protocol、runtime hash、source revision 和 calibration identity；
4. 配置好的 provider/model credential；
5. rehearsal PostgreSQL/Redis、独立 secret 与 fault injection 显式开关。

任一条件缺失时 driver 在控制面写入前 fail closed，不生成正式证据目录。

## 前置条件探测

`2026-11-02T10:16:19Z` 使用不存在的 campaign 路径执行同一 driver 参数面，
结果为 exit `2`：

```text
rehearsal rejected [campaign_missing]: required campaign file does not exist
```

探测后的 `--output` 目录不存在；API URL 使用不可达端口且未发生连接，因此请求数
和模型调用数均为 0。该探测只证明缺失前置条件会在写入前拒绝，不是 formal
rehearsal。

## 正式验收命令

```bash
python tools/run_policy_rehearsal.py \
  --api-url http://127.0.0.1:8890 \
  --ops-token env:OPS_API_TOKEN \
  --campaign "$ELIGIBLE_CAMPAIGN" \
  --actor "$PROMOTION_COMMAND_PRINCIPAL" \
  --candidate-basis-points 5000 \
  --healthy-runs 48 \
  --failure-runs 20 \
  --output docs/engineering/evidence/m3-policy-rehearsal
```

通过条件：Shadow isolation receipt；Canary 至少 20/20 匹配样本；显式 candidate
commit failure 达冻结阈值；一个自动 rollback audit；旧 Run binding 保持；新 Run
使用回滚后的 stable；七个 artifact 完整且敏感值扫描通过。

## 限制

当前结论只支持“实现和 fixture 控制面验证通过”。它不支持“正式策略可发布”、
“真实模型效果提升”或“学生学习效果提升”。本地未执行 Docker 动态 smoke；
该缺口已由绑定 source commit 的 GitHub Actions Compose job 补齐，但仍不等于
正式 rehearsal。
