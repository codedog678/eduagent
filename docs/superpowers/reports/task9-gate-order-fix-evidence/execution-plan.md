# Task9 Gate 排序修复执行计划

本轮沿用已批准 design、Task9 六步与修复 brief，不新增设计门禁。
唯一写源码 worktree 为 eduagent-m3，父提交 38f48d7；Task10 不启动。

- [x] 阅读权威 FAIL 全文、原实现交接与独立 probe/live harness，确认 clean 起点。
- [x] 原样归档独立 FAIL、raw XML/log、probe/runner/live harness、截图和 failed traces。
- [x] 添加真实 PG 同 issued_at 的 failed/unknown 回归，对照发布 authority；未修复源有效 RED。
- [x] 只补 Ops 的 created_at 排序键；回归 GREEN。
- [x] 全 Task9/Ops API、完整 backend、独立 probe GREEN。
- [x] tmp 实体 node_modules，Node20 production build、40 desktop/mobile。
- [x] 真实 PG production 页面 failed/unknown 的 desktop/mobile F1 复验与视觉检查。
- [x] 每关键 run 的 source before/after、原证据 bytes、retention manifest 与 raw 计数核对。
- [x] 专用 DB/ports/caches 清理；Redis 原 finalizer 清理与只读 audit，不删归属不明历史键。
- [x] 新报告、提交边界与具体 owned path 清单准备，提交前 manifest 将重新计算。
- [ ] 正常 NEW commit、提交后核验、写盘完整 /tmp 交接，再通知父侧。

本文件冻结于提交前，因此最后一项不在 commit 内追改。提交后实际终态见
`/tmp/m3-task9-gate-order-fix-result.md`；不 amend，也不把步骤完成当 Task9 acceptance。

产品改动仅 `python/core/distributed/ops_queries.py` 的三键排序。
回归仅扩展 `python/tests/distributed/test_promotion_ops_api.py`。
本轮证据与报告使用新目录，不改原 Task9 report/evidence。
