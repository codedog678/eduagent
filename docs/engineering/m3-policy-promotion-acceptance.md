# M3 Trusted Policy Promotion Acceptance

## 当前结论

Task 10 的实现与 fixture-only 验证已完成到可执行阶段；正式 rehearsal 尚未获得
发布资格。原因是当前工作区没有可用的真实 `state=eligible`、Judge v3、
`simulation=false` campaign，也没有为该 campaign 确认匹配的模型凭据。

这不是 Task 9 的验收结论。Task 9 仍保持未完整验收，本轮按用户授权跳过。

## 已完成证据

| 项目 | 结果 | 证据角色 |
| --- | --- | --- |
| 真实 PostgreSQL/Redis 多进程 promotion integration | 通过；含 SIGKILL、binding 保持、自动回滚、迟到 observation | `test_fixture` |
| policy-health 独立轮询配置 | 聚焦单测通过 | implementation test |
| Ops 新进程过滤 | 聚焦单测通过 | implementation test |
| rehearsal driver pre-write rejection 与七文件合同 | 聚焦单测通过 | implementation test |
| Compose/CI 静态接线 | 已实现，待 Docker CI 动态执行 | validation required |
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
| Compose 动态 smoke | 本机未执行；等待 GitHub Actions |
| `git diff --check` / Python compile | 通过 |

静态复审覆盖 19 个文件、约 2589 行变更。首轮发现的 token argv、用量来源、
分页、完整 audit chain、并发发布、CI 扫描后上传、Quick Start secret 持久化、
真实 registry 和 Shadow queue latency 测试缺口均已修复；复审后无剩余 P0-P2。

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
“真实模型效果提升”或“学生学习效果提升”。Docker 在本地不可用时，Compose
动态结果必须等待 GitHub Actions，不能以 YAML 静态检查替代。
