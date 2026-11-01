# Task9 独立代码审查未通过

状态：全 Task9 CODE FAIL，C1/P2 阻断验收。Task10 未启动。
此前全任务 SPEC PASS 和 1684 项常规回归通过均不能关闭本问题。

审查 HEAD 为 `365a11542843ebcc7ecfce13e91a76e44c43d816`，
产品冻结为 `e29bdb4d0c1b0e07b0e60a62ee61df3ae2e9915e`；
完整审查 base 为 `8869166878a193a1c453376471cbe52c8fa84b3f`。
351 个 tracked Python/frontend 文件的权威摘要为
`8561cf7f84c2ed1f30e548ccb5adba0ed891cca2b9efef3d9c0ad40bb91ea582`。

`get_policy_deployment` 按 artifact 的 policy/protocol/runtime/source
选择 gate，却未限定健康回执的 deployment/version/threshold/window。
真实 PostgreSQL 复现表明：相同 artifact 的 A 已通过，B 没有样本且
窗口为 hold，B 的详情仍展示 A 的绿色 canary_health passed；A、B 都
通过后，历史 A 的详情又被较新的 B 回执替换。production 桌面与移动
viewport 均确认错误展示。此前三键排序问题 F1 已修复，C1 为新问题。

本轮独立有效执行共 1753 次，1749 passed、4 failures、0 errors、
0 skip；不是独立 case 数或 HTTP 请求数。完整后端 1684、mocked UI
40、额外探测 4 均通过；正确性攻击 21 中失败 2，production browser
4 中失败 2，四项失败均指向 C1。Node20 实际 production build 通过。
Redis guard、immutable fixture、冷启动和 selector 的无效尝试亦完整
保留，未混入产品缺陷计数。

父侧重新解析全部 10 个原始 XML，核验 148 个原始文件及 manifest，
逐字节保留全文报告；source Git blob 与首尾 snapshot 均一致。
原 148 文件 combined SHA 为
`14cc0b77076f7608968762b7ea28769516f0103dae455c3293ea16fbacc6d016`，
原 manifest SHA 为
`8713e23393c6c5e0650c31204cc2053757da2c97484374a3d42f85d94fe4541f`。

- [完整独立 CODE FAIL 报告](task9-code-failure-evidence/review-result.md)
- [全部原始 CODE 证据](task9-code-failure-evidence/manifest.json)
- [父侧字节与来源核验](task9-code-failure-evidence/parent-retention.json)
- [此前完整 SPEC PASS](2026-11-02-m3-task9-spec-recovery.md)
- [父侧隔离依赖兼容性基线](task9-patched-runtime-baseline/manifest.json)

额外的父侧安全依赖环境完整 1684 项通过，仅证明当前冻结源的兼容性，
不是 reviewer 自身执行，不关闭 C1，也不替代 Task10 最终源、构建及
两个安装入口验证。其原始 XML/log/snapshot/context/runner 单独留档。
runner 是运行记录，固定输出路径不可覆盖重跑。

自有数据库、Redis、服务及缓存已清理，原失败材料继续保留。
这些 synthetic fixture 不授予模型发布资格或教学效果结论。
下一步交给新实现者修复健康回执来源关联；新冻结后先全任务 SPEC，
通过后再全任务 CODE，新的 CODE PASS 后才验收 Task9。
