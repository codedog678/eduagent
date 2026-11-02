# 本人实际图像检查

本记录在 8 次 `view_image` 返回图像后撰写，不将图片 hash 当成视觉检查。

| 自有路径 | 角色 | 本人观察 |
| --- | --- | --- |
| screenshots/detail-spec-production-leaf_active_bad-desktop.png | real PG + 本轮 production dist | 两健康 gate unknown，无认证来源；审批/资格历史和 canary→active 审计保留。 |
| screenshots/detail-spec-production-leaf_active_valid-mobile-left.png | real PG + 本轮 production dist | 合法 Active 两通过来源，分别前序 Canary/Shadow，均标“非本部署新观测”。横滚后的局部区域，列不保证同屏。 |
| screenshots/detail-spec-production-leaf_local_bad-mobile-left.png | real PG + 本轮 production dist | 坏 local Canary 没有认证行；独立 Shadow 保留。最新 pass 窗口仍作为诊断事实显示，不等于认证来源。 |
| visual/policy-trace-mobile.png | frontend fixture，仅 UI | 固定 deployment、candidate/rehearsal 和 hash、run.attempt/expert.wait 可读，无生产 PG Trace 角色升级。 |
| screenshots/detail-spec-production-current-mobile.png | real PG + 本轮 production dist | current v3、hold/基线不足、未知指标与零计数分开；横滚后 Candidate/Stable 可见。 |
| screenshots/detail-spec-production-history-desktop-left.png | real PG + 本轮 production dist | 历史 v2、本地 pass receipt 与当前 v3 分开。region 捕获中 sticky header 遮挡一部分，不宣称像素完美。 |
| screenshots/detail-spec-production-minimum_zero-mobile-left.png | real PG + 本轮 production dist | 0/0 精确 Canary 使 Active 两门禁 unknown；资格/审批/审计保留，未声称已发布。 |
| visual/policies-desktop.png | frontend fixture，仅 UI | filter/tab/list/detail/冻结阈值、failed gate、未知指标、rollback/frozen 时间线、只读控制清晰。 |

12 个本人 production mobile 场景均有实际 wheel 与 `scrollAfter.left > scrollBefore.left`；
current 真实范围为 0→220、容器 340/560。不能仅用图像或结构宽度替代动作证据。
