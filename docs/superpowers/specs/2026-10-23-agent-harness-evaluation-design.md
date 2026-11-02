# EduAgent Agent Harness 评测与工程化设计

> 历史设计快照，归档日期：2026-11-02。下文的状态、124 项测试等事实属于
> 2026-10-23，不是当前验收结论。后续实现与评测口径以
> [当前评测索引](../../evals/README.md)和
> [工程验收记录](../../engineering/m3-policy-promotion-acceptance.md)为准。

日期：2026-10-23
状态：方案已确认，待书面规格复核

## 1. 背景与事实

EduAgent 已具备一条可运行的教学 Harness 主链路：

- 请求指纹去重、成功结果重放、失败后整轮重试；
- SQLite 原子提交学习状态、测验状态、教学证据和执行结果；
- 运行超时、事件步数、模型调用和工具调用预算；
- 跨会话教学历史、来源引用、待回答问题和受助证据；
- Tutor 原生工具循环、严格参数校验和学习者范围隔离；
- 现有后端测试 124 项通过，前端可构建。

当前主要缺口不是再增加编排能力，而是缺少可重复的质量评测入口、持续集成、稳定的数据契约和可安装的 Python 包。现有 `python/pyproject.toml` 还存在构建元数据不完整、包发现不明确的问题；SQLite 表由运行时代码直接创建，没有显式 schema 版本。

## 2. 方案比较

### 方案 A：只做仓库内确定性回归集

优点是快、稳定、无网络和许可风险，适合 CI。缺点是只能证明已知工程契约没有回归，不能说明 Tutor 在公开教育基准上的相对表现。

### 方案 B：直接接入完整公开基准

优点是可与外部研究对齐。缺点是下载、格式、模型费用和评审模型依赖较重，公开基准通常以数学辅导为主，也不能直接覆盖 EduAgent 的幂等、事务和跨会话边界。

### 方案 C：双层评测集

仓库内保存小型、人工编写、可确定判分的回归集；仓库外按需下载 MRBench，并转换为统一格式。CI 只运行内置层和外部适配器 fixture，人工或定时评测再使用完整外部数据。

选择方案 C。它同时覆盖 Harness 工程可靠性与 Tutor 教学行为，又不会把网络、GPU、付费模型或第三方数据许可引入每次提交。

## 3. 目标与非目标

### 目标

1. 提供统一、可扩展的评测样例 schema 和命令行入口。
2. 建立内置小型回归集，覆盖教学策略与 Harness 边界。
3. 提供 MRBench 的按需下载、校验和转换能力，不提交第三方原始数据。
4. 输出机器可读结果、失败明细、配置与版本信息。
5. 修复 editable install，并用 CI 持续验证后端、评测和前端。
6. 为 Harness SQLite 增加显式、向前迁移的 schema 版本。

### 非目标

- 不训练或内置 LLM judge、reward model。
- 不声称确定性规则可以替代人工教学质量评审。
- 不在本阶段接入向量数据库、语义检索或消息队列。
- 不重写 AgentOrchestrator、EventBus 或现有 Tutor 工具循环。
- 不把 MRBench、MathTutorBench、MathDial 等原始数据提交到 Git。
- 不在 CI 中调用真实远程模型或执行完整外部基准。

## 4. 数据集决策

### 4.1 内置回归集

仓库保存 20 个英文学习与 Harness 契约样例，每组 4 个；使用项目自有文本和明确许可声明。样例按能力分组：

| 分组 | 验证内容 |
|---|---|
| `pedagogy` | 指出错误、提供相关引导、给出下一步、避免直接泄露答案 |
| `dialogue` | 澄清问题、等待学生回答、跨会话接续 |
| `safety` | 受保护测验不泄露答案、工具越权拒绝、来源不伪造 |
| `reliability` | 幂等重放、冲突检测、预算耗尽、失败回滚 |
| `trace` | run/attempt 关联、步骤顺序、版本和配置指纹 |

这些样例用于回归，不用于宣称总体教学效果。所有必须通过的判定都基于结构化字段、事件或显式文本约束，避免依赖随机模型输出。

### 4.2 外部公开基准

首个适配目标为 MRBench V1。它包含 192 段对话、1,596 个 Tutor 回复及八个教学维度：错误识别、错误定位、答案泄露、指导、可行动性、连贯性、语气和自然度。数据采用 CC BY-SA 4.0；项目与论文：

- <https://github.com/kaushal0494/UnifyingAITutorEvaluation>
- <https://arxiv.org/abs/2412.09416>

下载器固定到仓库提交 `bbef521ddb875f2cc8a5ee798f4066965a7cfd8a`。MRBench 适合校准 EduAgent 的教学评价维度，但其数学领域和人工标签不能直接代表英语学习成效。转换器保留来源、原始 ID、许可、split 和标签，不修改原始数据含义。转换结果属于第三方数据的派生副本，继续保存在缓存中，不进入项目发布包。

