# Task9 SPEC-1 最小修复实现交接

状态：已完成本轮实现和验证，待 fresh WHOLESPEC；不授予 Task9 SPEC/CODE 验收。
角色：新的 SPEC-1 修复实现者。未运行 Agent50、真实模型、Task10 或独立验收。
授权：`authorized-brief.md` 原字节保留；本轮使用已批准设计与 Task9 六步计划，不重新设计确认。

## 冻结与范围

唯一可写源码树：`/Users/bytedance/Documents/trae_projects/eduagent-m3`。
分支：`feature/m3-trusted-policy-promotion`。
本报告写入时实际 HEAD / 最终矩阵产品冻结：
`d77299c710a4d330539010d9067c5b4938f4adf1`。
产品提交 parent：
`6147cec5bff26d60a3422b0f43f133b2db782e8f`。
原 parent 的 parent：`ed42d33a187115825a8a94fb45ae8b4652cf4c11`；
此前产品：`9ef34434cc72f270085d234d89eae5f22d3d6ecd`。

产品只改两个路径：
`python/core/distributed/ops_queries.py`；
`python/tests/distributed/test_ops_minimum_evidence.py`。
NEW 产品提交保留正常 hooks/签名行为，没有 amend、push、git config 或 bypass。
后续 NEW docs-only 冻结的 parent 必须是上述 d77299c；其实际 HEAD 通过以下
命令定位，而不把一个提交的哈希写入该提交自身：

```bash
git log -1 --format='%H %P' -- docs/superpowers/reports/2026-11-02-m3-task9-minimum-fix.md
```

提交后的 literal actual HEAD、parent、逐 blob 复算、同字节核验和资源复核由
归档 `publish.py postfreeze` 写入 `/tmp/m3-task9-minimum-fix-postcommit.json`，
并在实现者最终交接中提供；该后验记录不参与被它验证的提交哈希。

源全集按 tracked 加新增 source/tests、路径前缀 python/ 与 frontend/ 计算：
最终 355 文件，SHA256
`7179c2f089080e4125f510c4bb241e415d53e92ba98e257f7c4a43d5830dc5fc`。
起点 354 文件，SHA256
`6fb437fa79b04874756c3a762aa62a2d7a8c8c39193769811eb9a779ecb93e96`。
最终矩阵快照包含新增测试；355 source 与产品冻结逐 Git blob 匹配，
3845 当前 tracked blobs、3844 起点 tracked blobs 均实际核验。
source SHA 不包含报告或证据，计算协议见 `bootstrap.py` 与 manifest。

只读 primary HEAD 保持 `2ff803c968d64741d149e5a1ce88a823d4d32422`；
266 source SHA 保持
`85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`。
两树 tracked/source、index，以及 primary/M3 主 .venv 和 source Vite cache
均以每次执行 before/after 核验；产品 stage/commit 的合法 M3 index 变化另建冻结快照。

## 事实、修复与边界

原 Ops 完整 GET 会认证自洽但不足冻结下限的 passed Canary leaf，
并沿完整 Active 链给出 Canary/Shadow 双来源；真实 authority helper 拒绝
0/0、19/20、20/19，接受 20/20。Active 攻击是 append-only fixture，
不是 PromotionCommand 写入或晋级绕过，不扩大此结论。

`_frozen_summary_matches` 现在对 passed leaf 使用所属 deployment 冻结的
`candidate_min_runs`、`stable_min_runs`，而非全局 20 字面值。
消费来源原本必须 passed，沿 exact consumed Canary 校验传播；
无效 Active 整链不从其他合法 leaf 借绿。仍然有界、纯读，
Ops REPEATABLE READ READ ONLY 没有调用 command/evaluator/qualification 写入口。
默认阈值、Tasks1-8、worker/control plane 和前端源码未修改。
合法独立 Shadow 历史、低样本 local failed/unknown/hold/fail 展示保留。

原探测末尾 local 断言把独立 Shadow 也算入，范围过宽且原失败未执行到：
复制后仅断言 `canary_health` 不可认证，并增加合法独立 Shadow 对照。
原字节、owned 字节 SHA 与差异见 `minimum-probe-provenance.json`、
`minimum-probe-owned.diff`；不将原过宽断言当作验收依据。

新增 24 项真实 PostgreSQL 完整 GET 回归覆盖：
local Canary/Shadow 和 Active 整链的 0/0、19/20、20/19、20/20；
独立 Shadow 保留；local 1/1 failed/unknown 与 hold/fail；
冻结 22/23 的 20/23、22/20 拒绝及 22/23 接受；
21/21 循环 Decimal 精确成本；合法 Active local 继承冻结基线，
不漂移到后续 Canary 新 leaf。真实 migrations/triggers/FK 保持启用，
没有 UPDATE immutable、关 trigger 或伪造 fixture FK 来求 RED。

