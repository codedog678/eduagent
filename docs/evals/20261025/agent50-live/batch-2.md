# Tutor 真实模型首批评测结果

生成时间：2026-10-24T21:41:34.829354+00:00。模型：`deepseek-flash`，思考关闭。

固定脚本模拟学生；本批测量 Agent 行为、状态契约和回复质量，不能证明真实学生学习效果。
自动硬检查与语义审阅分开。`review_pending` 表示尚未完成语义审阅，不等同于整体通过。

| 方向 | 有效场景 | 自动检查全部通过 | 语义待审阅 | 自动检查失败 |
| --- | ---: | ---: | ---: | ---: |
| Agent 行为（主评测） | 7 | 5 | 5 | 2 |
| 教学回复（辅助） | 0 | 0 | 0 | 0 |

模型请求：15/42；输入 Token：18219；输出 Token：2611。
估算费用：0.015117–0.030235 元（闲时至高峰定价区间，实际扣费以供应商账单为准）。未确认请求预留：0.000000 元。

| 场景 | 结果 | 自动失败项 | 工具路径 |
| --- | --- | --- | --- |
| live-15-ongoing-now | review_pending | 无 | ask_student / 直接回复 |
| live-16-passive-recipient | review_pending | 无 | ask_student / 直接回复 |
| live-17-submit-recipient | failed | H1,H2,H3 | 直接回复 |
| live-18-ambiguous-tense-resolved | failed | H1,H2,H3 | get_knowledge_context → search_learning_history |
| live-19-opening-time | review_pending | 无 | ask_student / 直接回复 |
| live-20-main-idea | review_pending | 无 | ask_student / get_knowledge_context |
| live-21-ticket-exception | review_pending | 无 | ask_student / get_knowledge_context |

## live-15-ongoing-now · 时态：补充正在发生的动作

**s1 学生输入**：这里为什么用这个动词形式？稍后我补上句子。

**s1 实际回复**：

请把你要问的那句原句发给我（连同上下文一两句更好），我才能具体解释这里为什么用这个动词形式。

**s2 学生输入**：句子是 Look! The children are playing outside now. 动作正在发生。为什么是 are playing？

**s2 实际回复**：

这句话用 **are playing**，是因为它描述的是**此刻正在进行、尚未结束**的动作。

**1. 时间参照点 = 现在**

句首的 **Look!** 和句末的 **now** 都把观察的时间点定在“说话的这一瞬间”。说话人是在现场看到孩子们正在玩，而不是在回忆或预测。

**2. 动作性质 = 进行中的过程**

play 是一个可以持续的动作。用进行体（be + doing）表示“动作已经开始、还没结束，正处于过程中”，画面感是“玩”这个动作正在展开。

**3. 结构上必须用 be 动词**

现在进行时的形式是 **am/is/are + 动词-ing**。主语 the children 是复数，所以用 **are**，再加 playing（play 直接加 -ing，不需要双写）。

**对比一下差别：**

- The children **are playing** outside now. → 此刻正在玩（进行中）
- The children **play** outside every day. → 经常玩（习惯，一般现在时）
- The children **played** outside yesterday. → 昨天玩过（过去，与现在无直接联系）

所以这里不是“now 这个词决定时态”，而是**说话人把动作放在“现在这一刻”这个参照点上，并且强调它正在进行**，两个条件合起来才选 are playing。

顺带提醒一个常见错误：不要写成 *The children playing outside*，进行时不能省掉 be 动词。


硬检查：
- H1 `passed`：status=completed、dialogue_state=awaiting_student、pending_question_id 非空；ask_student 为单独调用。
- H2 `passed`：status=completed、dialogue_state=answered，answered_question_id 等于 s1.pending_question_id。
- H3 `passed`：s1 待答记录的 answered_by 非空，场景结束没有未回答的该问题。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：s1 索取原句；s2 解释此刻进行的动作与 be+现在分词，不能说 playing 是过去分词。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。

## live-16-passive-recipient · 被动：补充承受动作的主语

**s1 学生输入**：这里为什么是被动？我还没给你原句。

**s1 实际回复**：

请把你说的那个原句（或包含它的那段材料）发给我，我来具体解释为什么用被动。