MathTutorBench 提供三类教师技能、七类任务及教师基准，可作为后续扩展：

- <https://github.com/eth-lre/mathtutorbench>
- <https://aclanthology.org/2025.emnlp-main.11/>

本阶段不执行其 reward model，也不引入 GPU 依赖。BEA 2023 受注册与条款限制，只在数据说明中记录为可选人工来源，不提供自动下载。

## 5. 项目结构

新增结构如下：

```text
python/
├── evals/
│   ├── __init__.py
│   ├── cli.py                 # list、validate、run、report
│   ├── models.py              # EvalCase、EvalResult、EvalReport
│   ├── runner.py              # 统一执行和汇总
│   ├── scorers.py             # 确定性契约评分
│   ├── datasets/
│   │   ├── README.md          # 来源、许可和使用边界
│   │   └── builtin.jsonl      # 仓库内回归集
│   └── adapters/
│       └── mrbench.py         # 下载校验与统一格式转换
├── core/
│   ├── versions.py            # 应用、trace、eval schema 版本
│   └── harness_migrations.py  # SQLite 顺序迁移
├── tests/
│   ├── evals/
│   │   ├── fixtures/          # 小型、重写后的格式 fixture
│   │   └── test_*.py
│   └── ...
└── README.md                  # Python 包构建说明

.github/workflows/ci.yml
```

外部数据默认进入用户缓存目录：

```text
~/.cache/eduagent/evals/mrbench/<revision>/
```

可通过命令行参数覆盖缓存路径。生成报告默认写入 `python/eval-results/`，该目录加入 `.gitignore`。

## 6. 统一数据契约

每行 JSONL 对应一个 `EvalCase`：

```json
{
  "schema_version": 1,
  "case_id": "pedagogy-no-answer-leak-001",
  "suite": "builtin",
  "kind": "tutor_response",
  "knowledge_id": "grammar_present_perfect",
  "input": {
    "messages": [],
    "student_text": "I have went there yesterday.",
    "quiz_mode": "practice"
  },
  "expected": {
    "dialogue_state": ["answered", "awaiting_student"],
    "required_signals": ["guidance"],
    "forbidden_signals": ["answer_reveal"]
  },
  "tags": ["pedagogy", "english"],
  "source": {
    "name": "eduagent-authored",
    "license": "project-license"
  }
}
```

`kind` 决定执行器和可用 scorer。第一版支持：

- `tutor_response`：调用 Tutor 文本或 scripted provider 路径；
- `harness_contract`：执行幂等、回滚、预算、隔离等场景；
- `trace_contract`：验证公开 trace 的结构、关联和脱敏；
- `labeled_response`：读取 MRBench 已有回复和人工标签，只做标签/规则校准，不重新生成回复。

加载器拒绝未知 schema 版本、重复 `case_id`、缺少来源信息和不受支持的 `kind`。适配器输出也必须先经过同一验证器。

## 7. 评分与报告

第一版只提供确定性 scorer：

| Scorer | 输入 | 输出 |
|---|---|---|
| `ContractScorer` | API 结果、异常、状态变化 | pass/fail 与失败原因 |
| `DialogueScorer` | dialogue_state、pending question | 接续契约结果 |
| `PolicyScorer` | 结构化模式、受助标记、受保护内容 | 泄露/越权等规则结果 |
| `TraceScorer` | execution、attempt、steps | 关联、顺序、脱敏、版本结果 |
| `LabelAgreementScorer` | MRBench 标签与规则映射 | 每维混淆矩阵和匹配率 |

`PolicyScorer` 的文本规则只应用于为该规则专门编写的固定样例。它不能把“未命中关键词”解释为教学质量良好。

报告同时输出：

- 终端摘要；
- JSON 报告；
- suite、case、tag 和 scorer 级通过率；
- 每个失败样例的公开输入摘要、期望、实际结果和原因；
- 应用版本、eval schema、trace schema、数据集 revision；
- 影响行为的配置快照及 SHA-256 指纹；
- provider、model、generation mode；无真实 usage 时明确标记未知。

退出码：全通过为 `0`，存在评测失败为 `1`，数据/配置错误为 `2`。

## 8. 外部数据流

```text
显式 fetch 命令
  → 下载固定 revision 的源码归档
  → 校验来源、许可文件和内容摘要
  → 解压到缓存
  → MRBench adapter 读取受支持字段
  → 转为统一 EvalCase JSONL
  → schema 校验
  → run / report
```

下载器遵循以下边界：

