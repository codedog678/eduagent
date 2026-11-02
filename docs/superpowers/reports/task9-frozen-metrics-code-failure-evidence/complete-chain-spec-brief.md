# Task9 恢复修复后 fresh WHOLE SPEC：待实际冻结后启动

父侧已核对实际 NEW freeze、全集源码/归档Gitblob、rawXML/快照/资源与秘密，
本页现在用于启动新的独立WHOLESPEC。实施和父侧核验不等于独立验收。
起始85c2759为失败归档，不是修复或验收版本。

## 本次实际身份和父侧已核对材料

- 当前review HEAD `ed42d33a187115825a8a94fb45ae8b4652cf4c11`，parent/
  产品freeze `9ef34434cc72f270085d234d89eae5f22d3d6ecd`；product parent
  `85c2759d54fd55691cf69d98df91c81ad9caf65b`。ed42仅NEWdocs证据。
- 全354python/frontend源（含新47项完整GET测试）SHA
  `6fb437fa79b04874756c3a762aa62a2d7a8c8c39193769811eb9a779ecb93e96`；
  当前clean，源每字节对product和reviewHEAD Gitblob。
- `docs/superpowers/reports/task9-complete-chain-recovery-evidence/` 共598文件，
  外manifest597payload SHA
  `330fa3eef8833666cf8ae0c0adec5c27d1c2211a6f4c3d57c7f79edecb9cb173`，
  manifestSHA `35c56ec0e1a5c2cfd25d0b889b0078bcfad4167edc51cfd9f851fe4ab9c559ee`。
  raw-only592scope与后续补充区分，报告SHA
  `93d1943ed901e4051a82fabd3cdc5bd0e94469753db2d650fa4abd819b953181`。
- 父侧实际复算3374当前trackedGitblob（旧档含在内）、358baseline tar blobs、
  18XML/19paired完整快照/76traceZIPCRC/2969ZIPmembers，local秘密值2distinct
  匹配0；结果 `/tmp/m3-task9-complete-chain-parent-verification.json`、
  runner `/tmp/m3-task9-complete-chain-parent-verify.py`。该执行只证明provenance，
  不能当你自己的规格检查或运行。
- 实施有效RED integrity47=42/5、metadata17=11/6、new47=16/31、
  productionpoison2=0/2；GREENnew47/integrity47/metadata17/API291/full1840/
  UI54/六production双视口12均无failure/error/skip。旧无效attempt完整保留。
- 父侧实际查看poison/合法Active各desktop/mobile共4关键图，
  poison完整health来源不可用，合法仍双来源；不能替代你本人截图/正确性验证。
- actual15UUIDDB查询无残留；owned ephemeralRedis已shutdownNOSAVE，
  57379/37730/37731已关闭。248记录exactkeys不冒充全部曾创建keys；
  另11UUIDworkerkeys+1非UUIDkey归属初始化链未装表，已随自有非持久服务停服，
  无DEL/FLUSH，旧identity的redisPID不能当当前服务。共享PG见下。
- runtime实际58dist/44入口约束匹配，最终兼容full1840已执行；
  **该runtime漏洞扫描未执行**，父侧54旧env扫描FAIL仅Task10预检。
  主266source/index/.venv和源Vitecache当前仍对应本轮恢复起点。

唯一目标树 `/Users/bytedance/Documents/trae_projects/eduagent-m3`，branch
`feature/m3-trusted-policy-promotion`。primary `eduagent` source/index/.venv
只读。用户批准设计、新实现者→NEWfreeze→fresh WHOLE SPEC→PASS后fresh
WHOLE CODE；不重新询问许可。你只能读源码/tests/index，写自有UUID tmp，
不 commit/push/模型请求，不自行验收或启动 CODE/Task10/Agent50。

WHOLE范围：Task8 acceptance `8869166878a193a1c453376471cbe52c8fa84b3f`
至父侧提供的实际 freeze，整个 Task9（初实现、F1、C1、S1-S3、S1-R、
中断恢复和所有前后端影响），不能仅审查最后修复 diff。
权威为 `docs/superpowers/specs/2026-10-30-trusted-policy-promotion-design.md`
全文与 `docs/superpowers/plans/2026-10-30-m3-trusted-policy-promotion.md`
Task9六步；实现交接 `/tmp/m3-task9-recovery-implementation-brief.md`、
实际结果 `/tmp/m3-task9-complete-chain-fix-result.md` 及新的 repo 原始归档。
完整读旧失败 `docs/superpowers/reports/2026-11-02-m3-task9-chain-spec-failure.md`
和 `task9-chain-spec-failure-evidence/`，以及历史 F1/C1/S1-S3 的原始材料。

