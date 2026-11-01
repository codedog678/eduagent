# M3 正式资格前提核对

核对时间：`2026-11-01T11:24:40.914835+00:00`。
此记录为只读前提核对，不是正式评测、资格回执或受控演练结果。

## 当前归档事实

仓库 `docs/evals` 下只找到一份 campaign 状态文件：
[20261029-exploratory-01](../../evals/rsi-campaigns/20261029-exploratory-01/campaign/campaign.json)。

| 字段 | 实际值 | 对正式演练的影响 |
| --- | --- | --- |
| `config.mode` | `exploratory` | 不授予 promotion 或 release eligibility |
| `protocol.schema` | `eduagent.gepa.v2` | 不能替代当前 Judge v3 冻结协议 |
| `state` | `exploration_completed` | 表示探索完成，不是资格完成 |
| `config.simulation` | `false` | 历史运行具有模型证据，仍不改变探索数据角色 |
| `holdout_receipt_hash` | `null` | 没有已消费并通过的正式留出回执 |
| `harness_hash` | `null` | 没有与该 campaign 绑定的 Harness 资格证据 |

本次直接调用当前 `Campaign.require_qualification()` 的模式检查，
输入为归档 campaign 的实际 `config`，得到：

```text
qualification_rejected=exploratory campaign cannot grant promotion or release eligibility
```

检查未打开或修改历史 SQLite 账本，没有注册策略、签发 token、提交请求或
调用外部模型。它证明该 campaign 被模式门禁拒绝，不表示其它资格检查已通过。

## 配置事实与范围

只输出凭证是否存在，未输出凭证值、服务地址或私有配置：

- 隔离 `eduagent-m3` 的有效配置：provider 为 `auto`，四种聊天 provider 的
  凭证均未配置，promotion 关闭，发布密钥长度不满足启用条件。
- 主工程 `eduagent` 的有效配置：provider 为 `deepseek`，DeepSeek 凭证存在。
  主工作树保持 `2ff803c` 且干净。

因此不能笼统声称“项目没有模型密钥”。主工程凭证存在仅证明配置可见，
没有验证账户额度、供应商可用性或该凭证的发布授权；本次无需发请求验证。
隔离工作树的运行配置可以另行准备，但配置不能替代资格证据。

## 尚缺的正式前提

正式演练需要与当前运行代码、模型和 Judge v3 协议绑定的 qualification
campaign：独立校准通过，正式留出的一次消费和失败/中断记录完整，Harness
资格通过，账本与冻结证据可重算。归档的探索结果与开发重放不能提供这些回执。

后续受控演练入口应在上述前提不满足时先拒绝，再记录实际缺项、尝试命令、
时间和已完成的工程测试。fixture-only 集成测试可以继续验证分流、隔离、
接管和回滚，并须标记 `evidence_role=test_fixture`、`release_eligible=false`。
