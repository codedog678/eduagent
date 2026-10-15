# EduAgent Harness 补齐方案：OpenMAIC 源码参考与跨会话教学闭环

日期：2026-10-16。正文保留实施前的源码分析与设计；以下“实施记录”描述当前已落地的代码及边界。

## 实施记录（2026-10-16）

第一阶段及第二阶段的基础闭环已接入现有 API 和前端。

| 能力 | 当前实现 |
|---|---|
| 跨会话范围 | session/thread 校验归属；默认学习者 × 知识点线程跨会话稳定；前端保存线程入口并支持新会话 |
| 长期证据 | Harness SQLite 保存公开教学消息、错题评估、受助证据和待回答问题；限定知识点的词项匹配与时间排序 |
| ContextBuilder | 当前结构化学习状态、公开题目、待回答问题、最近线程消息及相关历史；记录来源和 UTF-8 字节估计预算 |
| Tutor 原生工具 | search/read learning history、知识关系、公开题目和 ask_student；只读工具为主，不提供掌握度写工具 |
| Provider 协议 | 实际使用的 LLMService 接入 OpenAI 兼容协议和 Anthropic tool_use/tool_result；未重写未被主链路使用的旧 llm 适配层 |
| 生命周期 hooks | before_model 管预算，before_tool 校验允许列表与严格 schema，after_tool 收集来源和必要执行记录 |
| 完成与接续 | execution completed 与 dialogue awaiting_student 独立；ask_student 成功立即终止；同线程下一条消息接续 |
| 受助口径 | /question 和 /message 可绑定测验；旧客户端遗漏 quiz_id 时关联最近有效同知识点测验；受助后答对不更新 BKT |
| 独立测验 | advance 模式禁止本题答疑与提示；主动查看答案结束测验，不能继续提交为独立证据 |
| 提交及重试 | 回复、受助证据、测验状态、checkpoint、步骤、可重放结果在同一成功事务提交；失败 attempt 分别保留 |
| 前端 | 知识点教学历史、跨会话标记、历史分页、等待回答提醒和本轮互动记录 |

关键代码入口：

- `python/core/harness.py`：执行上下文、事务、converse、受助和重放。
- `python/core/learning_history.py`：存储、检索、来源读取、分页、轨迹与 pending question。
- `python/core/run_context.py`：run/attempt 标识、截止时间和必要步骤。
- `python/core/tutor_runtime.py`：ContextBuilder、原生工具循环及文本路径。
- `python/core/tutor_hooks.py`：有限生命周期门禁。
- `python/core/llm_service.py`：原生 provider 消息与工具协议。
- `frontend/src/components/TeachingHistory.tsx`：跨会话历史和互动记录。
- `python/tests/test_tutor_harness.py`：实际 Harness/API 与 scripted provider 的端到端边界测试。

新增配置见 `.env.example`。`ENABLE_TUTOR_TOOLS=true` 时，已配置的远程模型走原生工具协议；未配置模型时使用明确标记的本地文本回退。设为 false 可使用文本模型路径，同时保留长期证据与受助记录。

实施边界：

1. 当前是有界词项检索，不是 FTS5、embedding 或语义记忆；尚未加入摘要生成和增量摘要。
2. 来源列表表示提供给运行上下文或工具读取的证据，不声称模型逐句引用都已验证。
3. 工具为同进程只读查询和待回答问题登记。request_hint 仍为原有确定性 API；after_run 派生摘要任务尚未实现。
4. 中断后标记 interrupted 并整轮重试；没有租约、多 worker、消息边界 checkpoint 或中途工具恢复。
5. 细粒度步骤在本轮成功或正常异常时提交。进程硬退出前未提交的步骤可能丢失；不能据此声称有完整崩溃轨迹。
6. 现有 checkpoint 中受条数限制的旧历史没有自动回填新消息表。新增长期证据从此次升级后的交互开始记录。
7. 服务仍是当前学习者 ID 驱动的演示应用。资源归属校验与模型参数隔离已实现，API 登录主体认证仍待多用户部署时接入。
8. 原生 provider 协议使用无网络 mock 与 scripted 模型验证；没有调用真实付费模型，也没有验证教学效果。