**s2 学生输入**：原句是 The window was broken by the storm last night. 窗户不是动作发出者。

**s2 实际回复**：

你补充的原句是：

**The window was broken by the storm last night.**

这句用被动，核心原因不是“窗户不是动作发出者”这一条，而是下面几点合在一起：

1. **谁受影响、谁是话题中心**：说话人关心的是 the window（窗户怎么样了），所以把它放在句首当主语。窗户本身不能“打破”东西，它只能“被打破”，因此谓语要用被动形式 was broken。

2. **被动的基本结构**：be + 过去分词。这里 was 是过去式，配合 last night 指向过去的一个具体时间点；broken 是 break 的过去分词。整句意思是“窗户昨晚被暴风雨打破了”。

3. **by the storm 的作用**：by 短语引出动作的施动者（真正“打破”窗户的东西）。被动句里施动者可以出现，也可以省略；这里出现是为了说明原因。

4. **为什么用过去时**：last night 把事件定位在过去，且与现在没有直接联系，所以用 was 而不是 is。

关于你说的“窗户不是动作发出者”：这个观察方向是对的，但它只是被动的一个表面特征。更准确的表述是——**主语是动作的承受者，而不是执行者**。判断被动要看主语和谓语动词的关系，而不是只看主语“是不是人/物”。

顺带提醒一个常见误区：不能只凭 by 或某个时间词就断定用被动。比如 The storm broke the window last night. 同样有 last night，但主语 the storm 是执行者，就该用主动。所以关键是先确定“谁承受动作、句子想以谁为话题”。


硬检查：
- H1 `passed`：status=completed、dialogue_state=awaiting_student、pending_question_id 非空；ask_student 为单独调用。
- H2 `passed`：status=completed、dialogue_state=answered，answered_question_id 等于 s1.pending_question_id。
- H3 `passed`：s1 待答记录的 answered_by 非空，场景结束没有未回答的该问题。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：s1 索取原句；s2 说明 window 承受动作、was 对应过去、broken 是过去分词。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。

## live-17-submit-recipient · 搭配：补充接收者结构

**s1 学生输入**：我在一个搭配里加了介词，不确定是否多余，原句待会发。

**s1 实际回复**：

你还没把原句发来，我无法判断那个介词是否多余——搭配里介词是必需、可选还是多余，取决于具体动词/名词和整个结构，脱离原句只能空谈。

请把原句（含你加的介词和完整上下文）发给我。

步骤状态：`blocked_by_prior_step`；原因：``。

硬检查：
- H1 `failed`：status=completed、dialogue_state=awaiting_student、pending_question_id 非空；ask_student 为单独调用。
- H2 `failed`：status=completed、dialogue_state=answered，answered_question_id 等于 s1.pending_question_id。
- H3 `failed`：s1 待答记录的 answered_by 非空，场景结束没有未回答的该问题。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：s1 索取原句；s2 区分 report 是提交物、office 是接收方，不能把该 to 判为多余。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。

## live-18-ambiguous-tense-resolved · 时态：补充语境后消除歧义

**s1 学生输入**：单看 finished 和 have finished 我不知道该选哪个，我还没给时间背景。

**s1 实际回复**：

你的判断是对的：单看 finished 和 have finished，确实无法决定选哪个，因为这两个形式的差别不在“动作本身”，而在**说话人如何把这件事和“现在”联系起来**。

**核心区别**

- **finished（一般过去时）**：把动作当作一个已经结束、与现在切断的过去事件。说话人关注的是“那时发生了什么”。
- **have finished（现在完成时）**：把动作的结果或状态延续到现在的参照点。说话人关注的是“现在这件事处于完成状态”。

**所以真正决定选择的是语境，而不是某个时间词**

判断时问自己两个问题：

1. **现在有没有一个“结果”在起作用？**
   - I **have finished** my homework, so I can go out now.（作业完成的状态支撑“现在能出去”）
   - I **finished** my homework at eight and then watched TV.（只是叙述过去的事件序列）

2. **有没有明确的、已结束的过去时间点？**
   - 有明确过去时间点（yesterday, at eight, last week, in 2019）→ 一般用 finished。
   - 但这不是机械规则：即使出现时间词，如果重点是“到现在为止的结果”，仍可能用完成时。反过来，没有时间词也不自动等于完成时——纯粹叙述往事时，finished 同样可以不带时间词。

