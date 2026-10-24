# 50 条数据扩展的离线验证

日期：2026-10-25。本次只扩展和验证数据，没有真实模型请求，也没有新增模型最终成功标签或工具语义评分。

| 检查 | 结果 |
| --- | --- |
| 主任务总数 | 50：原 8 条 + 新 42 条 |
| 原任务内容 | 原 8 条 JSONL 行逐字保留 |
| 数据同步 | docs 与 Python 包中的 JSONL 字节一致 |
| 预置与 Harness 执行契约 | 50/50 可执行并通过脚本核对 |
| 后端测试 | 186 项通过，另有 1 条既有测试类收集警告 |
| 内置离线回归 | 20/20 通过 |
| 供应商请求 | 0 |
| 新套模型成功与工具语义评分 | 未运行、未评分 |

验证在基于 Git `a4260b95c436cfc0a084b634a860d16f17247bba` 的隔离副本中执行，加入本次评测修改；原工作区同时进行的长期记忆和协调模块改动未混入本次验证或提交。

最终离线记录包含数据和 Python 源码指纹：数据 SHA-256 为 `ef3d2071ef99bf5edc63a4a369af7a5a6861314284fd2b636a43ed2d334f5233`；源码 SHA-256 为 `818aea94e011eb6b217720728501b1cb7b6b5e701859551c189f5efb11f1cde5`。详见[逐条验证 JSON](tutor-agent50-validation.json)。

新增测试检查变体契约、全部场景标识隔离、原 12 条兼容、明确主任务归属、网络禁止、隐藏答案和新题不可见、临时数据库清理、错误来源与口令、私有标记泄露负例、真实入口子集选择与预算保持。最终添加验证记录的代码指纹后，新测试 12 项再次通过。

首次离线检查中，部分完整检索样例因冗余预置文本达到上下文上限。缩短干扰记录和重复正文后，目标仍不在初始上下文、口令仍位于 400 字符摘要之外，搜索与正文读取链路全部可执行。没有调高 6000 Token 上下文预算、42 次单批请求上限或 3 元费用上限。

脚本预先知道工具路径和检索口令，所以 50/50 仅证明预置、执行链路和断言相容。自动检查之外的语义质量没有被这份记录判定；新增任务仍需真实运行及独立归属的语义审阅。数据包含已用于提示修订的旧任务，应作为开发集报告。

复现命令：

```bash
python docs/evals/build-agent50-dataset.py
cd python
LLM_PROVIDER=template python -m pytest tests -q
LLM_PROVIDER=template eduagent-eval run --suite builtin
LLM_PROVIDER=template eduagent-eval validate-live \
  --dataset evals/datasets/tutor_agent50_review.jsonl \
  --output eval-results/tutor-agent50-validation.json
```
