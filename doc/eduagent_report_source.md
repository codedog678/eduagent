# EduAgent — 多Agent智能教育与个性化学习系统

## 项目概述

EduAgent 是一个基于多Agent协作架构的AI英语学习系统，面向教育技术学专业的课程设计/毕业设计项目。系统采用事件驱动的Mesh架构，通过4个专业AI Agent的协作，为学习者提供个性化的英语学习体验。

核心定位：构建一个"可运行、可测试、稳定可演示"的智能教育原型系统。

## 研究背景与动机

### 教育技术领域的AI趋势
- 大语言模型（LLM）正在深刻改变教育场景
- 传统智能教学系统（ITS）面临扩展性和个性化不足的挑战
- 多Agent协作是实现复杂教育任务的有效范式

### 项目目标
- 探索多Agent架构在个性化学习中的应用
- 整合经典教育算法（BKT、SM-2、知识图谱）与现代LLM技术
- 实现一个功能完整、架构清晰的教学原型系统

## 系统架构

### 事件驱动Mesh架构
系统采用事件驱动的Mesh架构，Agent之间通过EventBus进行异步通信，无中心协调器。

工作流程：
1. 用户提交答案 → REST API接收请求
2. EventBus发布STUDENT_SUBMISSION事件
3. 4个Agent各自订阅感兴趣的事件，并行处理
4. 各Agent发布结果事件（如MASTERY_UPDATED、TEACHING_RESPONSE）
5. 前端通过WebSocket实时接收所有事件流

### 技术栈
- 后端：Python 3.13+, FastAPI, SQLAlchemy 2.0, PostgreSQL 16
- 前端：React 18, TypeScript 5.5, Vite 5
- 基础设施：Docker Compose, Nginx
- LLM：Anthropic / OpenAI / MiniMax / DeepSeek + 模板回退

## 四大AI Agent

### 1. AssessmentAgent — 知识掌握评估
- 角色：基于BKT（贝叶斯知识追踪）算法评估学习者知识掌握度
- 订阅事件：STUDENT_SUBMISSION
- 发布事件：MASTERY_UPDATED, WEAKNESS_DETECTED, ASSESSMENT_COMPLETE
- 核心功能：更新掌握概率、分析错误模式（概念性/程序性/粗心）、识别薄弱知识点

### 2. TutorAgent — 个性化辅导
- 角色：苏格拉底式教学，提供渐进式提示
- 订阅事件：ASSESSMENT_COMPLETE, STUDENT_QUESTION, STUDENT_MESSAGE, ENGAGEMENT_ALERT
- 发布事件：TEACHING_RESPONSE
- 三级提示策略：
  - 第一级：元认知提示 — 引导自主思考
  - 第二级：脚手架提示 — 提供解题框架
  - 第三级：定向提示 — 直接给出关键信息

### 3. CurriculumAgent — 学习路径规划
- 角色：基于知识图谱和SM-2间隔重复算法规划学习路径
- 订阅事件：MASTERY_UPDATED, WEAKNESS_DETECTED, PACE_ADJUSTMENT
- 发布事件：NEXT_TOPIC, REVIEW_SCHEDULED, REVIEW_REMINDER
- 核心算法：拓扑排序确定学习顺序、SM-2安排复习计划、艾宾浩斯遗忘曲线预测记忆保持率

### 4. EngagementAgent — 参与度感知
- 角色：检测学习者情绪状态并触发干预
- 订阅事件：STUDENT_SUBMISSION, ASSESSMENT_COMPLETE, STUDENT_MESSAGE
- 发布事件：ENGAGEMENT_ALERT, PACE_ADJUSTMENT, ENCOURAGEMENT
- 6种情绪状态识别：专注、困惑、沮丧、无聊、疲劳、空闲
- 针对不同状态触发不同干预策略

## 三大核心教育算法

### BKT（贝叶斯知识追踪）
- 参数：P(L0)=初始掌握率, P(T)=学习率, P(G)=猜测率, P(S)=失误率
- 每次答题后通过贝叶斯公式更新掌握概率
- 产品优化：学习转换仅在答对时应用，避免"答错反而掌握度提升"的反直觉行为
- 掌握度分级：未开始 → 入门(0-0.3) → 发展(0-0.6) → 熟练(0.6-0.85) → 精通(0.85-1.0)

### SM-2 间隔重复
- 难度因子EF：根据答题质量动态调整
- 间隔天数递增：1天 → 6天 → 6×EF天 → ...
- 答题质量<3时重置间隔为1天
- 艾宾浩斯遗忘曲线：R = e^(-t/S) 预测记忆保持率

### 知识图谱（DAG）
- 有向无环图表示知识点间的前置依赖关系
- Kahn算法拓扑排序确定学习顺序
- get_ready_nodes()推荐当前可学的下一个知识点
- 英语学习知识图谱：7个维度、37个知识点

### 三大算法的协作关系
- BKT告诉系统"学生现在知道什么"
- 知识图谱告诉系统"接下来该学什么"
- SM-2告诉系统"什么时候该复习"

## 系统数据流与交互

### 一次完整的学习交互
1. 学生选择知识点，生成测验题目
2. 学生作答，答案提交到REST API
3. EventBus发布STUDENT_SUBMISSION事件
4. AssessmentAgent评估掌握度，发布MASTERY_UPDATED
5. TutorAgent根据评估结果生成教学反馈
6. CurriculumAgent更新学习路径，推荐下一个知识点
7. EngagementAgent分析情绪状态，必要时触发干预
8. 前端通过WebSocket实时展示所有Agent的反馈

### 数据库设计（6张核心表）
- learners：学习者档案
- knowledge_states：知识点掌握状态
- learning_records：答题历史
- review_items：SM-2复习计划
- event_logs：事件溯源日志
- agent_states：Agent运行时状态

## 前端界面

### 学习流程页面
- 知识点选择器：覆盖词汇、语法、阅读、写作等16个知识点
- 答题面板：生成测验、选择答案、提交作答
- 导师问答：自由文本提问
- 反馈面板：展示评估结果、导师回复、教学决策
- 事件流：按Agent分组的实时事件展示

### 分析仪表板
- 学习统计卡片
- 知识点掌握分布
- 薄弱知识点列表
- 学习曲线图

### 复习提醒
- 复习队列与记忆保持度仪表
- 紧急度标签
- 自动刷新（每30秒）

## 项目亮点与创新

### 架构创新
- 事件驱动Mesh架构：Agent自主订阅事件，无中心协调器
- 松耦合设计：Agent可独立开发、测试、部署
- 实时反馈：WebSocket实现毫秒级事件推送

### 教育算法整合
- 经典教育算法（BKT、SM-2）与现代LLM的融合
- 知识图谱驱动的个性化学习路径
- 多维度学习者建模

### 工程实践
- 完整的前后端分离架构
- Docker容器化部署
- 多LLM Provider支持与自动回退
- 事件溯源与链路追踪

## 总结与展望

### 项目成果
- 实现了4个AI Agent的协作学习系统
- 整合了3大经典教育算法
- 支持实时个性化学习反馈
- 具备完整的前后端界面

### 未来方向
- 扩展更多学科领域的知识图谱
- 引入更多Agent角色（如讨论伙伴、评估专家）
- 增强学习者画像与自适应学习
- 支持多模态学习内容
