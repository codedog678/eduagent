# 可选备题与规划澄清分离：冻结复测协议

源码f8a5c1f，源码及数据SHA256见run-protocol.json；设计见[第四循环边界](../../../engineering/harness-hardening-20261027.md)，实施及离线结果见[日志C41–C42](../../../engineering/problem-solution-log.md)。

原L01–L06及顺序，每例单次，不运行进化、不改评分v2或旧档。DeepSeek Flash、thinking disabled、lexical，无embedding/rerank。原整批120请求/1.5元、每例20；父轮45秒、8模型/16工具、3委派、1重规划，上下文6000估算token、Tutor输出800token，均保持。

事前后端346 passed、2 skipped、1既有warning，全部template/空embedding离线运行；数据6/6验证。正式D01–D08必须8/8后才请求模型。保留失败、partial、awaiting_student；运行器finally清理临时数据库。没有扩大预算或选优重跑。

```bash
cd python
set -o pipefail
LLM_PROVIDER=deepseek MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
  /Users/bytedance/.cache/eduagent-harness-venv/bin/python -m evals.cli run-long \
  --dataset ../docs/evals/harness-long-runs/20261027-plan-gate-deepseek-flash/dataset.jsonl \
  --output ../docs/evals/harness-long-runs/20261027-plan-gate-deepseek-flash/result.json \
  --max-requests 120 --max-cny 1.5 \
  2>&1 | tee ../docs/evals/harness-long-runs/20261027-plan-gate-deepseek-flash/formal-run.txt
```

本次对话此前三轮正式87请求、峰值估算0.60953424元，尽量将本轮控制在剩余33请求内。C34旧配置错误的联网尝试usage/可能费用未知，不能计为0或声称总扣费已完整核定。沿用2026-10-25冻结估算价格，非供应商账单。

旧六轮仅校验manifest并在本档离线派生同v2对照。模型执行期间源码/数据/评分不变；助手审计不是人工或独立模型裁判。六例为复用工程回归，单次结果不能证明留出稳定性或教学学习效果。
