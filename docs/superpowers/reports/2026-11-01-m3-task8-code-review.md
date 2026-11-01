# M3 Task8 独立代码审查

日期：2026-11-01。当前验收仍为 **CODE FAIL**，Task9 尚不启动。
P1 修复已冻结于 `4c9b204d9ebdf3655f2ec59707ee837c77137677`；
新的独立规格复审已通过，但新的独立代码审查再次 **FAIL**，
复现执行异常退出时跳过存储权限检查的另一个 P1。修复与重新验收正在进行。
下文保留原失败结论，修复测试通过不替代独立验收。

## 再次代码审查：异常退出权限缺口

审查冻结 Python 为 `4c9b204`，`774f69a` 只追加文档。
[LearningTaskExecutor.execute](../../../python/core/distributed/executor.py#L126-L145)
仅在 `converse()` 成功返回后检查实际打开的 SQLite 存储。
若执行抛错，连接在未重新检查权限边界时关闭。

真实 PostgreSQL、Redis Worker 和 SQLite 独立探测复现：

1. 合法固定的 candidate 或 Shadow 执行由服务端附加一个范围外 SQLite 数据库，
   写入并提交标记，然后抛出 `ValueError`。
2. Primary 保存 `terminal_failed / ValueError / not_applicable`；
   Shadow 保存 `terminal_failed / execution_failed / isolated`。
3. 晋级仍成功；primary 后继 Active 的健康检查返回 **PASS**。

相同范围外写入在正常返回时会产生 `ConfirmedPermissionViolation` 并拒绝晋级；
合法存储内的普通失败仍是普通失败。这组对照定位异常退出缺口，
没有伪造权限诊断，也不是 OS 沙箱或已演示的客户端攻击结论。

修复要求：关闭连接前覆盖异常退出的真实存储能力检查，Worker 保存已确认硬违规，
补 primary candidate 与 Shadow 两条失败路径及正常返回/合法存储对照。
原发布锁与因果链修复继续保留；修复后重新顺序进行独立 SPEC、CODE 审查。

独立完整后端 1412 项通过，273.95 秒，无失败、错误或跳过，
保留一个已有收集 warning。初次探测 2 通过/2 失败，2.45 秒；
扩展重复探测 6 通过/2 失败，4.14 秒，无错误或跳过。
测试前配置路径错误未计入验证结果。冻结 XML 和源码摘要核验匹配。
未发现其它已确认 Task8 缺口；审查未修改文件，临时文件与数据库已清理，
两工作树干净。外部模型请求为零。

## P1 修复冻结与待审状态

修复父提交为 `07293a2`。观测发布取得与晋级相同的环境 head 行锁，
Canary/Active 通过已消费的不可变晋级链继承前序硬违规；
重新注册相同制品的其它历史链不能移动当前 head。
实现及边界见[修复报告](2026-11-01-m3-task8-health.md)。

父侧已解析并核验冻结 JUnit 与 SHA-256：聚焦 222、定向 469、
完整后端 1412 项，均无失败、错误或跳过；完整 XML 时间 270.868 秒。
修复前回归为 5 项失败、2 项通过。四个修复 Python 文件组合摘要为
`9785e3347d5bbb50aed170e8946831c7f263b892731bd2b1b71748056a57e4f3`。
新的[独立规格复审](2026-11-01-m3-task8-spec-review.md)已通过：
独立 469 项矩阵与 19 个新增探测均通过。新的 CODE 审查发现上述异常退出缺口，
因此 Task8 仍不授予验收。

## 原独立代码审查

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
