# Agent 算法面试证据卡

核对日期：2026-11-01。本页把现有算法、实现与运行证据连接起来，
帮助展开技术追问。实现机制、自动契约、模型语义和教学效果分别具有不同证据。

| 追问 | 可讲清的算法与实现 | 运行证据与限制 |
| --- | --- | --- |
| 如何检索长期历史？ | [memory_store](../../python/core/memory_store.py#L131-L169) 使用 FTS5/BM25 与未索引原文词项匹配；[memory_retrieval](../../python/core/memory_retrieval.py#L102-L164) 对来源去重后按 `Σ1/(60+rank)` 融合词法与向量排名。 | 默认最多返回 5 条，向量在授权范围内最近 2000 块用 Python 余弦计算。语义阈值 0.55 尚未用实网语料校准；第五轮模型证据使用 lexical，不能证明向量效果。 |
| RRF 与 rerank 分别解决什么？ | RRF 合并两路排名；[rerank](../../python/core/memory_retrieval.py#L166-L184) 在融合候选上调用模型重排序，默认关闭，失败保留融合排名。 | 检索 Trace 保存两路命中、扫描数、耗时、调用 usage 与降级原因。当前没有独立的向量/rerank 效果对照实验。 |
| 没有相关命中时怎么继续？ | [发现候选](../../python/core/learning_history.py#L75-L81) 只读同学生、同知识点最近公开摘要；运行内最多一次，显式 `discovery_only`。 | 发现候选不代表相关命中、全文读取或语义支持。当前工具描述仍使用“无相关证据时返回空集”的简写，理解行为应以返回标记和实现为准。 |
| 如何拆解并调整任务？ | [Coordinator](../../python/core/coordinator.py#L380-L433) 校验结构化角色、任务 ID、依赖与预算，保留已完成成果和失败事实，再修订剩余步骤。 | 重规划次数与全轮模型/工具预算有界；无法完成原必需动作时返回 partial。不能改名为 completed 或扩展学生授权。 |
| 是否实现了 Reflection？ | [ExpertEngine](../../python/core/distributed/expert_engine.py#L265-L325) 对结构、未读来源和必要动作提供共用一次的有界纠错机会，关闭工具并消耗原预算。 | 可准确称为有界纠错与重规划；没有开放式反思训练或自动在线改 prompt。第五轮新纠错分支零触发，只有本地回归证据。 |
| 如何保证工具调用不扩权？ | [coordination_budget](../../python/core/coordination_budget.py#L8-L50) 从原请求与学生补充识别许可；[动作复核](../../python/core/coordinator.py#L550-L574) 再检查资格、目标与来源。 | 模型 goal/findings 不授予权限。当前许可识别是规则策略，演示 learner ID 仍需多用户登录主体认证。 |
| Tutor 和专家的来源检查是否一样？ | [TutorRuntime](../../python/core/tutor_runtime.py#L175-L259) 检查识别出的显式来源 ID 已提供且仍可用；专家对未读来源另有完整读取要求与有界修正。 | 搜索来源也可进入 Tutor 的 source refs；不能宣称所有 Tutor 引用都强制阅读全文或已逐句验证语义 grounding。结构合法与语义支持不同。 |
| 如何衡量学生掌握？ | [Harness](../../python/core/harness.py#L571-L613) 只用首次、无提示、无对话受助的作答更新独立掌握；[受助绑定](../../python/core/harness.py#L463-L484) 随成功事务提交。 | 受助正确、重试和查看答案保留为不同证据。教学片段、自动工程通过与固定脚本选择不证明真实迁移能力。 |

## 用真实失败展开追问

[第五轮来源恢复分析](../evals/harness-long-runs/20261027-source-recovery-deepseek-flash/analysis.md)
与[核验 JSON](../evals/harness-long-runs/20261027-source-recovery-deepseek-flash/verification.json)
记录自动契约 5/6、30 次模型请求，六例中五例 completed、一例 partial。
“计划完成 5/5”的原分母排除了 L01，面试时应同时报告完整六例。
历史运行代码为 `52157e6`、评分 v2，不能作为当前 M3/Judge v3 的新模型验证。

L01 的课程草稿两次违反 findings 数量上限，未完成必需备题，保留 partial。
归档未保存非法原稿，因此可引用校验失败与预算事实，不能展示不存在的原始条数
或逐条内容。L02 恢复原写作计划成功，但新计划简化和未读来源修复分支均零触发，
不能用该轮成绩证明它们带来效果提升。

## 评分证据尚有的边界

[旧工具语义评分](../evals/20261025/tutor-final-scoring-20261025.md)来自一次非盲
AI 审阅，评分员参与过提示修订；三版场景不同，不能画成全量性能提升曲线。
工具选择、参数正确、漏调、工具返回成功与最终任务成功应分别说明。
[开发重放](../evals/rsi-review-20261029/analysis.md)的 100% 是开发一致率，
仍为 `validation_required`，不能授予发布资格。

[Agent50 运行](../evals/20261025/agent50-live/run-state.json)已记录 82 次请求、
自动契约 40/50。最终任务与工具语义审阅曾按用户要求暂停，本轮保持该状态；
未审阅结果不能写为最终成功率，也不能自动补成独立人工标签。
当前 [Judge v3](../../python/evals/optimization/judge_v3.py#L78-L136) 校验覆盖判据、
证据引用与 verdict/reason 一致性，unknown 不授予资格；这仍不替代独立语义审核。