## 本轮执行证据

| 调用 | XML 实际结果 | 角色 |
| --- | --- | --- |
| red-original-minimum | 4 = 1 PASS / 3 有效断言 FAIL | 改产品前真实 RED |
| red-production-minimum-zero | 2 = 0 PASS / 2 正确性 FAIL | 改产品前双视口 RED |
| red-new-get | 24 = 12 PASS / 12 FAIL | 11 有效产品 FAIL，1 无效 UUID fixture FAIL |
| red-new-get-corrected | 24 = 13 PASS / 11 有效 FAIL | 修正 fixture 后真实 RED，无 error |
| green-minimum | 28 PASS | 原 4 + 新 24，非独立样本总和 |
| green-integrity-complete | 111 PASS | 原 47 + 17 + repo 完整链 47 |
| green-production-minimum-zero | 2 PASS | 修复后双视口正确性 |
| full-final | 1864 PASS | 产品冻结全后端，378.71 秒 |
| api-final | 315 PASS | 产品冻结完整关系/API 矩阵，100.60 秒 |
| ui-final | 54 PASS | 原 27 场景 x 双视口，17.9 秒 |
| prod-final-* | 7 x 2 = 14 PASS | 产品冻结七场景双视口正确性 |

全部 XML 均无 error 或 skip。无效尝试不能计为产品 RED 或独立有效样本；
`invalid-attempt-minimum-test.py`、原 log/XML/GET bodies 原样保留。
新 UUID observation 修正后才执行 corrected RED。
其他 invalid evidence-audit 尝试两次也完整记录，均是汇总脚本错误，
不是产品失败；最后 fresh audit-final 实际完成。

原 F1 九项、C1 同 artifact 两部署、S1-S3/S1-R，以及 exact command、
count/fee/keys、latest malformed、bad reference、unknown/failed、Decimal
对照在上述 111/315/1864 重叠矩阵中保持；没有把重叠调用加成独立样本量。

production 七场景：
`current`、`history`、`approval_malformed_latest`、
`genuine_malformed_latest_valid`、`genuine_valid`、
`referenced_canary_poison`、`minimum_zero`。
18 个本轮 production 视口 raw（含 RED/GREEN 重复）记录 108 个 page GET；
最终 14 个记录属于七场景正确性，不以常规 green 替代新正确性判断。
每次实际 HTTP CSS/JS bytes 与 dist 一致，哈希/trace/截图保留；
页面请求均 GET，无 console/page error，页面 overflow <= 1。
另实际 view_image 查看 14 张 production 左侧关键截图和
Policies/immutable policy Trace 双视口 4 张，共 18 张，索引见 execution-audit。
移动端宽表保持局部横向滚动，不宣称一屏同时展示所有列。
API auth/privacy/keyset、Run/Trace immutable identity、legacy NULL、
abort/reset/delayed response 等由最终全 API/UI 矩阵验证。
production 是 loopback 真实 PG fixture、本地空 Ops token 模式，
不是公网部署或生产认证配置验收。

## 命令、运行时与成本

自有目录：
`/tmp/m3-task9-minimum-fix-157727b8-1740-4144-b066-f9a239fe4ecb`。
各 exact command/cwd/UTC/start/end/exit/DB/drop/env 和 test log/XML
在 `*-command.json`、`*-lifecycle.json`、`execution-ledger.json`；
协议、阈值、逐条 GET body、role/source SHA 也随 raw 保留。

```text
PYTHONDONTWRITEBYTECODE=1 TASK9_MATRIX_SNAPSHOT=final-snapshot.json
/tmp/eduagent-m3-patched-runtime/bin/python OWN/review.py pytest full-final -c pyproject.toml tests -q
/tmp/eduagent-m3-patched-runtime/bin/python OWN/review.py pytest api-final ... -q
/tmp/eduagent-m3-patched-runtime/bin/python OWN/frontend_run.py ui ui-final e2e/ops.spec.ts
/tmp/eduagent-m3-patched-runtime/bin/python OWN/frontend_run.py build build-final
/tmp/eduagent-m3-patched-runtime/bin/python OWN/production_batch.py
/tmp/eduagent-m3-patched-runtime/bin/python OWN/finish_audit.py dependencies
/tmp/eduagent-m3-patched-runtime/bin/python OWN/finish_audit.py audit audit-final
/tmp/eduagent-m3-patched-runtime/bin/python OWN/finish_audit.py cleanup
```

