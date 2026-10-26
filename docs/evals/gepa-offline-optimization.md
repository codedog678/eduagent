# EduAgent 离线策略优化闭环：GEPA 执行手册

基于当前 50 条 Agent 开发任务实现。日期：2026-10-25。此文及配套代码不报告新的真实模型成绩。

## 选择与范围

推荐直接使用 GEPA 自定义 Adapter，复用现有 `LiveExecutor → LearningHarness → score_live_case`。不需要先学 RL，不训练 DeepSeek 权重，也不需要将项目迁入 DSPy。

| 路线 | 优点 | 代价 | 当前选择 |
| --- | --- | --- | --- |
| GEPA 自定义 Adapter | 原有工具、状态、Trace 和硬检查均可复用；有成熟候选搜索 | 需要明确评测与反思接口 | 采用 |
| DSPy + GEPA | 适合已经用 DSPy 编排的应用 | 当前项目需额外一层编排适配 | 暂不引入 |
| 自写反思、修改、重跑循环 | 原型简单 | 候选池、采样和选择逻辑要自行维护 | 不重复实现 |

首版只优化 `turn_rules`：什么时候澄清、如何接续、何时检索、何时直接答疑。`BASE_RULES`、`QUIZ_RULES`、工具权限、学习证据更新代码和评分器均固定。固定提示不能保证模型绝不违规，仍须通过执行门禁和评测检查。

离线指与学生在线服务分离的批处理；`optimize` 和 `compare` 仍会请求模型 API 并产生费用。`prepare` 和测试不调用远程模型。

## 数据与实验口径

现有 50 条已被用于开发、调试或分析，整体作为开发集。默认 seed=42，按六类能力近似 70/30 划分，8 条旧任务全部放在训练侧：

| 能力 | 优化训练 | 开发验证 |
| --- | ---: | ---: |
| 多轮接续 | 10 | 4 |
| 可见历史接续 | 6 | 2 |
| 全文历史检索 | 6 | 2 |
| 工具与缺失证据决策 | 4 | 2 |
| 注入及权限 | 6 | 2 |
| 学习证据 | 4 | 2 |
| 合计 | 36 | 14 |

训练集提供失败轨迹和反思反馈；开发验证集用于 GEPA 选择候选，其轨迹禁止进入反思。两组仍共享任务模板，不据此声称分布外泛化。

最终验收另建未参与调试的新测试集，建议 18–24 条、覆盖六类能力，使用新原句、知识点组合、历史内容和注入方式。不能只替换 ID，也不能从已反复分析的 50 条里重新抽 10 条称为独立留出集。代码拒绝重复 ID、学习者和只换 ID 的相同任务输入；语义近重复仍需人工检查。首次验收后该集合视为已使用，不再拿它反复挑策略。

正在运行的 50 条报告可用于定位问题，不直接导入 GEPA 当作候选评测结果。优化会在同一配置下重测基线与候选。首版固定 Coordinator 关闭、词法检索、后台记忆提取/重排关闭，隔离 Tutor 决策策略的贡献。它与其他正在开展的记忆/Coordinator 实验属于不同配置，成绩不能直接相减。

## 闭环执行

```mermaid
flowchart LR
  A[冻结数据与评分] --> B[执行基线和候选]
  B --> C[硬检查与语义裁判]
  C --> D[GEPA 反思和搜索]
  D --> B
  D --> E[重复比较与留出验收]
```

1. **冻结协议。** 保存数据 SHA256、36/14 明细、随机种子、基础策略、固定约束、评分器摘要和运行配置。后续运行校验协议一致性；不覆盖原评测文件。
2. **重测基线。** GEPA 在开发验证集执行原 `TURN_RULES`。基线与候选使用相同提示拼接方式、模型、预算与 Harness 配置。
3. **执行训练小批。** 默认每批 3 条。每条使用独立临时 SQLite，完整运行预置学生脚本，保存公开回复、工具轨迹、状态与证据。
4. **评分与反馈。** 原硬检查提供确定性约束；固定 AI 裁判补充语义项、工具选择/参数、必要调用是否遗漏。全局预算、供应商或裁判格式问题停止运行，不能把这些故障计成任务 0 分。候选导致的固定上下文、模型调用次数或工具次数耗尽属于任务失败，记 0 分。
5. **GEPA 生成候选。** `make_reflective_dataset` 仅从训练轨迹提炼反馈。自定义 `propose_new_texts` 复用已配置模型，以便计入同一预算；候选搜索、采样与 Pareto 选择仍由真实 GEPA 完成。
6. **开发验证选择。** GEPA 比较候选，导出 `best-policy.json`。即使验证分提高，也只是开发候选；最佳版本可能仍是原策略。
7. **重复比较。** 原策略与候选在相同案例各跑 3 次，按案例交替先后顺序，关闭评测缓存；记录每轮结果，不挑最好一次。
8. **新测试集验收。** 固定候选后，对另建的测试集运行同样的成对重复比较，产生 `selected-policy.json`。失败保留基线，通过标记为可进入发布审阅；不覆盖在线策略。

