# Task9 健康来源修复后的全任务规格复审失败

本轮独立全 Task9 SPEC 为 **FAIL**，尚未启动 CODE 或 Task10。
范围从 Task8 验收版本 `8869166` 到产品冻结
`2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d`，含初实现、F1 和 C1。
常规后端 1726、UI 54、build 全部通过；新增有效规格探测与真实生产页面
正确性断言失败，不能依据常规绿灯认领 Task9 验收。

| 发现 | 实际行为 | 修复所需事实 |
| --- | --- | --- |
| S1 / P2 | audit/approval 同时声明相同错误 command hash，或缺 required_receipts、actor/issuer/model/role 不匹配，仍显示 passed consumed chain | 核对实际规范命令身份与完整审批、审计、部署关系；保留合法链正向对照 |
| S2 / P2 | 新 malformed approval 在查询阶段被过滤，旧 passed 被恢复；真实命令链桌面、移动页面均复现 | 先选最新再校验，无法确认最新绑定时保守遮蔽，不能跳过它获得旧绿色消费证明 |
| S3 / P2 | 新健康收据 sample_count 或 cost 为 0，而冻结窗口为 20 样本、费用 0.4，仍获得 local pass 归属 | 验证冻结计数和 Decimal 费用的一致性，失败不回退旧 pass |

没有证明发布写权限被绕过、真实学生影响或生产规模安全；Ops 仍是证据显示面。
修复不得通过缩减来源校验、删除断链测试、伪造费用或将显示逻辑改成发布授权来求绿。

完整[独立报告](task9-health-binding-spec-failure-evidence/review-result.md)、
[原始文件摘要](task9-health-binding-spec-failure-evidence/retained-manifest.json)、
[机器验证](task9-health-binding-spec-failure-evidence/independent-verification.json)和
[父侧保留核验](task9-health-binding-spec-failure-evidence/parent-retention.json)
均已保存。原 202 payload + 原 manifest + 完整报告逐字节保留，另有父侧核验。
无效 fixture/async/序列化/启动尝试与有效重跑均保留，不混为产品失败。

父侧独立复算 202 原文件 SHA、13 份 XML、15 份相同完整 before/after 快照、
352 源与 Git blob 身份。源摘要为
`78fb2d84827b0e9c32df1bebbee9d4840f5eff301100da0a9f5489a0146b4357`，
原 payload 摘要为
`03c093f997344b8000e077d54bf76ca90df7af4841fed8085ab1cec7f02d5d4a`，
原 manifest SHA 为
`ca86a8c220fbcf30a4f8cdec10d9c5fcf674cd69a453fbef8779ca51be3a99d2`。
本次独立全量运行已补足实现者 fullv2 未 hash 新增未跟踪回归文件的边界。

有效 relations-valid 为 11 项、2 PASS/9 assertion FAIL；最终 corroboration 为
3 assertion FAIL；两组 malformed production 各双视口 2 assertion FAIL。
这些执行有重复场景，不相加为独立样本。full/API138/UI54 的重叠同样保留。
父侧实际查看真命令与合成对照两组桌面、移动端来源截图。

父侧重新查询 exact13 UUID DB、248 UUID Redis stream，均无残留，
33630/33631 端口关闭。主工作树未变，本轮模型请求及费用均为 0。
下一步为新实现者修复 S1–S3、NEW commit 冻结、fresh 全任务 SPEC；
仅其 PASS 后才能启动 fresh 全任务 CODE。
