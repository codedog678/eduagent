# 独立 SPEC 原报告的父侧定位补充

原报告 `/tmp/m3-task9-leaf-authenticity-spec-result.md` 原字节保留，
SHA `542fd8da3e1b25a77794f48ef39f7cfae1e998cb0dcb2ef90b0dca7abf4cb081`。
本页只更正源码定位，不修改报告、测试或 WHOLE SPEC 结论。
实际 review `9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f` 的
`python/core/distributed/health_evidence_identity.py` 共 51 行。

| 原表定位 | 实际定位与内容 |
| --- | --- |
| LEAF-2 helper L49-L56 | 分布算法 L16-L23；passed Canary 调用及 namespace L49-L51 |
| LEAF-3 helper L55-L56 | passed Canary 非 production namespace L49-L51 |
| LEAF-4 helper L53-L54 | passed Shadow 同 run 配对 L47-L48 |
| LEAF-6 helper L37、L51 | passed triggered 空集合 L35，拒绝 L37；非 pass 提前返回 L45-L46 |
| MIN-4 helper L51-L52 | 非 pass 合法诊断继续保留 L45-L46 |
| LEAF-8 promotion_repository L651-L754 | 原范围存在；共享函数调用约 L723-L727，后续仍重算评估，不把 evaluator 接入 Ops |

上述越界或不精确行号不能作为源码定位证明，需连同实际 Git 原文阅读。
独立测试及 frozen source SHA 不受此定位更正影响，父侧另逐 raw 复算。

本人实际查看本轮四张 production 图：

- `screenshots/detail-spec-production-leaf_active_bad-desktop.png`：
  坏精确 Canary 引用使 Active 两健康 gate unknown，无认证来源，资格/审批/审计历史保留。
- `screenshots/detail-spec-production-leaf_active_valid-mobile-left.png`：
  合法 Active 保留两条已消费前序来源及非本部署新观测提示；图为横滚后的局部。
- `screenshots/detail-spec-production-leaf_local_bad-mobile-left.png`：
  坏 local Canary 不认证，独立 Shadow 保留；最新 pass 窗口摘要仍作为诊断显示。
- `screenshots/detail-spec-production-current-mobile.png`：
  current v3 与 hold/不足基线、费用/结构未知及零计数分开；
  0→220 真横滚另由 raw+Trace 验证，截图本身不能代替动作证据。

没有重新运行浏览器，不将 reviewer 八张图计为本人视觉检查。
两次 schema fixture 辅助失败、historical v1 辅助失败和所有历史 RED/UI错误原样保留。
新模型0/实际费用0，全HTTP unknown；Task9 尚待独立 CODE。

父侧辅助尝试（不记产品失败）：`ad9de54b3875362712e83896dcbbb907`
exit1，错误将最终ledger包装 `{raw_sha256,raw,aggregate_exit}` 当原命令；
`09a71c0a6d9d1883a48d704a68d6aa83` exit1，误将嵌套locator
`spec-runtime-final.json:commands` 当文件名。最终按真实包装和嵌套字段核验，
不改写原ledger、缺失的aggregate exit或原命令UTC。
`bb9f3036ace5ffdf429efd8351986a08` exit1：父侧只计production网络GET
却与所有UI Trace的GET声明比较；最终分开计普通UI和production，
242仅为production口径，不伪称全部HTTP。
