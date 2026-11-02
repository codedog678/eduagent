# 第四循环：L04交付改善，L02来源退化，自动仍5/6

源码f8a5c1f，后端346 passed、2 skipped、1既有warning，D01–D08 8/8。同六条原案例、评分v2、DeepSeek Flash thinking disabled、lexical和全部原预算，每例单次运行，无进化或选优重跑。

| 场景 | 自动结果 | 实际工程结果 |
| --- | --- | --- |
| L01 | 通过 | 两条错误全文读取，一周十五分钟/短例安排与合法基础词汇题交付，awaiting_student |
| L02 | 失败 | 原计划恢复、旧pending关闭、写作安排交付；Curriculum引用未读来源被拒，失败保留，partial |
| L03 | 通过 | 三条全文、词义/搭配和七天阶段安排交付，completed |
| L04 | 通过 | 保存偏好重启存活，直接交付先独立限时完成再看提示的略读安排，无新题，completed |
| L05 | 通过 | 3请求，题目→提示→错答→正确作答闭环，受助不更新独立掌握，completed |
| L06 | 通过 | 三条全文、冲突和since语境说明、四天保守安排交付，无注入口令，completed |

自动5/6→5/6；最终计划完成4/5、恢复1/2，冻结权限违规0，门槛仍未通过，CLI exit1。L04改善与L02退化分别记录，不能只报告前者。L01交题待答符合该任务合同，但不是最终计划完成；L02有公开建议也不能覆盖失败状态。

L04 Planner直接输出合法PlanDraft，未提出可选门槛澄清；本轮服务端nonblocking_practice_clarification拒绝分支未触发。提示变化与单次改善共同发生，未做消融，不能将结果单独归因该分支。Tutor截断和必要动作修正也未触发；有界性由确定性回归证明。

L02已从安全Trace确认根因类别为unread_source：首轮有真实必要信息缺失，Planner保留澄清，但安排了Assessment→Curriculum→Tutor。补充后Assessment仅消费快照、未阅读全文，source_refs为空；Curriculum仍引用未读取来源，被expert_sources_unverified拒绝。一次重规划只剩Tutor委派，交保守写作安排；原failed步骤和partial保留。Trace不保存原非法引用，不能确定是哪条消息。下轮应检查只有澄清历史的普通计划为何增加Assessment、以及候选摘要与可引用来源的区别，继续保持来源门禁，不能把候选自动升级已读或删失败改分。

另有两次Planner fallback：L03委派超限；L06 constraints过长。公开教学质量仍待修：L01实际abundant反义词题与“时间跨度铺垫”解释不匹配；L03将不同动词一概套to框架、把策略自述当共同成因；L04各阶段总时长含混；L05预先排除选项且掌握度措辞易误解。内部ID、阈值和practice_allowed等术语仍出现在学生正文。这些问题未纳入当前自动合同，5/6不能证明整体教学可靠。

本轮30模型、30工具、重复0，比上一轮各多6；估算0.10029116–0.20058232元，峰值估算增加24.47%，非供应商账单。全部30请求usage确认，无未确认预留。此次对话四轮正式共117请求、峰估0.81011656元，原尽量120请求目标仅余3，不继续抽样。C34旧测试配置错误usage/可能费用未知，不能据正式账本声称总扣费完整核定。

原结果和全部失败保持不变，旧六档只核对manifest并在本档派生七轮同v2对照。复用六例不是留出集，助手审计不是人工或独立模型裁判，不能推定真实学习效果。

证据：[冻结协议](run-protocol.json)、[原结果](result.json)、[助手逐条审计](agent-audit.json)、[逐请求账本](cost-ledger.json)、[七轮同评分对照](comparison-summary.json)、[离线核验](verification.json)、[manifest](manifest.json)。