**一个实用的自查步骤**

先在心里补一句“这句话想说明什么”：

- 想说明“现在处于什么状态/现在能做什么/到目前为止的成果”→ 倾向 have finished。
- 想说明“过去某个时刻发生了什么、事情怎么一步步发生”→ 倾向 finished。

如果你把要判断的那句话（或前后文）发给我，我可以直接帮你定夺并说明理由。

步骤状态：`blocked_by_prior_step`；原因：``。

硬检查：
- H1 `failed`：status=completed、dialogue_state=awaiting_student、pending_question_id 非空；ask_student 为单独调用。
- H2 `failed`：status=completed、dialogue_state=answered，answered_question_id 等于 s1.pending_question_id。
- H3 `failed`：s1 待答记录的 answered_by 非空，场景结束没有未回答的该问题。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：s1 索取句子或时间语境；s2 依据 yesterday 解释一般过去时，不能因工作完成就强推完成时。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。

## live-19-opening-time · 阅读：定位博物馆开门时间

**s1 学生输入**：这次阅读我不知道先怎么读。先问我一个问题确认题目目标，再给方法。

**s1 实际回复**：

这次阅读任务的目标是什么——是要在限定时间内找出某个具体信息（如某个数字、人名、某句细节），还是快速把握全文大意和结构？

**s2 学生输入**：找博物馆周六几点开门这个细节，不需要全文主旨。

**s2 实际回复**：

学生已补充任务目标：限时找具体信息（周六开门时间），不需要主旨。下面直接给方法。

## 先明确这类任务的性质

这是**扫读（scanning）**，不是略读（skimming）。略读求大意和结构，扫读求定位一个具体事实。两者读法完全不同：扫读时**不要从头逐句读**，也不要先读全文再找。

## 可执行步骤

1. **先锁定关键词**：把问题里的信息点转成"目标词形"。周六开门时间 → 你要找的是 `Saturday` / `Sat.` / `weekend` 这类词，以及 `open` / `hours` / `opening times` 这类词。数字本身（如 9:00）不能作为搜索词，因为你不知道它是几点。

2. **用版式缩小范围**：博物馆类文本的开放时间通常在固定位置——页面底部、侧栏、"Visitor information / Opening hours / Plan your visit" 小标题下。先扫标题和加粗词，跳到对应区块，再在区块内找 `Saturday`。

3. **视线走 Z 字形，不读句子**：眼睛沿行快速掠过，只抓词形轮廓，看到 `Sat` 才停下来读那一行。停下来时读整行，因为时间常和星期分开写（如 "Sat–Sun: 10 am – 6 pm"）。

4. **核对限定条件**：找到时间后确认它对应的是**周六**，不是平日或周日；注意是否有节假日、季节（summer/winter hours）例外说明。

5. **限时控制**：给自己设一个上限（如 60–90 秒）。超时就换区块（如从页首换到页尾），而不是回头重读同一段。

## 自查要点

- 我是不是在"读句子"而不是"扫词形"？如果是，说明还在略读模式。
- 我找到的时间是否明确绑定在 Saturday 上？
- 有没有漏掉括号或脚注里的例外？

一句话概括：**扫读靠词形匹配和版式预判，不靠理解句子。**


硬检查：
- H1 `passed`：completed、awaiting_student，pending_question_id 非空。
- H2 `passed`：session_id 不同、thread_id 相同；s2.answered_question_id 等于 s1.pending_question_id。
- H3 `passed`：等于 answered；旧待答问题已关闭。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：s1 只问一个关于目标的问题；s2 围绕 museum、Saturday、open/opening hours 定位，检查周末时段，不凭空给开门时间。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。

## live-20-main-idea · 阅读：从细节目标切换到主旨

**s1 学生输入**：这次阅读我不知道先怎么读。先问我一个问题确认题目目标，再给方法。

**s1 实际回复**：

这次阅读任务的具体目标是什么——是要回答细节题、概括主旨，还是限时快速判断正误？

**s2 学生输入**：这次问整篇文章主要讲什么，不是找日期或数字。

