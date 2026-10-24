# Tutor 真实模型首批评测结果

生成时间：2026-10-24T20:56:25.140435+00:00。模型：`deepseek-flash`，思考关闭。

固定脚本模拟学生；本批测量 Agent 行为、状态契约和回复质量，不能证明真实学生学习效果。
自动硬检查与语义审阅分开。`review_pending` 表示尚未完成语义审阅，不等同于整体通过。

| 方向 | 有效场景 | 自动检查全部通过 | 语义待审阅 | 自动检查失败 |
| --- | ---: | ---: | ---: | ---: |
| Agent 行为（主评测） | 2 | 2 | 2 | 0 |
| 教学回复（辅助） | 1 | 1 | 1 | 0 |

模型请求：6/6；输入 Token：7576；输出 Token：1163。
估算费用：0.008214–0.016428 元（闲时至高峰定价区间，实际扣费以供应商账单为准）。未确认请求预留：0.000000 元。

| 场景 | 结果 | 自动失败项 | 工具路径 |
| --- | --- | --- | --- |
| live-03-participle-hint | review_pending | 无 | 直接回复 |
| live-05-missing-sentence-followup | review_pending | 无 | ask_student / 直接回复 |
| live-06-reading-goal-cross-session | review_pending | 无 | ask_student / get_knowledge_context |

## live-03-participle-hint · 定位 have 后动词形式的错误

**s1 学生输入**：我准备选 A 的 wrote，因为 write 的过去式是 wrote。但我不太确定，先别告诉选哪个，指出我应该检查什么动词形式。

**s1 实际回复**：

你现在的思路是“按过去式来选”，这里需要先停下来检查一个关键点：**这个空前面有没有助动词，以及它要求的是哪一类动词形式。**

检查步骤：

1. **看空格前的结构**：句子里空格前是 “have”。这里的 have 不是表示“拥有”的实义动词，而是构成某种时态的助动词。
2. **判断语法类别**：助动词 have 后面要求的是**过去分词**，而不是过去式。过去式通常单独作谓语（如 “I wrote the report.”），而 “have + 过去分词” 构成的是另一种时态，表达与现在有关的完成意义。
3. **区分两种形式**：对 write 这类不规则动词，过去式和过去分词要分开记。你已确认过去式是 wrote，那么请再单独查一下 write 的**过去分词**形式是什么。
4. **回填验证**：把查到的过去分词放进 “have ____ the report”，看它是否符合“助动词 + 过去分词”的结构。

所以你要检查的不是“write 的过去式”，而是“write 的过去分词”，以及这个空是否处在 have 之后。答案由你自己判断。


硬检查：
- H1 `passed`：等于 completed；若有 ask_student，其 batch_size=1 且有 pending_question_id。
- H2 `passed`：assisted=true、attempts=0、solved=false、revealed=false。
- H3 `passed`：所有 KnowledgeState 字段保持不变。
- H4 `review_pending`：指出 have 后形式问题；没有肯定 A 正确，也没有直接提供 B、have written 或目标词 written 作为答案。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。

## live-05-missing-sentence-followup · 缺少句子时提问并处理补充信息

**s1 学生输入**：这句话为什么用这个时态？我不知道从哪里判断。

**s1 实际回复**：

请把你要分析的那句话（连同上下文，如果有的话）发给我，我需要看到原句才能判断它的时态。

**s2 学生输入**：原句是 She has lived here since 2020. 她现在仍住在这里，我不懂 since 的作用。

**s2 实际回复**：

这句是**现在完成时**（has lived），判断依据不是 since 这个词本身，而是“过去起点 + 延续到现在”这个时间关系。

**句子结构**
- `has lived`：现在完成时，表示“从过去某时开始、一直持续到现在”的状态。
- `since 2020`：since 后面接**时间点**，标出这段延续的**起点**是 2020 年。
- 合起来：从 2020 年起到现在，居住这个状态一直没断，所以“她现在仍住在这里”正是这个时态本身带来的含义，不是额外补充的信息。

