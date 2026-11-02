# 代码评审报告

- 仓库：eduagent-m3
- 检测模式：通用检测
- 检测范围：8869166878a193a1c453376471cbe52c8fa84b3f..c52aaababba238ec26282f8c560c8f565a60a09e
- 生成时间：2026-11-02 13:57
- 检查文件：2323
- 变更行数：2337223

## 缺陷统计

- P0：0
- P1：1
- P2：0
- 合计：1

## 缺陷详情

### 1. [P1][业务语义问题] 冻结叶子真实性校验不完整，错误认证 local 和 Active 消费链

- 位置：`python/core/distributed/ops_queries.py:583-596`
- 置信度：10/10

**问题描述**

有界叶校验只检查格式、部分身份、排序/计数和 Decimal cost，未核验 canonical observation_key、Canary 同分布/非 production namespace、Shadow 同 parent pairing、window start/end 和 passed window 空 triggered_thresholds。真实 PostgreSQL append-only fixture 保留原合法证据，新增真实 FK Run/observation，按替换 keys 重算窗口与收据哈希。权威 helper 拒绝 7 种无效 leaf，但完整 GET 200 仍输出 passed/local。另独立 5 项 Canary Active 断言全部失败，返回 Canary/Shadow 两条 passed/consumed_chain，合法 Canary/Shadow 和 Active 双来源对照通过。原 XML/完整 GET/commands 留 fresh-leaf 与 fresh-active。原回归和新 SPEC PASS 不抵消反例。未证明写晋级绕过，P1 为明确条件性可信证据投影错误。

**修复建议**

补齐有界纯读的 canonical 身份、namespace/distribution、parent pairing 和 window 关系谓词，可与权威 helper 共享验证组件；精确 Canary 失败后整条 Active 依赖链不可认证。保留独立合法 Shadow 历史和非 passed local 对照，新增完整 GET 回归；不调 command、不无界 replay evaluator、不借新合法 leaf 或前端删行。

---
