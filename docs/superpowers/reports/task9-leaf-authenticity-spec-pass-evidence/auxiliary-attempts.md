# 本人辅助尝试与保留限制

本页不记作产品缺陷或模型调用。测试业务矩阵目前无有效 FAIL。

- `a529a6664923e697faabdf4e48223514` exit1，UTC 06:58:30.684113→06:58:48.050947。
  historical 审计初版将全部旧 manifest 当成最终相对目录清单，遇到旧
  `task9-leaf-authenticity-fix-staging-evidence/manifest-v1.json` 中
  `finalize-docs.py` 摘要与当前修正版不等而中止。原脚本 `audit_spec_v1.py`
  与 `audit-historical-command.json` 保留。有效业务测试没有启动。
  原错误：`AssertionError: /Users/bytedance/Documents/trae_projects/eduagent-m3/docs/superpowers/reports/task9-leaf-authenticity-fix-staging-evidence/finalize-docs.py`。
  v2 逐项列出实际不等及保留路径，旧摘要与 `finalize-docs-v1.py` 原字节相等；
  最终 manifest 9/9 相等。不是扩白名单或丢掉原失败。
- `20efc01d1b2b077bdcefd365cccccb39` exit2：rg 的 `-g` 放在 `--` 之后，
  因而按文件名解释。无结果不能当 scan PASS。
- `e3628c762fcb56f730c5bbf41bb455db` exit2：猜测不存在的 runtime_check.py /
  secret_checks.py。实际实现记录在 final_evidence.py，已完整读取。
- `8d3976cd15df6fbc1cf3a6cf2e5327ca` exit1：rg 无匹配不代表安全扫描已完成，
  也不代替最后 actual secret values 与 ZIP 解压字节扫描。
- `13a86f3aa3567f369a82e729fb49fb25` exit2：旧报告日期路径不存在；
  evidence/freeze.py 与 actual Git 历史另读，不把不存在的路径当事实。
- 前文 primary/project memory 路径读取失败与过长文件清单输出截断属于辅助读取限制。
  精确 shell UTC 未逐次计量的阅读命令标 unknown，不事后编造。

原 historical source-manifest 是仓库相对 `files_sha256`，不是 archive 相对 payload；
初版的“missing321”只描述错误根目录解释，不能算原材料丢失。需独立核对历史实际
product `2d823cfb82f0b49b0f046bb0bb89f0a43b6b6c1d` 全 352 Git blobs。

- `5c58b9bf90680871e13e0423dcdc1a29` exit1：spec-boundary 8 个脱敏 GET503
  通过；schema fixture 的 `pg_constraint.contype` 是 bytes `b'f'`，初版与
  字符串 `"f"` 比较无效。XML、命令/DB/drop/快照和 boundary_supplement_v1.py 保留。
- `70e4733db86b936f32c885d3a391c6e5` exit1：v2 修正 SQL cast 后 FK 断言通过，
  但以 `"UPDATE OR DELETE"` 字符串搜索实际 `"DELETE OR UPDATE"` 定义错误。
  原 XML、脚本 v2 与实际 triggers JSON保留；六个 trigger 实际均启用 O、FOR EACH ROW。
- `6209eb25b556cc22ec4c7aa0a8c042c8` exit0：v3 使用实际 tgtype bitmask，
  合法真实链先创建可测试行，对六表的既有行 DELETE 在 savepoint 内全部被
  append-only 拒绝并回滚，9/9 通过。没有 disable trigger/DELETE WHERE false 求假通过。

用户要求保留的历史无 -c pytest、错误 production 场景名、Decimal 启动失败、
父 parser 误假设、UI 原失败/重跑、已中断/丢失 tmp unknown 均在冻结原档，
本人没有重写其结果或将其升级为有效 RED。

- 报告整理阶段 `5943b9fa440e8a8f14845fb9a64b647e` exit2：行号搜索误用
  `python/agent_harness/...` 路径；随后用 `rg --files` 定位实际
  `python/core/distributed/...`、`python/api/ops_routes.py` 并读取。
  这是辅助只读搜索失败，不是测试执行或产品 FAIL；该阅读命令精确 UTC unknown。
