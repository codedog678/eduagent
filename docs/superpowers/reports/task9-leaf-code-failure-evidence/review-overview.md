# 独立 WHOLE CODE 评审

结论：**WHOLECODEFAIL**。1 个 P1，置信度 10/10。
范围：Task8 acceptance 至 `c52aaababba238ec26282f8c560c8f565a60a09e` 的全部 Task9，17 源路径及完整原证据。

## [P1] 冻结叶子真实性校验不完整，错误认证 local 和 Active 消费链

位置：`python/core/distributed/ops_queries.py:583-596`；调用链 `:483-521,724-731`。

有界叶校验只检查格式、部分身份、排序/计数和 Decimal cost，未核验 canonical observation_key、Canary 同分布/非 production namespace、Shadow 同 parent pairing、window start/end 和 passed window 空 triggered_thresholds。真实 PostgreSQL append-only fixture 保留原合法证据，新增真实 FK Run/observation，按替换 keys 重算窗口与收据哈希。权威 helper 拒绝 7 种无效 leaf，但完整 GET 200 仍输出 passed/local。另独立 5 项 Canary Active 断言全部失败，返回 Canary/Shadow 两条 passed/consumed_chain，合法 Canary/Shadow 和 Active 双来源对照通过。原 XML/完整 GET/commands 留 fresh-leaf 与 fresh-active。原回归和新 SPEC PASS 不抵消反例。未证明写晋级绕过，P1 为明确条件性可信证据投影错误。

```python
            rows = [by_key[key] for key in keys[label]]
            if rows != sorted(rows, key=lambda row: (row.observed_at, row.observation_key)):
                return False
            for row in rows:
                if (
                    row.deployment_id != source.deployment_id or row.cohort != cohort
                    or row.policy_hash != policy or row.metric_contract_version != 1
                    or not source.created_at <= row.observed_at <= window.evaluated_at
                    or row.created_at > window.evaluated_at
                    or not isinstance(row.cost, Decimal) or not row.cost.is_finite() or row.cost < 0
                ):
                    return False
                total += row.cost
        return receipt.cost == total
```

修复建议：补齐有界纯读的 canonical 身份、namespace/distribution、parent pairing 和 window 关系谓词，可与权威 helper 共享验证组件；精确 Canary 失败后整条 Active 依赖链不可认证。保留独立合法 Shadow 历史和非 passed local 对照，新增完整 GET 回归；不调 command、不无界 replay evaluator、不借新合法 leaf 或前端删行。

全后端1864、API315、完整链111、下限28、最终UI54、真实PG七场景双视口14均通过；
新local7种有效FAIL和独立Active5项FAIL不能被常规green抵消。重复/重叠不相加。
完整命令/UTC/XML/SHA/清理/限制见同字节主报告 `review-result.md`。
未commit/push/实施修复/Task10/模型请求或授予Task9验收。