验证记录：后端全量测试、前端 TypeScript/Vite 构建；浏览器中验证首次提问入库和新会话显示旧对话。最终测试数量见本文件末尾。

源码基线：

- EduAgent：实施前源码基线 `e70f51e`；当前实现入口见上方实施记录。
- OpenMAIC：`https://github.com/THU-MAIC/OpenMAIC`，源码基线 `ecb940c136cc5b4ea56dc81b2505e64eff1dea29`，MIT 许可证。
- 本次进行了源码及测试用例阅读；未启动 OpenMAIC、未运行其测试、未验证真实模型调用。

## 1. 实施前事实

### EduAgent 已有的执行基础

1. 四个 Agent 在同一 Python 进程中，通过类型化事件协作。EventBus 使用每次交互独立的优先级队列，按订阅顺序串行执行 handler；子事件入队后再执行。虽然部分注释仍写着并发、Mesh 和容错隔离，实际代码是确定顺序、失败中止。
2. `LearningHarness.run` 已有请求指纹去重、全局异步锁、SQLite WAL、学习状态快照、失败回滚、测验状态与成功结果原子提交。通过文件锁限制同一 store 只能有一个服务器 worker。
3. Tutor 的近期对话、按知识点组织的历史与最近答题信息，可以随 Agent 状态恢复。它已有有限历史记忆；缺少的是独立、可检索、带来源和预算的长期证据层。
4. 目前 LLM 主要生成文本，尚未接入原生 tool-call / tool-result 循环；历史主要按条数截断，LLM 提示构建通常只取最近六条。
5. 当前运行成功后可重放结果；中断则标失败，重试整轮执行。它尚不支持从某次工具结果后恢复。
6. 当前题目“独立作答”判断依赖首次提交且没有使用提示。普通 `/question` 没有当前测验绑定及受助记录，可能遗漏学生通过对话获取帮助的情况。

源码：

