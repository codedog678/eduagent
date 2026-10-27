# 有效安排交付与空历史规划：冻结复测协议

源码88dde48，机器可读版本、源码和数据摘要见run-protocol.json；实施边界见[第二循环设计](../../../engineering/harness-hardening-20261027.md)，过程见[问题日志C30–C34](../../../engineering/problem-solution-log.md)。

原L01–L06、原顺序、每例单次；不运行GEPA，不改数据、评分v2或旧档。DeepSeek Flash、thinking disabled、lexical，无embedding/rerank。整批120请求/1.5元、每例20；父轮45秒、8模型/16工具、3委派、1重规划，上下文仍6000估算token。未用新预算重复采样选优。

事前离线回归324 passed、2 skipped、1既有warning；D01–D08全部通过才进入真实阶段，数据须6/6校验。失败、退化、待答及partial原样保存；临时数据库由执行器finally关闭清理。

```bash
cd python
LLM_PROVIDER=template MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
  python -m pytest tests -q
LLM_PROVIDER=deepseek MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
  python -m evals.cli run-long \
  --dataset ../docs/evals/harness-long-runs/20261027-delivery-deepseek-flash/dataset.jsonl \
  --output ../docs/evals/harness-long-runs/20261027-delivery-deepseek-flash/result.json \
  --max-requests 120 --max-cny 1.5
```

正式运行前，本次对话已计量一轮33请求、峰值估算0.22782184元；本轮另有测试配置失败导致联网尝试，其完整usage/可能费用不可核定，不能将该失败轮计为0请求。正式运行全部请求由原LiveBudget记录，与测试配置失败严格分开报告。

沿用2026-10-25冻结估算价格，非供应商账单；与前四轮比较只在本档离线派生同v2评分，旧档只验manifest。复用六例属于工程回归，自动合同、助手审计均不能代替独立教学语义评测或学习效果研究。
