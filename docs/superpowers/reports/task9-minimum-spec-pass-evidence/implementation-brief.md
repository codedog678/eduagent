# Task9 SPEC-1：冻结样本下限可信校验修复

你是本轮新的实现者，直接完成已授权修复与新冻结，不再询问设计/许可。
用户批准 fresh实现者→NEWfreeze→freshWHOLESPEC→PASS后freshWHOLECODE，
不push/amend/gitconfig/跳hooks或签名；primary main/source/index/.venv只读。
brainstorming/writing-plans已批准方案继续，不重开产品需求。
你不自行启动审查/Task10/Agent50/真实模型，不授予Task9验收。

## 实际起点和权威

唯一可写源码树 `/Users/bytedance/Documents/trae_projects/eduagent-m3`，
branch `feature/m3-trusted-policy-promotion`，clean HEAD
`6147cec5bff26d60a3422b0f43f133b2db782e8f`，parent
`ed42d33a187115825a8a94fb45ae8b4652cf4c11`。6147仅NEW docs失败归档470路径；
产品仍 `9ef34434cc72f270085d234d89eae5f22d3d6ecd`/354sourceSHA
`6fb437fa79b04874756c3a762aa62a2d7a8c8c39193769811eb9a779ecb93e96`。
primary `eduagent` HEAD `2ff803c968d64741d149e5a1ce88a823d4d32422` clean，
266sourceSHA `85a9d519241498368c76f4724c38e7f63b265143c77645230957e7c1279e43d5`。
Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f`。

完整读批准design全文与planTask9六步、最新独立WHOLESPECFAIL报告
`docs/superpowers/reports/2026-11-02-m3-task9-minimum-spec-failure.md`，
466原raw+manifest+parent-retain+parent-retention目录
`docs/superpowers/reports/task9-minimum-spec-failure-evidence/`。
原manifestSHA `04952f15c0258d545dca305c6b14ca4a68fcaefd32257a3ace8389e95f7e2344`，
466payloadSHA `69900312b69b41ebd5694890112f0eef180cf634d3d81c6eca5a7dd0036e41a6`，
报告SHA `1477affb6fb21ec9be96354c1d44178bca21cca5cb3f714fa8314040a97fd6f8`。
父侧复算16XML/17paired全部完整受保护快照+2final/122ZIPCRC+4055member/
3844currentGitblobs，14UUIDDB实际无残留，58479/38730/38731已关闭，
2distinct真实secret值在raw/ZIP匹配0；parent-postcommit
`/tmp/m3-task9-minimum-parent-postcommit.json`。父侧实际查看minimum desktop/
mobile左侧图，确认冻结下限20/20却Canary0pass并Active双来源。
这些provenance不能替代你实际RED/GREEN，不冒充父侧或SPEC执行为本人。

## 唯一当前缺陷与必要修复

SPEC-1：`ops_queries._frozen_summary_matches`只要求keys个数>=0且<=max/
run_count/sample_count/Decimalcost相等，不对可信passed/consumed来源应用
**所属deployment冻结**的candidate_min_runs/stable_min_runs。
0/0、19/20、20/19均canonical自洽却被Ops认证；权威
`promotion_repository._validated_health_window:651-752`实际拒绝。
这不证明写权限或晋级绕过：攻击Active由append-onlyfixture构造，不是
真实PromotionCommand成功。不要升级或篡改这个事实。

最小有界纯读修复：
- 对passed或消费来源的leaf证明应用冻结最小cohort限制，取所属deployment
  PolicyThresholds而非全局20字面。默认20/20不得降低。Canary无效通过现有
  exact `_consumed_canary`验证传播，完整Active链不可用，不换合法leaf恢复。
- 保留Canary独立合法Shadow历史：本地Canary无效只针对该gate，不全局删
  Shadow。原probe最后local断言把独立Shadow也算进，范围过宽，未执行到、
  **不能作为验收依据**；复制后修正自身探测到gate-specific并保存差异。
- 保留本地hold/failed/unknown低样本的合法非通过展示、合法Active local
  基线继承、合法20/20和21/21循环Decimal；不无条件对所有窗口下限判无效。
- 优先复用现有leaf纯校验，中文注释；Ops REPEATABLE READ READ ONLY，
  不调用command/evaluator/qualification写入口、不无界重放、不靠前端过滤。
- 不改已验收Tasks1-8、threshold默认或worker控制面，不能抹掉历史健康。

## 回归、执行、冻结

1. 新UUIDtmp/start snapshot（两树全tracked、新增source/tests、index、
   主venv、sourceVitecache）与旧档byteexact。所有outputs只自有新目录。
   不直接运行旧固定OWNrunner，复制probe/server/runner到自己目录改ROOT/
   HEAD/labels/ports/cache/record路径，新fixtureDB每invocationUUID。
2. 产品改前真实有效RED：原minimum4=1PASS/3有效ActiveassertFAIL，
   productionminimum双viewport=0PASS/2有效correctnessFAIL。修正原local
   最后过宽断言为只看canary_health（且独立Shadowpositive），明示probe
   差异；新本地gate负例亦实际RED，不借无效fixture/setup求失败。
   authority拒绝负例/接受20positive由真实helper证明，canonical命令8字段、
   real migrations/triggers/append-only/真实obsordered subset/精确cost，
   禁UPDATE immutable/禁关trigger/禁fixtureFK错误。
3. 加真实PG完整GET回归覆盖0/0、19/20、20/19、20/20及21/21、
   localCanary对应gate不可pass、独立Shadow历史仍可展示、Active整链不可用；
   localShadow不足下限不得认证、local非pass不足样本仍正确展示；
   自定义冻结candidate/stable下限（例如>20）按冻结值验证、合法边界对照，
   Active合法local基线规则不回退/不漂移到新leaf。不要只测内部helper。
4. 最小修复后GREEN原minimum/newregressions，原47+17/新增complete47、
   F1九/C1sameartifact两部署/S1-S3/S1-R全维持。badreference/latestmalformed/
   unknown/failed/完整command、count/fee/keys/Decimal21 positive不漏。
5. 全最终backend、关系API、Node20build/全UI双viewport；真实PG production
   原六场景+minimumzero，七场景双viewport正确性PASS，实际看关键截图，
   HTTPassetbytes匹配dist/GETonly/auth/privacy/keyset/RunTraceimmutable/
   legacyNULL/abortreset/mobile保持。常规green不能覆盖新正确性FAIL。
6. 源全集含新增tests在最终矩阵before/after且逐freezeGitblob；证据不循环
   入hash。rawXML/log/commandUTC/runtime/protocol/threshold/source/role/
   request/failed/interrupted/cost/manifests可复算，重叠不加独立样本，
   未计量HTTPunknown不补零。旧中断/tmp丢失counts/time/costunknown保留，
   originalRED/invalidattempts全部原样归档不覆盖。
7. exactUUIDDB/key/browser/cache清理，主树/venv/cache不变；自建nonpersistent
   Redis只核身份后SHUTDOWN NOSAVE，不用prefixDEL/flush清未计量workerkeys。
   共享PG/runtime保留供审查，明确自有服务状态，不停共享PG/删他人库。
8. 具体本次paths stage、全部stagedsecret/localvalue+ZIPmembers扫描、
   gitstatus/diff/log/HEREDOC NEWcommit（必要product再docscommit），
   不amend/push/config/hooksbypass，不剪rawwhitespace求green。
   先完整写 `/tmp/m3-task9-minimum-fix-result.md`，同字节报告与全部raw随新
   repo docs目录持久留档防/tmp丢失。实际freeze/parent/sourcecountSHA/
   manifests/files/REDGREENfullAPIUIprodcounts/commands/resource/限制完整。
   实施green不是验收，父侧后续freshWHOLESPEC再freshWHOLECODE。

## 现役环境

Python `/tmp/eduagent-m3-patched-runtime/bin/python`3.11.17，PYTHONPATHM3/python，
TZUTC，pytest -c pyproject.toml。新runtime58installeddist/44入口约束全满足；
父侧新扫描projectclosure57depsinput3a13e8c...3103/audit40cd...b2a于02:40Z
exit0/0已知漏洞仅Task10preflight，不冒充你的安全审计/正式release。
主venv只读，不向sourceeditableinstall、不重装此现役runtime。
PG16.15 127.0.0.1:57432 postgres trust PID16852，bin
`/opt/homebrew/opt/postgresql@16/bin`，datadir
`/Users/bytedance/Library/Caches/eduagent-task9-test-services/d7c17eb6-6c53-4bca-9c54-26b53147cd36/pgdata`。
每invocation自有UUIDDB/finallydrop，只测试distributedURL，不生产DATABASE_URL。
Redis原57379/58479已停，自己新UUIDnonpersistentloopback实例新freeport与账本。
Node20.19.5 binary .npm/_npx/39826d059b592c66/node_modules/node/bin/node，
M3physicalmodules实体copy自有tmp不symlink源；Vite7.3.7/plugin5.2/React18锁
不降级。browser前读skill，新端口/trace/cache；Docker不可用不安装，未实CI
不认绿，zero模型，Agent50paused。父侧期间只准备tmp非重叠材料。