## 必须独立证明

1. Active 精确引用的 Canary receipt 自身无效时，经该断链连接的 Shadow
   也不得得到 passed/consumed_chain。不得以另一合法 latest leaf 替换引用，
   不 fallback 同 artifact 相邻 deployment，不靠前端删行隐藏后端问题。
2. 精确receipt的 gate/status/四维/issuer/model/data_role/strictversion/
   deployment/window/threshold/evidence/time/sample_count/Decimal cost/
   bounded observations 全有效；canonical command 全8字段、audit、
   approval/required/actor/reason 与两段消费关系闭合，不把两份错声明
   相等当真实证据。缺/错/过期/malformed/failed/unknown 都 failclosed。
3. 原有效47integrity/17metadata-v2/生产引用poison双视口须独立正确行为
   GREEN；11种poison为同根因。原0收集、2FK无效尝试原样保留，不计
   PASS或产品缺陷。实现 recovery baseline replay RED 是新独立运行，
   不能伪称发生在中断前或原作者修改前。
4. 正向合法Active双来源、Canary独立Shadow历史、local/current/history、
   latest审批遮蔽、transition cutoff、同artifact两部署、20/20及21/21
   循环Decimal保持；不全局删除health求绿。新增完整GET回归真实有效。
5. 全WHOLE auth/四GET/严格query/422-404-503/keyset100/closedDTO/
   numericpoison/隐私/REPEATABLE READ READ ONLY/bounded SQL/GET不写/
   F1九条/C1两部署/RunTrace immutable binding/legacy NULL，全验证。
   UI loading-empty-error-staleabort-disposed-filterreset、无写控件、
   mobile真横滚/document overflow，来源可信不能只看DTO形状。
6. 自己完整后端、关系/API和有意义攻击、Node20 production build、
   全UI双视口、真实PG生产 current/history/synthetic malformed/
   genuine malformed/genuine valid/referenced poison 六场景双视口。
   实际看关键截图，HTTP资产字节/hash与dist一致，GET-only正确；
   “观察到bug”不能当正确性断言PASS。
7. 实际freeze source全集包含新增测试，before/after对Gitblob；
   XML counts/hash/commands/UTC/environment/role/request/cost/failed/
   interrupted诚实，证据不参与source hash循环。实现者/父侧运行
   不冒充自己执行，重叠suite不加为独立样本，unknown不补零。
8. 所有历史失败档案byteexact保留。前代理已killed、/tmp evidence和
   runtime曾丢失，是事实边界；不能断言其丢失运行的具体请求数或费用。
   核对恢复后源/index/主venv前后未变，不把跨断点元数据说成全相等。
9. exact自有UUID DB/key/browser/cache清理，保留实际指定共享测试基础
   服务/runtime供下轮审查时明确区分。主树、主venv、source Vitecache
   不写；Docker不可用不装、不声称实际CI/容器/live资格/教学效果。

## 环境与交接

实际恢复runtime `/tmp/eduagent-m3-patched-runtime/bin/python` Python3.11.17；
PG16.15 loopback127.0.0.1:57432 postgres trust，PID16852/data-dir
`/Users/bytedance/Library/Caches/eduagent-task9-test-services/d7c17eb6-6c53-4bca-9c54-26b53147cd36/pgdata`。
父侧刚连接核对实际data-dir/PID/version，不删共享库/服务。
Redis原57379已停，你在自有UUIDtmp启动独占无持久Redis（可同关闭端口，
先验证free、新identity账本），每invocationexactkeys，并最终shutdownNOSAVE
自身服务处理子process未装表keys，不能把全前缀清除或DEL他人key当cleanup。
完整运行前快照两树/tracked/source/index/venv/Vite cache，遵守只读边界。
PYTHONPATH=M3/python，TZUTC，
pytest -c pyproject.toml。每invocation自有UUID DB，finallydrop，只测试
distributedURL，不触碰production DATABASE_URL；Redis只exact自有keys。
Node20.19.5/Vite7.3.7/plugin5.2/React18，不降锁；实体copy modules自有tmp，
禁止symlink回source。Browser工具前读skill，新ports/trace/cache。

最终完整写 `/tmp/m3-task9-complete-chain-spec-result.md`：WHOLESPECPASS/
FAIL、逐项权威fileline和原始材料、有效复现actual/expected、独立计数/
命令/time/SHA/source/资源/未执行限制，另保留自有raw manifest。
父侧核验并归档PASS后才新WHOLECODE；你不自行跳阶段。
