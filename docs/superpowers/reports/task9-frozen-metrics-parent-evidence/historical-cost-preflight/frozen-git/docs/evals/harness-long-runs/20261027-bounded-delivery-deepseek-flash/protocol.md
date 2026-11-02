# 授权边界与截断重生成：冻结复测协议

源码2dd2de7，版本、源码和数据摘要见run-protocol.json；边界见[第三循环设计](../../../engineering/harness-hardening-20261027.md)，过程见[问题日志C36–C39](../../../engineering/problem-solution-log.md)。

原L01–L06及顺序、每例单次；不运行GEPA、不改评分v2、原数据或旧档。DeepSeek Flash、thinking disabled、lexical，无embedding/rerank。整批120请求/1.5元、每例20；父轮45秒、8模型/16工具、3委派、1重规划，上下文6000估算token、Tutor输出800token，全部沿用。

事前离线后端338 passed、2 skipped、1既有warning。数据6/6校验，正式D01–D08须8/8才请求真实模型。保留所有失败、partial、待答和退化，临时数据库由运行器finally清理。未增加预算重复采样选优。

```bash
cd python
LLM_PROVIDER=deepseek MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
  python -m evals.cli run-long \
  --dataset ../docs/evals/harness-long-runs/20261027-bounded-delivery-deepseek-flash/dataset.jsonl \
  --output ../docs/evals/harness-long-runs/20261027-bounded-delivery-deepseek-flash/result.json \
  --max-requests 120 --max-cny 1.5
```

此前本次对话正式已计量63请求、峰值估算0.44837968元；第三循环预计仍在原对话120请求目标内。C34旧测试配置错误引起的联网尝试usage/可能费用不可核定，不计为0请求，也不混入本正式账本。

沿用2026-10-25冻结估算价格，不是供应商账单。旧五轮只校验manifest并在本档离线派生同v2对照；真实模型执行中不得改源码/数据/评分。助手审计不是人工或独立模型裁判，复用六例是工程回归，不能证明留出集稳定性或学习效果。