首版无自动恢复 checkpoint；中断后保留已执行证据，记录 `stopped/error`，不发布不完整结果。再次运行需要新输出目录和新的预算，不能静默覆盖旧记录。

## 评分与选择规则

任务成功要求：预置有效、全部脚本步骤完成、原自动检查全通过、全部原语义硬检查通过。

工具决策按每个已执行答疑轮判定：所有实际调用的选择和参数均正确，且未遗漏该轮明确必需的调用。零工具调用可以正确，不把“执行成功”当成“选择正确”。逐调用标签和证据保存在结果中。

优化标量：

```text
任务任一硬要求失败：score = 0
任务成功：score = 0.8 + 0.2 × 对话轮工具决策通过比例
```

这是可解释的初版工程目标，权重是设计选择，不是学术标准。AI 任务成功率、自动检查通过率、工具轮决策比例和分能力表现分别报告，不能把加权分称为 TSR。

裁判必须：

- 精确覆盖所有原语义检查和已执行答疑轮、实际调用索引；布尔字段不能用字符串替代。
- 为语义通过项提供可在实际回复/调用中找到的证据；不存在的行为可以留空证据并解释原因。
- 使用固定规则，不自行增加“必须多问一句”等隐含要求，也不替代自动状态检查。

裁判默认也是 DeepSeek Flash，独立请求、temperature=0、思考关闭；它与被测模型同源，因此存在相关偏差。实际大批优化前，建议从当前 50 条已完成记录中选择约 10 条成功、失败、边界案例校准 AI 裁判；人工核对判断与证据。当前代码不自动导入旧人工/AI 标签，也不把同模型裁判当独立人工评审。

验收规则事先固定：TSR 严格增加，或 TSR 持平而平均优化分严格增加；同时不允许出现“基线自动检查通过、候选自动检查失败”的成对回归，且任何能力组 TSR 不下降。门槛保守，适合第一轮工程验证；重复结果仍相关，不将重复次数当独立样本数，不宣称统计显著或真实学习收益。延迟/成本保存作观察指标，首版不据此奖励少调用工具。

## 代码位置

| 文件 | 职责 |
| --- | --- |
| `python/core/tutor_policy.py` | `ContextVar` 注入决策文本；默认提示保持原样，退出即恢复 |
| `python/evals/optimization/protocol.py` | 数据划分、摘要校验、候选结构/样例字面量限制、留出集去重 |
| `python/evals/optimization/budget.py` | 任务/裁判/反思统一账本与纯文本模型请求 |
| `python/evals/optimization/scoring.py` | 冻结裁判提示、严格输出验证、评分与分组汇总 |
| `python/evals/optimization/adapter.py` | 实际 Harness 评测、反思数据与候选提议 |
| `python/evals/optimization/cli.py` | GEPA 搜索、成对比较、验收选择和审计输出 |
| `python/tests/evals/test_policy_optimization.py` | 禁网测试及真实 GEPA 搜索集成测试 |
| `python/requirements-gepa.txt` | 已核验的可选依赖 `gepa==0.1.4` |

GEPA 接口核心实际使用方式：

```python
result = gepa.optimize(
    seed_candidate={"turn_rules": TURN_RULES},
    trainset=train_cases,
    valset=dev_validation_cases,
    adapter=adapter,
    reflection_minibatch_size=3,
    max_metric_calls=160,
    candidate_selection_strategy="pareto",
    skip_perfect_score=False,
    cache_evaluation=False,
    seed=42,
)
```

完整可执行实现包含统一预算、版本校验、停止条件和结果持久化，见 `run_search`。API 实际核验于 GEPA 0.1.4 wheel，不依赖可能变化的 main 分支。

## 安装与运行命令

以下在已有后端 Python 3.11+ 环境中，从项目的 `python` 目录执行。依赖保持可选，不修改当前模型配置或正在执行的进程。

```bash
cd /Users/bytedance/Documents/trae_projects/eduagent/python
python -m pip install -r requirements-gepa.txt
```

先运行不收费的检查：

```bash
LLM_PROVIDER=template python -m pytest tests/evals/test_policy_optimization.py -q
```

当前可运行协议为 `docs/evals/gepa-protocol-v7.json`。v1–v6 保留用于追溯首次真实运行的裁判接入与预算分类修复，不适配当前评分器。以后数据、策略或评分器修改后，用新文件名重新准备：

```bash
python -m evals.optimization.cli prepare \
  --output ../docs/evals/gepa-protocol-v8.json
```

首轮建议用较小搜索预算：

```bash
python -m evals.optimization.cli optimize \
  --protocol ../docs/evals/gepa-protocol-v7.json \
  --output ../docs/evals/gepa-runs/pilot-01 \
  --max-metric-calls 40 --minibatch 3 \
  --max-requests 400 --max-cny 3
```

扩大搜索可使用 160 次 metric calls、1200 次总请求、10 元估算上限，并指定新目录。GEPA 的 metric calls 以“候选×案例”计数，停止检查可能位于批次边界，不等于精确 HTTP 请求上限。`--max-requests` 和 `--max-cny` 在每次任务、裁判、反思请求之前统一检查，是本实现的总门限。