- [执行与事务（实施前）](https://github.com/codedog678/eduagent/blob/e70f51e/python/core/harness.py#L109-L180)
- [事件通信（实施前）](https://github.com/codedog678/eduagent/blob/e70f51e/python/core/event_bus.py#L133-L224)
- [Tutor 提问链路（实施前）](https://github.com/codedog678/eduagent/blob/e70f51e/python/agents/tutor_agent.py#L222-L260)
- [受助与独立作答（实施前）](https://github.com/codedog678/eduagent/blob/e70f51e/python/core/harness.py#L209-L250)

### OpenMAIC 有两条不同的链路

| 链路 | 源码事实 | 对 EduAgent 的意义 |
|---|---|---|
| 课堂多角色讨论 | LangGraph `START → director → agent_generate → END`；每次请求最多选择一个角色，客户端串行发起后续请求形成多轮讨论 | 不应把它理解为多个 Agent 在服务器中无限自主对话。当前教学分工固定，无需增加 Director |
| 工作台 Agent 执行 | pi-agent-core 驱动工具循环；注册工具和允许工具分别声明；工具顺序执行并有超时包装 | 适合参考 Tutor 的运行边界、工具协议和调用门禁 |
| 用户历史读取 | 四个工具 search/read classrooms/chats；owner 从服务器 session 注入；分页及输出大小受限 | 适合参考“搜索摘要 → 读取选中证据”的长期记忆接口 |
| 执行完成与恢复 | 持久化消息及工具结果，按 transcript 尾部判断 start / continue / already-complete | 可参考完成规则；中途恢复应在确有需求后加入 |
| 用户追问 | 成功 `ask_user` 会终止本轮；收到后续用户消息再执行 | 对教学尤其有价值：本轮回复完成与等待学生回答可以同时成立 |
| 主机 hooks | authorizeStart、wrapExecution、classifyFailure、onRunEvent | 可参考关键控制与非关键观察的不同失败处理；这些是生成任务 hooks，不等同于任意 Agent 插件体系 |

源码：

- [课堂编排拓扑](https://github.com/THU-MAIC/OpenMAIC/blob/ecb940c136cc5b4ea56dc81b2505e64eff1dea29/lib/orchestration/director-graph.ts#L470-L497)
- [Agent 构建、工具门禁与顺序执行](https://github.com/THU-MAIC/OpenMAIC/blob/ecb940c136cc5b4ea56dc81b2505e64eff1dea29/lib/agent/runtime/build-agent.ts#L61-L101)
- [历史工具](https://github.com/THU-MAIC/OpenMAIC/blob/ecb940c136cc5b4ea56dc81b2505e64eff1dea29/lib/server/agent-runtime/personal-history-tools.ts#L401-L599)
- [runner 中的工具装配和持久化](https://github.com/THU-MAIC/OpenMAIC/blob/ecb940c136cc5b4ea56dc81b2505e64eff1dea29/lib/server/agent-runtime/runner.ts#L1508-L1630)
- [恢复与终止分类](https://github.com/THU-MAIC/OpenMAIC/blob/ecb940c136cc5b4ea56dc81b2505e64eff1dea29/lib/server/agent-runtime/resume.ts)
- [有界子任务结果](https://github.com/THU-MAIC/OpenMAIC/blob/ecb940c136cc5b4ea56dc81b2505e64eff1dea29/lib/agent/runtime/run-native-child.ts#L329-L361)
- [hooks 契约](https://github.com/THU-MAIC/OpenMAIC/blob/ecb940c136cc5b4ea56dc81b2505e64eff1dea29/lib/server/generation-run-hooks/types.ts#L160-L202)

注意：`workspace-session-memory.ts` 仅用 localStorage 记住上次打开的会话，不是语义记忆或长期学习记忆。`build-agent.ts` 中共享 quota hook 当前近乎无限额度；不能直接宣称 OpenMAIC 全部 Agent 已有统一严格预算。

## 2. Agent 怎么通信，任务怎么完成

建议保留现有同进程事件通信，补齐统一执行上下文和结果契约。

答题链路：

```text
提交服务端测验
  → Assessment 判分、校验独立性、更新 BKT
  → mastery_updated：Curriculum / Engagement 按订阅关系处理
  → assessment_complete：Tutor 形成教学反馈
  → Harness 校验必要结果并提交状态、证据、执行结果
```

追问链路：

```text
学生问题 → Tutor 检索上下文并调用工具 → 教学回复/澄清问题
        → Harness 保存本轮消息、证据与轨迹 → 返回
```

不是每个请求都需要四个 Agent 执行。各 Agent 通过明确的领域事件传递事实，避免让 Tutor 自由调用另一个 Agent 去修改掌握度。

### 统一上下文

```text
RunContext
  learner_id        服务端确定的学习者范围
  session_id        当前会话
  thread_id         跨会话的教学主题线程
  request_id        客户端请求去重键
  run_id            此次逻辑执行；重试时保持稳定
  attempt_id        每次实际执行尝试；重试时重新生成
  parent_run_id     可选，用于接续前一轮追问
  knowledge_id      知识点范围
  quiz_id           可选，当前题目范围
  deadline          本轮共享截止时间
```

复用 correlation_id 关联到 run_id；事件增加 parent_event_id，能够解释“哪条消息触发了这次教学响应”。固定 Agent 的 handler 同时记录开始、结束、失败与耗时。

learner_id 不放进模型可自行选择的工具参数。现有 API 中 learner_id 仍由请求提供，面向真实多用户部署时必须接入服务端认证主体与学习者映射；闭包注入只能限制模型，不能替代 API 鉴权。

### 完成契约：两个状态轴

```text
execution_status:
  running | completed | failed | cancelled | exhausted

dialogue_state:
  answered | awaiting_student
```

Tutor 可以返回：

```json
{
  "execution_status": "completed",
  "dialogue_state": "awaiting_student",
  "reply": "你上次把完成时间和过去时间混在一起了。这里有明确的过去时间吗？",
  "pending_question_id": "pq-1",
  "source_refs": ["message:m-17", "evidence:e-9"],
  "learning_effect": "assistance_only"
}
```

完成条件由 Harness 判断：

- 本轮模型正常停止，或明确产生等待学生回答的终止动作。
- 所需工具已取得结果；当前请求需要的教学回复/测验结果通过结构校验。
- 必须执行的领域 handler 均成功结束。
- 状态、受助证据、公开消息、可重放结果提交成功。

队列排空或模型输出“完成”都不足以证明成功。教学链路尤其不能将执行 completed 解释为学生掌握知识；掌握度仍由独立、合规的评估证据决定。

## 3. 跨会话追问到保存轨迹的完整链路

示例：学生开启新会话后问：“上次你说我总把现在完成时弄错，再讲一下？”

### 第一步：绑定线程与接续关系

前端发送 session_id、可选 thread_id、request_id、问题及可选 quiz_id。服务端验证会话、线程和测验的学习者归属。

有明确 thread_id 时直接接续；只有知识点时检索该学习者的相关线程；“上次”有多个候选时询问澄清，避免默默把最近一条历史当成准确指代。

### 第二步：构建最小必要上下文

复用当前 learner model、知识图谱与 Tutor 近期历史，新增 ContextBuilder：

1. 固定系统约束、工具说明和本轮问题。
2. 当前 BKT、测验模式、受助状态等结构化事实。
3. 当前线程最近对话。
4. 与本轮相关的旧错题、旧教学片段、带来源的线程摘要。

结构化评估事实的权威性高于模型生成的“学生可能存在某种误解”。历史对话和摘要作为低优先级数据输入，不能变成新的系统指令。

初始检索可用 SQLite FTS5、知识点和时间过滤；相关性需在 EduAgent 数据上验证。先用透明可解释的检索，再根据漏召回数据决定是否增加 embedding。

上下文按模型预算配置，预留输出及工具结果空间。记录候选、选中和省略的 source_refs、选择原因、token 估计方式及预算；估计值不得冒充供应商精确 token 计数。

### 第三步：只给 Tutor 必要工具

| 工具 | 用途 | 边界 |
|---|---|---|
| search_learning_history | 搜索旧线程、错题、教学摘要 | 仅当前学习者，返回摘要、来源 ID 和分页信息 |
| read_learning_history | 读取选中的公开教学证据 | 再次验证归属，限制长度，不暴露内部工具载荷 |
| get_knowledge_context | 获取概念及前置知识关系 | 复用已有知识图谱 |
| get_quiz_context | 获取当前题目的允许公开内容 | 隐藏 correct_index、参考答案及解释 |
| request_hint | 在允许的练习模式中请求分级提示 | 复用现有 support 语义，记录受助，不能嵌套调用持锁的 harness.run |
| ask_student | 需要澄清或引导时结束本轮并等待学生 | 创建 pending_question，下一次用户消息接续 |

其中基础学习状态由 ContextBuilder 直接提供，不必每次用工具获取。request_hint 第一阶段可保留为确定性前端操作，先把 Tutor 的只读检索和 ask_student 跑通；确认副作用事务后再暴露模型调用。

工具结果统一：

```text
ToolResult
  tool_call_id
  status: ok | denied | error
  data
  source_refs
  effect_id: optional
  retryable
  terminal: optional
```

权限按 Agent、当前学习者、测验模式和具体操作判定。拒绝调用也计入预算并写轨迹；工具声明允许不代表任意资源都可访问。

LLMService / provider adapter 需要新增原生结构化工具调用接口。文本模板回退仍可保留，但标记 execution_mode，不能将文本中出现的“调用工具”伪装成真实调用。

### 第四步：有界工具循环

```text
构建上下文
  → model
  → 有工具调用：校验参数与权限 → 执行 → 回填工具结果 → model
  → 正常最终回复 / ask_student：结束本轮
  → 超时、轮数或输出预算耗尽：exhausted
```

初始可配置为最多 3 次模型请求、4 次工具调用，同一批工具顺序执行；具体参数通过评测调整。每个模型请求及工具执行共用剩余 deadline。

当前 EventBus 默认 handler 超时 15 秒，Harness 超时 45 秒。增加多轮 Tutor 前，必须同步配置 Tutor handler 与模型、工具预算，避免外层 15 秒先截断整条链路。

同一工具调用 ID 重复出现时不重复执行副作用。超时后的迟到结果不得再修改学习状态。远程工具若不能真正取消，须有幂等键及提交时的 attempt 校验。

### 第五步：记录受助和回复

绑定当前题目后，只要生成了与本题相关的教学帮助，就追加 assistance 证据。对话帮助与 hint 按钮使用统一口径；随后答对也只能视为受助练习，不能由 Tutor 更新 BKT。

未知或未绑定题目时，先确认上下文或提供一般概念讲解；受保护测验通过服务端模式限制具体帮助。不能仅依赖模型自报“我没有透露答案”。

学生之后完成一道独立新题，由 Assessment 产生评估证据，并通过 thread_id / knowledge_id 与先前教学关联；由此形成可观察的“支架 → 行为 → 结果”链，但单条链仍不足以证明教学因果效果。

### 第六步：持久化与重放

成功事务中一并提交：

- learner checkpoint、quiz 更新；
- 公开用户消息和教学回复；
- 学习证据、pending_question；
- 本轮成功轨迹及可重放结果。

失败时回滚学习状态，保留 attempt 的诊断轨迹；失败内容不进入成功教学记忆。请求重试可重放已提交结果，失败重试另开 attempt。当前整轮重试机制可以继续使用。

摘要生成作为提交后的派生任务，不阻塞教学主链路。摘要必须带 source_refs、覆盖范围、生成版本和有效性标记；模型误解描述只能作为可修订观察。摘要失败时继续使用原始证据。

## 4. 最小存储扩展

建议先延续当前 Harness SQLite，避免另建一套与 checkpoint 竞争的学习事实源。为已有 runs 增加元数据，用迁移和显式列名操作替换依赖表列顺序的 INSERT。

| 表/逻辑记录 | 关键字段 | 作用 |
|---|---|---|
| runs（已有，扩展） | learner、request、run_id、session_id、thread_id、status、dialogue_state、result | 去重、接续和结果重放 |
| run_attempts | attempt_id、run_id、attempt_no、status、stop_reason、started_at、finished_at | 保留每次失败及重试 |
| conversation_messages | message_id、learner、session_id、thread_id、run_id、role、visible_content | 长期公开教学历史 |
| learning_evidence | evidence_id、learner、thread_id、quiz_id、run_id、kind、assisted、outcome、source_refs | 受助和独立评估证据 |
| run_steps | attempt_id、seq、event_id、parent_event_id、agent、kind、tool_call_id、status、duration、source_refs | 执行轨迹 |
| thread_memory | learner、thread_id、knowledge_id、summary、source_refs、covered_through、version | 派生摘要及跨会话主题记忆 |
| pending_questions | question_id、learner、thread_id、origin_run_id、status、answer_message_id | 等待回答与恢复 |

轨迹记录模型请求概要、公开回复、工具名、经筛选的参数/结果、耗时、可用 usage、拒绝原因及状态变更；不依赖隐藏思维链。内部 trace 与可展示学习历史分开，答案密钥、凭据及受保护答案不能进入历史搜索或公开 trace API。

第一阶段可成功时批量保存步骤、正常异常时保存失败步骤。进程硬退出前未提交的细粒度轨迹仍可能丢失，应如实记录 interrupted，不能宣称已有消息边界恢复。若需要完整崩溃审计，再增加逐步持久化。

## 5. Hooks 的最小范围

| Hook | 内容 | 失败处理 |
|---|---|---|
| before_model | ContextBuilder、上下文预算、测验限制 | 必要边界失败则中止；可选历史检索失败则明确降级 |
| before_tool | 注册校验、参数 schema、角色及资源范围、预算 | 拒绝调用，不进入工具 handler |
| after_tool | 标准化结果、记录受助与执行步骤 | 业务证据写入失败则整轮失败；结果不得伪装成功 |
| after_run | 摘要刷新、质量采样、非关键遥测 | 已提交业务结果保持有效，派生工作独立重试 |

关键轨迹、学习状态和结果提交由 Harness 显式负责，不放进允许忽略异常的遥测 hook。OpenMAIC 将 onRunEvent 的异常记日志并忽略，而必须持久化的 session entry 写失败会阻止成功结算，这个区分值得保留。

## 6. 实施顺序与验收

### 第一阶段：跨会话事实与证据

实现 session/thread 接续、消息与证据表、ContextBuilder、只读历史检索、普通提问受助记录及执行步骤。继续使用现有文本 LLM。

验收：

- 新会话能找到上次相关错题，进程重启后仍可读取来源。
- A 学生不能读 B 学生的会话、题目或证据。
- 同 request_id 重发不重复追加消息或更新掌握度。
- 普通提问受助后答对，不计为独立掌握证据。
- 历史为空或歧义时准确说明，不编造“你上次说过”。

### 第二阶段：Tutor 工具运行

新增 provider 原生工具协议、tool registry、运行预算、hooks、ask_student、公开轨迹读取与前端展示。request_hint 在事务设计完成后再接入。

验收：

- scripted model 真实走完 search → read → final，并保存 tool_call/tool_result。
- 违法参数、越权、重复调用、超时、输出截断都有可辨认结果。
- ask_student 后本轮正常完成，模型不继续替学生回答；下一条消息正确接续。
- 工具成功但最终提交失败时，学习状态回滚，副作用不会在重试中重复。
- 用少量真实模型轨迹验证历史命中、引用正确、任务完成与受助边界；模板回退与真实调用分开统计。

### 第三阶段：由实际瓶颈决定

加入摘要增量更新、检索评测，必要时再引入 embedding。只有长时间任务、后台课程生成或多 worker 成为需求时，才参考 OpenMAIC 的租约、消息边界 checkpoint、悬空工具结果修复和中途恢复。

目前不需要 A2A 协议、消息中间件、动态角色竞争或开放工具市场。教学方法适合先做内部版本化策略配置；确有多个可复用教学流程后，再引入轻量教学 skills。

## 7. 对项目定位的作用

完成前两阶段后，可以将项目描述为：

> 围绕多 Agent 教学系统构建轻量 Harness，统一跨会话上下文、受控工具执行、任务终止与学习证据持久化；通过执行轨迹关联教学支架、受助行为与独立评估结果。

当前可描述已经实现并通过协议测试的工具循环、长期检索和执行记录；真实模型质量与教学效果仍待验证，中途恢复也尚未实现。

## 当前验证结果

- 后端：`python -m pytest tests -q`，124 项通过。包含 23 项新增 Harness、原生 provider 协议及 API 边界测试；保留一项已有测试类收集提示。
- 前端：`npm run build`，TypeScript 与 Vite 构建通过；存在构建包大小提示。
- 浏览器：真实发送提问并显示持久化对话；开始新会话后旧内容显示“之前的会话”。浏览器后续视口变为 0×0，未将之后的提交或轨迹按钮操作视为验证完成。
- 事务：注入必要历史写入失败，验证公开消息、受助状态和学习 checkpoint 全部回滚；重试后成功且保留两次 attempt。
- 预算与隔离：覆盖模型轮数、工具次数、上下文预算、输出截断、重复 tool_call_id、截止时间取消、严格参数校验和跨学习者来源访问。
- `git diff --check` 通过；浏览器验证使用的临时服务器已停止，临时测试数据库已清理。

测试中使用 scripted 模型和 mock SDK，无真实模型调用、付费请求或教学效果验证。此处验证的是执行协议与状态边界。