`api-final-command.json` 包含完整参数，不以此处省略号作为可复现命令。
Python 3.11.17，patched runtime 未改或安装；
独立解析 58 installed distributions、39 项声明约束匹配，pip check exit 0。
Node 20.19.5、Vite 7.3.7；Node modules 使用自有实体 copy，
全部内部 symlink 已核验，无源模块链接；Node20 两次 build exit 0。
pytest deprecation/collection 与 Vite chunk >500 kB warning 原 log 保留。
没有运行新的漏洞扫描，不把父侧 Task10 dependency preflight 冒充本轮安全审计。
模型请求 0、模型费用 USD 0；没有真实模型或 eval 发布资格声明。
未全局计量 pytest/API/HTTP 请求，总数 unknown，不补零。
历史中断、丢失 tmp 的 counts/time/cost unknown 原档保持，父侧 replay 不冒充本轮 RED/GREEN。
Docker/真实 CI 未运行，不认定 CI/release green。

## 资源与清理

本轮 16 个独立 UUID PG invocation DB 均 finally drop exit 0，
并用 exact datname 查询确认无残留；另查旧档 14 个 DB，余 0。
共享 PG 16.15 / 127.0.0.1:57432 / postgres / PID16852，
data dir 与原 identity 一致，保留；没有停共享 PG 或删他人数据库。

自建 nonpersistent Redis 61803 / PID49811 /
run_id `07225b691813d6952dc1771ccdd2c295b5a0280a`；
shutdown 前实际核对 PID/run_id/dir/save/appendonly identity。
428 次 exact UUID DEL/UNLINK 留账，没有 prefix DEL、FLUSHDB/FLUSHALL。
worker subprocess ledger 不完整：shutdown 前 12 个余 key 均未计量，
不能宣称 key 账本完整；仅对确认属于自己的 nonpersistent 实例
执行 SHUTDOWN NOSAVE，不用宽删清理这些 key。
61803/61804/61805 已关闭，无自有 browser/Vite/live_server 残留。
自有 modules/dist/cache/tmp/vite-cache/npm-cache 已删，
构建和 HTTP 资产原字节保存在 `retained-http-dist`。
patched runtime 与共享 PG 保留供后续审查，primary/source/index/.venv/cache 未改。

## 持久归档与可复算

先完整写入 `/tmp/m3-task9-minimum-fix-result.md`，再同字节复制为
`docs/superpowers/reports/2026-11-02-m3-task9-minimum-fix.md` 和
`docs/superpowers/reports/task9-minimum-fix-evidence/report.md`。
该新 evidence 目录保存本轮 570 个 raw payload 文件，
另保存 payload manifest 和同字节报告；不删除或覆盖旧失败/无效证据。
570-file payload SHA256：
`a0f174383667b0ccdc56c174e28d5e0f8acf0c4b07006abcc872c46449ae6d9b`。
`payload-manifest.json` SHA256：
`daeaf5ae1953363ec9027082b3e0bd70bb2d712d16f14499049f4b7ad4103d19`。
manifest 排除自身/报告/未来 staged-secret 和 postcommit 记录以避免哈希循环，
其余全文件逐字节匹配；自身和报告由 NEW commit Git blob 单独核验。

最终 raw 17 XML、23 组完整 protected before/after、
72 ZIP CRC / 2378 members 均实际复算；
trace/network 14615 events 已逐行 JSON 解析。
原 Task9 档 2627 文件也逐历史 Git blob/JSON/XML/ZIP 解析核验，
最新 SPEC FAIL 的 466 raw 与原 manifest/report 保持原字节，不替代本轮执行。
具体 source、原失败、无效尝试、manifest、counts 与单项路径
见 `execution-audit.json`、`final-payload-audit.json`、`payload-manifest.json`。

提交前具体 staged paths 扫描，raw/ZIP 成员均扫描实际本地两项 distinct
secret 值与高置信 key pattern，匹配 0；不回显 secret。
扫描记录 `product-staged-secret-check.json` 和新
`docs-staged-secret-check.json` 保留，postfreeze 再扫描整个新 docs 变更。
NEW docs 提交必须只包含本报告与本轮 evidence 路径，不 amend/push/config/bypass。

后续：父侧 fresh WHOLESPEC；PASS 后 fresh WHOLECODE。
本轮实现和测试 green 不是 Task9 最终验收，也不启动 Task10。
