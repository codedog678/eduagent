# 代码评审报告

- 仓库：eduagent-m3
- 检测模式：Independent WHOLE CODE; FAIL/P1
- 检测范围：8869166878a193a1c453376471cbe52c8fa84b3f..a3e2c0b0f510235cec8a98784afdb26b3bb6db79
- 生成时间：2026-11-02 07:47
- 检查文件：21
- 变更行数：3908

## 缺陷统计

- P0：0
- P1：1
- P2：0
- 合计：1

## 缺陷详情

### 1. [P1][业务语义问题] 冻结叶指标未按实际观测认证，错误的 passed 传播到 Active 完整消费链

- 位置：`python/core/distributed/ops_queries.py:594-604`
- 置信度：10/10

**问题代码**

```python
# ops_queries.py:603-604; preceding checks cover identity/time/cost, not full metrics.
        total += row.cost
return receipt.cost == total
```

**问题描述**

_frozen_summary_matches 在实际 key/canonical 身份、run_count 和 Decimal cost 一致后即返回 True，没有验证其他冻结指标与精确观测一致、观测 schema 或实际阈值结果。details 与 window 的互相比对只能证实两个声明相同。真实 migration/FK/append-only 下，新增含 commit_failed、terminal_failed、confirmed_permission_violation、unknown_counter、invalid_counter 或 stats_claim 的同一叶，发布权威先判拒绝，完整 GET 仍返回 200，Ops 展示 local passed；Active 的精确消费链进一步保留 Canary 和 Shadow passed。独立互补矩阵 42 条为 6P/36F/0E/0S，生产构建三个坏叶双视口 6F。这是 Task9 的核心证据展示语义缺陷，不代表发布写绕过；原观测/收据保留，未禁用 trigger 或修改 immutable 行。

**修复建议**

以冻结有界 key 集合完成纯只读的观测 schema、完整指标摘要和阈值真实性认证，并让 local 与 consumed_chain 使用同一认证条件；精确 Canary 无效时移除 Active 整条健康消费链。保持冻结 minima、精确 Decimal 费用、合法非通过 local、独立 Shadow/history 和合法 Active 两来源。不得从 GET 调用 promotion command 或无界、带副作用 evaluator；补充上述同叶差分回归。

---

## 独立证据

结论 FAIL。backend1911P、API362P、integrity131P、leaf/minimum90P、UI54P、build exit0；本人互补矩阵6P36F，真实PG生产构建双视口28P6F。常规通过不能抵消有效FAIL，亦不证明发布写绕过。

23 exact UUID DB均删除、自有Redis核身份后NOSAVE关闭，两仓库source/index/mtime/venv/cache/runtime保持不变。本人actual secret两值扫描0命中；原失败、XML/ZIP/响应正文/截图完整保留。

详情：[code-review-detail.md](file:///tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814/code-review-detail.md) · [独立结果](file:///tmp/m3-task9-leaf-authenticity-code-result.md)。

未实现、提交、推送、外发评论、归档、自授Task9验收或启动Task10；0新模型，Agent50 paused，缺CI/Docker/正式v3独立链/学生效果。
