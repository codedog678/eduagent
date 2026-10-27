# 普通计划与来源修复：冻结复测协议

用户明确要求按规划多余诊断、来源误用、修复链三个问题修改代码并再次评测。源码52157e6，源码和数据SHA256见run-protocol.json；实现边界见[第五循环设计](../../../engineering/harness-hardening-20261027.md)，过程见[日志C45–C48](../../../engineering/problem-solution-log.md)。

原L01–L06及固定顺序，每例单次，评分v2不变，旧档不改，不运行GEPA、裁判、反思或选优重跑。DeepSeek Flash、thinking disabled、lexical，无embedding/rerank。原每批120请求/1.5元、每例20；单次父45秒、8模型/16工具、3委派、1重规划，角色额度、上下文6000估算token、Tutor输出800token均保持。

事前离线后端370 passed、2 skipped、1既有warning；新增24项业务回归，全部template/空embedding运行。数据6/6验证。正式D01–D08必须8/8后才能请求真实模型。原失败、partial、待答和退化保留；临时数据库由运行器finally清理。

```bash
cd python
set -o pipefail
LLM_PROVIDER=deepseek MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
  /Users/bytedance/.cache/eduagent-harness-venv/bin/python -m evals.cli run-long \
  --dataset ../docs/evals/harness-long-runs/20261027-source-recovery-deepseek-flash/dataset.jsonl \
  --output ../docs/evals/harness-long-runs/20261027-source-recovery-deepseek-flash/result.json \
  --max-requests 120 --max-cny 1.5 \
  2>&1 | tee ../docs/evals/harness-long-runs/20261027-source-recovery-deepseek-flash/formal-run.txt
```

此前本次对话四轮正式累计117请求、峰值估算0.81011656元。用户本次明确要求追加一轮，不以原“尽量120请求”仅余3次为由停止；本轮另记30左右预期请求及原批次硬上限，实际数量如实累计。C34旧配置错误的联网尝试usage/可能费用未知，不能计为0或声称总扣费完整核定。价格沿用2026-10-25冻结估算，不是供应商账单。

七个旧档只核验manifest，并在本档离线派生八轮同v2对照。执行期间源码、模型、数据、评分和预算不变。助手审计不是人工或独立裁判；复用六例不构成留出集或学习效果证据，新增修复分支是否触发单独记录。
