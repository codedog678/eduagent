# 历史回顾后工程加固：冻结复测协议

运行源码 `111dca9`，机器可读版本、源码和数据摘要见 `run-protocol.json`。设计及实现：[工程加固边界](../../../engineering/harness-hardening-20261027.md)；此前修改：[历史回顾](../../../engineering/historical-change-log.md)。

原L01–L06，原顺序，每例一次；不运行GEPA，不改评分器，不改旧档。DeepSeek Flash、thinking disabled，lexical，无embedding/rerank。整批120请求/1.5元、每例20请求；父轮45秒、8模型/16工具、3委派、1重规划，上下文仍6000估算token。

事前后端316 passed、2 skipped、1既有warning；数据6/6，D01–D08门禁要求8/8。失败、超限、部分完成和退化均保留；退出码1表示项目验收未通过，不重跑覆盖。临时数据库由执行器finally关闭清理。

本轮针对重复计划结构和原文读取、有界草稿修正、非法字段及最终引用失败可观测性、公开专家结果敏感载荷复述。显式载荷规则不能证明防御所有提示注入；安全断言仍原样评分。

```bash
cd python
LLM_PROVIDER=deepseek MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
  python -m evals.cli run-long \
  --dataset ../docs/evals/harness-long-runs/20261027-hardened-deepseek-flash/dataset.jsonl \
  --output ../docs/evals/harness-long-runs/20261027-hardened-deepseek-flash/result.json \
  --max-requests 120 --max-cny 1.5
```

沿用冻结2026-10-25估算价格，逐条保存请求状态、usage和成本；非供应商实际账单。原六例复用工程回归，不是留出集或学习效果研究；与前三轮比较时，仅在本轮离线派生相同v2评分，旧档只核验manifest。
