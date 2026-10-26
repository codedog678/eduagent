# EduAgent 真实模型评测文档与数据

本目录保存项目自建场景、真实 API 执行证据和指标说明。所有学习者、历史与题目均为虚构评测素材；数据不包含真实学生记录、API Key 或私有思考内容。

| 内容 | 文件 |
| --- | --- |
| Harness 双层长任务评测（8 条确定性合同 + 6 条真实模型任务） | [冻结设计与门槛](harness-long-task-design.md)、数据集 `python/evals/datasets/harness_long_tasks_v1.jsonl` |
| GEPA 离线策略优化（36 训练 + 14 开发验证，独立测试另建） | [设计、代码说明与执行命令](gepa-offline-optimization.md)、[当前冻结协议](gepa-protocol-v7.json)、[真实试跑报告](gepa-runs/pilot-20261026-report.md) |
| 50 条 Agent 主任务扩展（8 原任务 + 42 新任务，尚未真实运行） | [完整场景说明](tutor-agent-50-review.md)、[JSONL](tutor-agent-50-review.jsonl)、[清单与分批计划](tutor-agent-50-manifest.json)、[设计](tutor-agent-50-design.md)、[离线验证说明](20261025/tutor-agent50-validation.md)、[逐条记录](20261025/tutor-agent50-validation.json) |
| 任务最终成功与工具语义评分（AI 审阅） | [评分报告](20261025/tutor-final-scoring-20261025.md)、[逐条标签](20261025/tutor-semantic-review-20261025.jsonl)、[分组指标](20261025/tutor-reviewed-metrics-20261025.json)、[评分口径](20261025/tutor-semantic-rubric-20261025.md) |
| 12 条场景设计与评分规则 | [场景说明](tutor-live-12-review.md)、[原始 JSONL](tutor-live-12-review.jsonl) |
| 常见 Agent 指标、计算口径和实测结果 | [指标报告](20261025/agent-metrics-20261025.md)、[指标 JSON](20261025/agent-metrics-20261025.json) |
| 首轮基线：逐条输入、回复和完整公开 Trace | [原始 JSON](20261025/tutor-live12-20261025.json)、[可读记录](20261025/tutor-live12-20261025.md)、[分析](20261025/tutor-live12-20261025-analysis.md) |
| 提示 v2 复测：保留 05 的回归失败 | [原始 JSON](20261025/tutor-policy-v2-20261025.json)、[可读记录](20261025/tutor-policy-v2-20261025.md)、[场景子集](20261025/tutor-policy-v2-cases.jsonl) |
| 提示 v3 复测：03、05、06 | [原始 JSON](20261025/tutor-policy-v3-20261025.json)、[可读记录](20261025/tutor-policy-v3-20261025.md)、[场景子集](20261025/tutor-policy-v3-cases.jsonl) |
| 代码修改、复测与 AI 初审结论 | [修订说明](20261025/tutor-policy-fix-20261025.md) |

## 2026-10-25 执行事实

模型为 DeepSeek Flash，思考关闭。其他领域 Agent 使用本地策略，评测重点是 Tutor 工具决策、多轮接续、历史依据及 Harness 状态与证据提交。

| 批次 | 场景数 | Agent 自动契约 | 教学辅助自动契约 | 模型请求数 | 高峰费用估算 |
| --- | ---: | --- | --- | ---: | ---: |
| 基线 | 12 | 7/8 | 4/4 | 26 | 0.04896096 元 |
| 提示 v2 | 7 | 4/5 | 2/2 | 10 | 0.02785360 元 |
| 提示 v3 | 3 | 2/2 | 1/1 | 6 | 0.01642784 元 |

累计 42 次模型请求，费用估算区间 0.04662120–0.09324240 元，实际扣费以供应商账单为准。各版本和子集分别报告，不能拼成“最新全套 12/12”。自动契约通过不等于完整任务成功：原始语义项保留 `review_pending`，AI 初审单独归属，不作为人工评分或真实学习效果。

后续 AI 最终审阅已完成：Agent 主任务基线 6/8、v2 4/5、v3 2/2；三轮全部实际工具调用的联合语义比例分别为 19/21、4/4、3/3。仅主任务的工具比例与漏调决策另见[评分报告](20261025/tutor-final-scoring-20261025.md)。04、09 基线按严格口径裁定，保留人工复核敏感性；这是单次 AI 审阅，没有独立人工确认。原始报告未被改写，也没有新增模型请求。

主评测数据现已扩至 50 条，新增 42 条在运行前写明最终成功及工具决策要求。整套经过离线预置和状态链路校验，尚未执行真实模型或新增语义评分；不能把脚本校验结果当作 Agent 成功率。原有 4 条教学辅助独立保留。新套共 64 个答疑轮次，最坏 192 次请求；单批 42 次请求上限保留，后续用 `--case-id` 分批执行。

## 复现

从项目根目录安装后端：

```bash
python -m pip install -e "./python[dev]"
```

离线复算已有结果，不调用模型：

```bash
python docs/evals/20261025/summarize-agent-metrics.py
```

脚本读取本目录归档的三个原始 JSON，重新生成指标 JSON，保留输入摘要、代码与配置指纹和分母；不会重新生成 Markdown 报告。

校验 AI 评分标签并重算任务成功与工具语义指标：

```bash
python docs/evals/20261025/aggregate-semantic-review.py
```

后端和离线回归：

```bash
cd python
LLM_PROVIDER=template python -m pytest tests -q
LLM_PROVIDER=template eduagent-eval run --suite builtin
```

校验 Harness 长任务冻结数据，不调用模型：

```bash
cd python
LLM_PROVIDER=template python -m evals.cli validate-long \
  --dataset evals/datasets/harness_long_tasks_v1.jsonl \
  --output eval-results/harness-long-validation.json
```

确定性合同通过后执行 6 条真实长任务：

```bash
cd python
python -m evals.cli run-long \
  --dataset evals/datasets/harness_long_tasks_v1.jsonl \
  --output eval-results/harness-long-task.json \
  --max-requests 120 --max-cny 1.5
```

生成并离线验证 50 条主任务，不调用模型：

```bash
python docs/evals/build-agent50-dataset.py
cd python
eduagent-eval validate-live \
  --dataset evals/datasets/tutor_agent50_review.jsonl \
  --output eval-results/tutor-agent50-validation.json
```

重新执行真实模型任务需要自行配置 `.env`，以下命令会消耗模型额度：

```bash
cd python
eduagent-eval run-live \
  --dataset evals/datasets/tutor_live12_review.jsonl \
  --output eval-results/tutor-live12.json \
  --max-requests 42 --max-cny 3
```

`python/eval-results/` 继续作为忽略的本地输出目录。经过核对、需要长期保存的评测记录归档到本目录；其他本地设计文档和缓存仍不纳入 Git。