**since 的作用**
它只做一件事：**划定起点，并把这段时间一直拉到“现在”**。它天然要求主句用一个“与现在有联系”的形式，因此常和现在完成时搭配。对比一下：
- `She lived here in 2020.` 一般过去时，只说 2020 年那段时间的事，不涉及现在。
- `She has lived here since 2020.` 起点 2020，延续至今。

**判断路径（可自查）**
1. 找时间信息：是**时间点**（2020、last year、Monday）还是**时间段**（for three years）？
2. 看这个时间是否**一直延伸到说话时的现在**。
3. 是 → 现在完成时；只讲过去某段、与现在无关 → 一般过去时。

注意：不要看到 since 就机械套完成时，关键还是“是否延续到现在”。比如 `Since you're here, let's start.` 里的 since 是“既然”，跟时间无关。


硬检查：
- H1 `passed`：status=completed、dialogue_state=awaiting_student、pending_question_id 非空；ask_student 为单独调用。
- H2 `passed`：status=completed、dialogue_state=answered，answered_question_id 等于 s1.pending_question_id。
- H3 `passed`：s1 待答记录的 answered_by 非空，场景结束没有未回答的该问题。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：s1 问题针对缺失例句；s2 正确解释 since 引出的起点和与现在相连的状态。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。

## live-06-reading-goal-cross-session · 跨会话接续阅读目标的澄清

**s1 学生输入**：我做阅读题时不知道该先通读还是先定位。你先问我一个问题，弄清这次阅读要找什么，再给我方法。

**s1 实际回复**：

这次阅读你要找的是什么——是某一处具体信息（如某个数字、人名、原因），还是全文主旨/作者态度这类整体性问题？

**s2 学生输入**：这次只要找火车几点出发这个具体细节，不是文章主旨。

**s2 实际回复**：

明确了：这次是**找具体细节（火车出发时间）**，不是主旨题。这类题不需要先通读全文，用“定位式略读”更省时间。

**具体做法（按顺序）**

1. **先看题干，圈出关键词。** 把“火车几点出发”转成原文可能出现的词：时间词（departure / leaves / time / schedule / timetable）、交通词（train / platform）。题干里如果有专有名词、数字、大写词，优先用它们，因为它们最不容易被同义替换。

2. **扫读（scanning），不逐句读。** 眼睛沿段落做 Z 字形快速移动，只找两类东西：
   - 数字和时间格式（如 7:45、08:30、a.m./p.m.）；
   - 上面圈出的关键词或其同义表达。
   这一步允许跳过整句，不要在心里默读翻译。

3. **找到候选位置后，只精读那一两行。** 确认这个时间是“出发”而不是“到达”“检票”“换乘”。常见陷阱：原文同时出现到达时间和出发时间，或者出现两个班次。

4. **核对题干问的是哪个方向。** 如果问“最早一班几点出发”，就要在几个时间点里比较，而不是抓到第一个就填。

**自查三个点**：① 我找的是 departure 还是 arrival？② 这个时间属于哪一班车？③ 有没有第二个同类数字被我漏掉？

**什么时候才需要通读**：只有主旨题、作者态度题、或者“这段主要讲什么”这类整体性问题，才值得先快速通读首尾段和每段首句。细节题先定位，通读是浪费。

如果原文里时间是用文字写的（如 “a quarter past seven”），扫数字会漏掉，这时要同时留意英文数词和 past/to 结构。


硬检查：
- H1 `passed`：completed、awaiting_student，pending_question_id 非空。
- H2 `passed`：session_id 不同、thread_id 相同；s2.answered_question_id 等于 s1.pending_question_id。
- H3 `passed`：等于 answered；旧待答问题已关闭。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：方法与定位具体出发时间匹配，正确区分找主旨与找细节。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。
