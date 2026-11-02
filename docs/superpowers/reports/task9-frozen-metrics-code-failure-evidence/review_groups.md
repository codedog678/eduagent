# WHOLE CODE 分组

范围：Task8 acceptance 8869166 至 a3e2c0b。源文件 21；归档 raw 不作为源行数。
当前无 task 委派工具，按 skill fallback 由本人逐组执行，再跨组核对。

## Group 1: 叶子与完整消费链
共享 health_evidence_identity.py、policy_health.py、promotion_repository.py、
ops_queries.py、ops_contracts.py、test_ops_leaf_authenticity.py、
test_ops_complete_chain.py、test_ops_health_binding.py、
test_ops_minimum_evidence.py、test_ops_source_integrity.py。
重点：实际 canonical row、集合与分布、指标摘要、冻结下限、审批、精确消费和断链。

## Group 2: API 与固定 Trace
共享 ops_queries.py、ops_contracts.py；ops_routes.py、test_ops_api.py、
test_promotion_ops_api.py；api.ts、types.ts。
重点：鉴权、closed DTO、RR READ ONLY、有界分页、错误脱敏、持久 Run 身份。

## Group 3: 前端行为
OpsApp.tsx、PoliciesView.tsx、RunsView.tsx、TraceView.tsx、api.ts、types.ts、
ops.css、e2e/ops.spec.ts；共享 ops_contracts.py。
重点：认证变化、stale/abort/dispose、来源语义、移动真横滚和资产正文。

## Group 4: 证据与边界
全部 Task9 docs/raw、指定 briefs、design、Task9 plan；共享 21 源文件身份。
重点：所有失败保留、完整 XML 与 ZIP、actual blobs、首末保护、秘密与资源。

状态：四组本人依序完成；跨组复核已完成。Group 1 的同根因汇总为一项 P1；Group 2/3/4 不另报产品缺陷。结论 FAIL，未授予 Task9 验收或 Task10。