成本按现有 DeepSeek Flash 费率估算，缺失 usage 时保留保守预留；不是供应商账单保证。每例最坏 6 次任务请求 + 1 次裁判，另有反思请求。保留原 `LiveBudget` 单批限制，新总账覆盖多批运行，没有改大旧评测入口的限制。

开发验证上成对重跑：

```bash
python -m evals.optimization.cli compare \
  --protocol ../docs/evals/gepa-protocol-v7.json \
  --origin-run ../docs/evals/gepa-runs/pilot-01 \
  --candidate ../docs/evals/gepa-runs/pilot-01/best-policy.json \
  --output ../docs/evals/gepa-runs/pilot-01-repeat \
  --repeats 3 --max-requests 600 --max-cny 5
```

14 条验证任务包含 18 个答疑轮，最坏每组每次 68 次请求（54 任务 + 14 裁判），成对 3 次为 408 次。命令必须预留整轮最坏请求数，不足时在请求前拒绝启动。

待独立测试集编写完成，将 `--holdout /absolute/path/to/new-holdout.jsonl` 加到同一 `compare` 命令，使用新的输出目录和足够的预算。`new-holdout.jsonl` 需遵循已有 `LiveCase` 契约；当前实现没有伪造新测试集或新成绩。同一优化运行只允许一次独立测试集验收，全部重复在该次验收内完成。

比较时校验优化运行的源代码摘要、有效运行配置、模型和策略摘要一致。若开发并行修改了代码，应在稳定版本上重新开始实验，而不是混用旧候选的分数。

## 输出与回退

| 输出 | 用途 |
| --- | --- |
| `protocol.json`、`run.json` | 数据/评分/代码/配置摘要、状态、版本与实验参数 |
| `baseline-policy.json`、`best-policy.json` | 可校验的策略文本与 SHA256；后者仅在搜索正常完成后产生 |
| `evaluations/*.json` | 每次实际执行的回复、Trace、自动检查、AI 裁定、计费记录 |
| `policies/<hash>.json` | 执行过的候选版本 |
| `budget.json` | 三种角色的请求数、usage、费用估算与未确认预留 |
| `request-ledger.json` | 包含失败或 usage 未确认请求的完整计费账本 |
| `comparison.json` | 成对比较、分能力表现和回归项 |
| `selected-policy.json` | 留出验收通过时选候选，否则选择基线 |

实验策略只经 `use_turn_rules` 注入当前异步上下文，不改 `.env`、线上服务或 `TURN_RULES` 源码。发布接入留到验收后另行进行；此阶段的“回退”是丢弃候选并继续选择基线。

GEPA 内部 checkpoint 和临时 SQLite 自动清理；公开评测证据与候选策略作为实验产物保留。运行期间不在同一 Python 进程并行执行其他评测，因为旧执行器依赖服务 singleton 和 settings。使用单独 CLI 进程与正在进行的 50 条评测隔离。

候选字面量检查只能阻止已知标识/口令直接进入策略，不能检测所有答案改写或规则投机；还需审阅最终策略文本和独立测试。源代码记录保留原 Tutor 策略版本标识，具体实验版本以每条记录的 `policy_sha256` 为准。

## 本次验证记录

已用真实 GEPA 0.1.4 搜索器、模拟任务模型与模拟裁判完成禁网验证，包括候选生成/选择、36/14 协议校验、异步策略隔离、总预算、裁判证据与覆盖校验、留出集去重、失败保留轨迹、开发比较不发布，以及全部 50 条预置的自动契约。新增测试 12 项通过；这些模拟分数只用于验证工程链路，不能当作模型能力或优化收益。

当前工作树完整后端测试 245 项通过；内置 Harness 回归 20/20 通过。完整测试使用下列环境覆盖，避免本地已配置的向量服务凭据触发网络，同时保留混合检索测试自行注入模拟 Provider 的能力：

```bash
LLM_PROVIDER=template \
MEMORY_EMBEDDING_API_KEY='' SILICONFLOW_API_KEY='' MEMORY_RERANK_API_KEY='' \
python -m pytest tests -q
```

默认本地配置下的首次完整测试有两项受向量服务调用影响；全局强制词法检索又会影响专门测试混合检索的用例，因此最终使用上述仅清空测试进程凭据的方式验证。未修改 `.env` 或并行开发中的记忆模块。

以上是 2026-10-25 的工程验证。2026-10-26 已执行真实模型试跑，结果见 [试跑报告](gepa-runs/pilot-20261026-report.md)。随机种子固定的是划分与搜索过程，不保证远程模型输出完全确定；重复比较仍不可省略。

## 原始资料

- [GEPA 论文](https://arxiv.org/abs/2507.19457)
- [GEPA 官方代码及 Adapter 接口](https://github.com/gepa-ai/gepa)
- [GEPA 官方文档](https://gepa-ai.github.io/gepa/)
