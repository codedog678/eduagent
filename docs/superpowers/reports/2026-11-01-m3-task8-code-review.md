# M3 Task8 独立代码审查

日期：2026-11-01。结论：**CODE FAIL**，Task9 尚不启动。
审查提交为 `a4691bf59f684dd4e6c068e60c98989de19f8281`，
覆盖原 Task8 实现与四项规格修复。之后 `ad858a2`、`6e55434` 仅追加文档与
离线结果，运行 Python 代码未变。规格复审已经通过，但本次代码审查另外复现
一个权限观测发布与晋级事务之间的 P1。

## 已确认并发缺口

[门禁验证](../../../python/core/distributed/promotion_repository.py#L852-L896)
只查询一次 lifetime hard event；
[观测补录](../../../python/core/distributed/policy_health.py#L193-L239)
没有共享晋级事务的同步边界。真实 PostgreSQL 独立探测使用真实
registration→Shadow→Canary→Active 命令链，并安排如下交错：

1. 晋级事务完成硬违规查询。
2. 另一个事务从真实 candidate 终态记录服务端 `ConfirmedPermissionViolation` 观测。
3. 该观测在 Active 创建之前提交，但晋级仍成功。
4. 随后的 Active 评估返回 pass，head 仍为 active。

因此合法 passing window 与门禁查询不能单独证明晋级提交时仍没有硬违规。
修复应让观测发布与门禁消费/head 变更共享锁边界，并补真实交错回归。
只有再次查询而没有同步，仍可出现同一漏洞。
相关源码行号对应冻结版本，修复后以审查提交为准。

## 独立验证范围

审查者独立定向矩阵 457 项通过，94.51 秒，无失败、错误或跳过；
另外的真实 PostgreSQL 探测复现上述 P1。未确认其它实质性代码问题。
完整后端未重复运行，fixture 不授予发布资格，外部模型调用为零。
审查未编辑、暂存、提交或安装；临时数据库已清理，两工作树干净。

修复后的验收需要：失败交错回归、同步实现、修复后绿测试及冻结版本，
再按顺序重新进行独立规格与代码审查。旧失败记录保留，不以既有 1400 项绿灯抵消。