1. 只有显式命令触发网络访问，import、测试和普通评测不自动下载。
2. revision、URL 和摘要写入 manifest；来源变化时失败，不静默使用新格式。
3. 临时下载使用原子重命名，失败时清理临时目录。
4. 已存在且摘要匹配时复用缓存。
5. 许可或预期数据文件缺失时停止转换。
6. CI 仅使用项目自有的小型 fixture 测试适配逻辑。

## 9. Harness 版本与迁移

新增三个独立版本常量：

- `APP_VERSION`：项目发布版本；
- `TRACE_SCHEMA_VERSION`：公开 execution/trace 结构；
- `EVAL_SCHEMA_VERSION`：评测样例与报告结构。

每次成功或失败 attempt 都记录 app、trace schema、provider/model 和关键配置指纹。历史记录没有这些字段时，API 返回 `null` 或 `legacy`，不伪造回填值。

SQLite 使用顺序、幂等迁移：

1. 新数据库从空库依次执行全部迁移。
2. 旧数据库先验证现有核心表，再登记为 legacy baseline。
3. 后续迁移只做兼容性新增，不删除列、不重写用户数据。
4. 每个迁移在单个事务内执行；失败不提升版本。
5. 运行时代码不再依赖 `INSERT INTO table VALUES (...)` 的隐式列顺序。
6. 数据库版本高于当前代码支持版本时拒绝启动并给出明确错误。

迁移基础设施只服务现有 Harness SQLite；不迁移 PostgreSQL 事件日志。

## 10. 包管理与 CI

`python/pyproject.toml` 调整为明确的项目名、描述、README、包发现范围和测试配置。创建 `python/README.md`，确保：

```bash
python -m pip install -e ./python
```

可以成功执行，并且安装后可运行：

```bash
python -m evals.cli validate
python -m evals.cli run --suite builtin
```

CI 使用固定 Python 主版本，包含三个 job：

1. `backend`：editable install、全量 pytest、内置 eval smoke；
2. `frontend`：`npm ci`、TypeScript/Vite build；
3. `package`：构建 wheel/sdist，并在干净环境中安装和导入关键包。

CI 不读取本地 `.env`，不需要 API key，不下载外部数据。

## 11. 错误处理

- 数据格式错误按文件、行号和字段报告，不跳过坏样例。
- 单个评测 case 的业务失败记录为结果并继续执行其他 case。
- 基础设施错误，如 schema 不支持、缓存损坏、迁移失败，立即终止并返回退出码 `2`。
- 评测输出经过现有 `public_data` 规则脱敏；禁止写入 API key、Authorization、系统提示、隐藏思维和答案密钥。
- 外部数据下载错误不得回退到未固定 revision 或未知镜像。
- 报告写入采用临时文件加原子替换，避免产生半份 JSON。

## 12. 测试策略

### 单元测试

- EvalCase 与报告 schema 的有效/无效输入；
- JSONL 重复 ID、未知版本和坏行处理；
- 每个 scorer 的正反例；
- MRBench fixture 转换、manifest 和摘要校验；
- 配置指纹稳定性与敏感字段排除。

### 集成测试

- 使用 template/scripted provider 跑完整内置 suite；
- 验证受保护测验、ask_student、幂等重放、回滚和预算耗尽；
- 验证报告中的 run/attempt/trace 关联与版本；
- 从旧结构 SQLite 副本迁移并保留原有结果；
- 新库初始化两次结果一致。

### 回归验证

- 后端全量 pytest；
- 内置 eval smoke；
- editable install 和构建产物安装；
- 前端 build。

真实模型和完整 MRBench 运行属于人工评测，不作为合并门禁。执行时必须记录模型、参数、数据 revision 和成本相关 usage。

## 13. 验收标准

1. 干净环境中 editable install 和 wheel 安装均成功。
2. `evals.cli validate` 能校验内置集，坏数据返回退出码 `2`。
3. 内置 suite 离线运行并生成稳定 JSON 报告。
4. MRBench adapter 可从固定 revision 转换数据；CI fixture 覆盖字段变化失败路径。
5. 原始外部数据、缓存和评测结果不进入 Git。
6. 新旧 SQLite 均可启动；迁移失败不改变 schema 版本。
7. trace 和 eval 报告包含版本、配置指纹和 provider/model 信息，且不包含敏感数据。
8. GitHub Actions 同时验证后端、前端与包构建。
9. 现有 API 行为和 124 项后端测试保持通过。

## 14. 实施顺序

1. 修复包元数据与 editable install。
2. 建立 eval schema、内置数据、scorer、runner 和 CLI。
3. 增加 MRBench fixture、下载器和适配器。
4. 增加版本元数据和 SQLite 迁移基础设施。
5. 接入 CI，补充 README 和数据许可说明。
6. 执行全量验证并清理缓存、中间报告和构建产物。