**s2 实际回复**：

你的目标是概括主旨，也就是问“整篇文章主要讲什么”，而不是找日期或数字。这类任务用略读（skimming）最合适，重点是抓住整体意思，不必逐句精读。

**具体做法（按顺序）：**

1. **先看标题、副标题和首段**：标题通常直接点明主题，首段往往交代“这篇文章要谈什么”。
2. **读每段的第一句（有时加上最后一句）**：英文说明文和议论文的段落主题句多在段首，串起来就是文章骨架。
3. **扫一眼反复出现的词**：同一个词或同义表达多次出现，通常就是核心话题。
4. **看结尾段**：常用来总结观点或给出结论，帮你确认主旨。
5. **跳过细节**：人名、年份、数字、举例、引语先略过，它们服务于主旨，不是主旨本身。

**概括时自查两点：**
- 你的一句话能否覆盖全文各段，而不是只说了某一段？
- 是否停留在“文章提到了什么”，而没有说“文章在讲什么、想说明什么”？主旨句通常要包含“对象 + 关于它的核心观点”。

**时间分配参考**：一篇中等长度的文章，略读抓主旨一般控制在全文阅读时间的四分之一左右，先形成整体印象，再决定是否需要回看某段。


硬检查：
- H1 `passed`：completed、awaiting_student，pending_question_id 非空。
- H2 `passed`：session_id 不同、thread_id 相同；s2.answered_question_id 等于 s1.pending_question_id。
- H3 `passed`：等于 answered；旧待答问题已关闭。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：s1 只问一个关于目标的问题；s2 先看标题、首尾段及各段主题句，再概括中心；不能只扫描一个数字。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。

## live-21-ticket-exception · 阅读：核对票价例外条件

**s1 学生输入**：这次阅读我不知道先怎么读。先问我一个问题确认题目目标，再给方法。

**s1 实际回复**：

这次阅读任务的目标是什么——是要快速抓住文章大意（略读），还是要在文中定位某个具体信息（扫读）？

**s2 学生输入**：我要找 12 岁儿童周末门票多少钱，文章可能把周末价格和儿童优惠分开写。

**s2 实际回复**：

你的目标已经明确：**在文中定位“12 岁儿童 + 周末”对应的票价**，这属于**扫读（scanning）**，不是略读。略读是快速抓大意，扫读是带着关键词找具体信息。

具体做法：

1. **先确定要找什么**：两个条件必须同时满足——年龄（12 岁 / child / children / age）和时段（weekend / Saturday / Sunday）。价格单位（$、£、yuan、per ticket）是第三个线索。

2. **不要逐句读**。眼睛沿段落快速移动，只捕捉数字和货币符号，遇到数字再回头看它前面的修饰语。

3. **注意分开写的情况**：文章常把“周末价”和“儿童优惠”放在不同位置。所以先找到所有价格数字，再逐个确认它属于哪个条件。比如看到 “Weekend: $15” 和 “Children (under 12): 50% off”，就要判断 12 岁是否算在优惠范围内——注意 under 12 是“不满 12 岁”，12 岁本身可能不适用，这类边界词要读准。

4. **留意小标题和表格**：票价信息常在 “Prices / Tickets / Admission” 这类小标题下，或直接排成表格。先扫这些小标题能省很多时间。

5. **找到后核对一次**：确认这个价格同时满足年龄和时段两个条件，而不是只满足其中一个。

自查时可以用一句话检验：你找到的那个数字，前面有没有同时出现年龄条件和周末条件？如果只有一个，说明还没找全，需要继续扫。


硬检查：
- H1 `passed`：completed、awaiting_student，pending_question_id 非空。
- H2 `passed`：session_id 不同、thread_id 相同；s2.answered_question_id 等于 s1.pending_question_id。
- H3 `passed`：等于 answered；旧待答问题已关闭。
- H4 `passed`：所有 KnowledgeState 字段保持不变。
- H5 `review_pending`：s1 只问一个关于目标的问题；s2 扫描 age/children/weekend/price 等线索，合并年龄与周末条件核对，不能只取第一个金额。

质量分：准确性、针对性、可操作性均待审阅。详细状态、用量与 Trace 见同名 JSON。
