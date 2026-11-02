# 优化后长任务单次复测协议

本轮按用户已批准的[优化实施检查表](../../../engineering/harness-optimization-20261027.md)执行；运行时代码已提交并推送为 `454a094`，Python 来源摘要和评分版本见 [run-protocol.json](run-protocol.json)。

固定原 L01–L06、原顺序，每例一次。DeepSeek Flash、thinking disabled，整批120请求/1.5元，每例20请求；父轮45秒、8模型/16工具、3委派、1重规划。词法检索，无 embedding/rerank；不运行 GEPA。独立临时数据库由评测执行器关闭清理；原始 Trace、失败、费用和产物保留。

离线门禁为306 passed、2项原有跳过；数据6/6有效，新增19项边界测试。正式入口再次执行 D01–D08，全部通过才发真实请求。本轮运行中不修改代码、评分或数据，不为改善分数复跑。

评分 v2 拒绝 completed/partial 假阳性，增加学生可见安排及证据断言。旧两轮的 observed 原样用新评分离线重算，作为本目录派生对照，原档和原评分不改写。自动规则仍是确定性产物/证据检查，不能替代独立语义审阅、统计验证或学习效果实验。

成功目标保持至少5/6、L02/L05通过、计划完成率≥80%、恢复成功率100%、冻结权限断言无违规。即使未达标也完成逐条审计和归档。

执行命令（工作目录 `python/`）：

```bash
LLM_PROVIDER=deepseek MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' \
python -m evals.cli run-long \
  --dataset ../docs/evals/harness-long-runs/20261027-optimized-deepseek-flash/dataset.jsonl \
  --output ../docs/evals/harness-long-runs/20261027-optimized-deepseek-flash/result.json \
  --max-requests 120 --max-cny 1.5
```
