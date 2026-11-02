# Task9 fresh 实现：完整冻结叶子的真实性与关系校验

用户已授权继续修复，设计与Task9计划无需重新确认。你是新的实现者，
不是本轮CODE/SPEC reviewer。只在M3实现并NEWcommit；不amend/push/gitconfig/
跳hooks，不改primary eduagent source/tests/index/.venv，不新模型/Agent50。
Task9尚未验收，不能启动Task10或给release/教学证明。

唯一R `/Users/bytedance/Documents/trae_projects/eduagent-m3`，
branch `feature/m3-trusted-policy-promotion`，实际clean起点
`855d5c6660343c24df0bef5ad4cf77160e83c566`，
parent `c52aaababba238ec26282f8c560c8f565a60a09e`。
产品仍d772，355sourceSHA
`7179c2f089080e4125f510c4bb241e415d53e92ba98e257f7c4a43d5830dc5fc`。
父侧5492actualGitblobs已核验，855是仅失败证据归档。
primary clean `2ff803c968d64741d149e5a1ce88a823d4d32422`，
266sourceSHA85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5。

完整读取批准design/plan Task9六步和既有WHOLE briefs：
`/tmp/m3-task9-minimum-spec-brief.md`、`/tmp/m3-task9-minimum-code-brief.md`、
`/tmp/m3-task9-complete-chain-code-brief.md`。也读brainstorming/writing-plans
相关技能，但设计/修复已授权，直接复用既定计划，不重问已有批准。
完整缺陷与原字节：
R/docs/superpowers/reports/2026-11-02-m3-task9-leaf-code-failure.md，
R/docs/superpowers/reports/task9-leaf-code-failure-evidence/。
manifest595 SHA1da8278d77d5b683e4b6c08211a0c49d610932a553971c33a24dad8d4c6ba92a，
payload3b95879869f3ce1db7afbe089d4093683643f9082d6cc20d8eb8f808e9dfda37，
reportc888b639b6e9a6bd9d60e1537fbf24a9cd8840e02738a5d42763751c8ce40b45。
原fresh-leaf9=2PASS7有效FAIL，fresh-active6=1PASS5有效FAIL；
7种local变体，5同类Canary输入的Active尾断言另执行，不是12种独立输入。
authority拒绝但Ops local/Active认证；不是已证明写晋级绕过。
原UI54=51PASS1F2E，同配置recheck54/visual4PASS，全部保留。

修复完整目标：

1. 对照authority `promotion_repository.py:651-759` 与
   Ops `_frozen_summary_matches`、`_project_health_sources`、`_consumed_canary`。
   补齐全部相关有界纯读真实性/集合关系，不能只补首个noncanonical反例：
   canonical observation_key绑定run/deployment/cohort/version；
   Canary candidate+stable同rehearsal/operation分布且非production namespace；
   Shadow两cohort同parent run pairing；
   window observation_start_key/end_key精确对应冻结candidate+stable keys；
   pass window不能带triggered_thresholds。
   检查两个cohort、两门禁及所有相关边界，保留已校验的身份、count、
   时间、阈值、窗口、成本、精确receipt、排序和有界LIMIT。
   优先复用小型纯验证组件防止authority/Ops再漂移；不要调用command或
   重放无界/带副作用evaluator。若不共享，说明限制并完整覆盖对应谓词。
2. 无效local passed source不可认证；引用无效精确Canary时Active整条
   consumed_chain必须断开，不能留下此前Shadow绿来源、借另一个合法leaf。
   Canary本地独立合法Shadow历史必须保留；合法替换Canary/Shadow和Active
   双来源必须保留。Active local合法baseline仍精确绑定已消费Canary stable keys；
   低样本failed/unknown、hold/fail窗口继续展示，不能以删历史求绿。
   不降低冻结candidate/stable minima，不改作者收据使fixture通过。
3. 初始有效RED：复制并重绑定本轮fresh-leaf/fresh-active到自有UUID E，
   新PG真实migration/FK/append-only触发器、完整HTTP GET200、authority先校验。
   新增有意义repo GET回归，两个cohort/window start+end/distribution operation/
   namespace/pairing/triggered边界及合法对照，既测local也独立测Active。
   不shutdown他人服务、不运行旧fixedOWN写golden、不disabletrigger/updateimmutable。
   单元测试文件需按bits-unit-test-gen技能处理，source/e2e新增测试写前读相应流程；
   既有批准RED/GREEN完整矩阵不能降成仅窄测试。
4. 完整最终backend/API/Ops影响矩阵、完整链/minimum/新真实性探测、
   Node20build/原全部UI54/七真实PGproduction双viewport，
   增加能展示本次坏叶与合法对照的真实production正确性证据。
   actualview_image关键截图、GET-only/consoleerror0/移动横滚、
   实际trace资产响应正文等于本次dist，不以生成截图当视觉验证。
   原F1/C1/S1-S3/S1-R/Decimal21/21/localActive/完整断链/隐私/RRREADONLY/
   authkeyset/Trace固定版本回归全部保持。
5. 只读两树保护与NEWfreeze证据：起止tracked/source/index hash+mtime/
   venv/sourceVitecache、每最终矩阵新增tests也在source全集；HEAD对应所有源
   Gitblob，原历史5492files不能覆盖。本人raw/XML/commands/UTC/退出/
   环境/角色/请求0/费用0/未知HTTP/失败与中断都有manifest。
   全raw持久repo新目录，同字节报告，sourcehash不循环包含evidence。
   stage具体paths，扫描actualsecret values与ZIP成员，HEREDOC NEWcommit，
   normalhook2秒hardcoded扫描超时不得声称完整scan通过。
6. 先完整写 `/tmp/m3-task9-leaf-authenticity-fix-result.md`，
   提供实际product/docsreviewHEAD、parent、sourcepaths/全集SHA、rawmanifest/
   reportSHA、有效RED/GREEN、全矩阵/原始证据/清理/限制。
   实施GREEN不等于验收。父侧核验NEWfreeze后fresh WHOLE SPEC，
   只有新PASS归档后fresh WHOLE CODE。

环境：
- runtime `/tmp/eduagent-m3-patched-runtime/bin/python` 3.11.17，只读58dist/
  39实际project/dev/build/requirements约束。不改主venv或runtime。
- 共享PG16.15 loopback57432 postgres trust PID16852/data-dir
  /Users/bytedance/Library/Caches/eduagent-task9-test-services/d7c17eb6-6c53-4bca-9c54-26b53147cd36/pgdata 保留。
  每invocation新UUIDDB/finallyexactdrop，自建freeport nonpersistentRedis，
  核PID/run_id/dir/save/appendonly后SHUTDOWNNOSAVE；noFLUSH/noPrefixDEL，
  subprocess未计量keys如存在只记录，不声称账本完整。
- CODE自有56737/56738/56739已关闭，13DB0，不复用固定身份。
- Node20.19.5 /Users/bytedance/.npm/_npx/39826d059b592c66/node_modules/node/bin/node；
  source modules实体copy自有E，不symlink回source，browser前读TRAE-browseruse。
- Docker absent，不安装/不虚构真实CI；无liveprovider/正式v3/holdout/学生任务。
- 父侧审查之外的临时准备（historical/docs-link preflight）不是本人验收，
  不把旧v1开发100%当当前v2/v3正式资格。
