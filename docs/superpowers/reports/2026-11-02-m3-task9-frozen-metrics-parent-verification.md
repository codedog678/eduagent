# Task9 完整指标修复：父侧冻结与原件核验

父侧已核验工程冻结和原始材料；这不是独立规格或代码审查，不授予 Task9 验收。
接续顺序仍为 fresh WHOLE SPEC → 新 PASS 父核并 NEW 归档 → fresh WHOLE CODE。

产品 `780087401022dcfb3be904dee9ee442675625dc6`，父 `ffc607d4908dc50d3d7977d8056a7d33385b78e5`；
主证据 `be56f27b67ee3bc54db71388f68de86f70358313`；
交接 `5d6e717b3ea715524cfed2e7e2e4ee143499618e`，父为主证据。
完整源码 358 files，SHA `788bbb025f2b26684e676fbafd6b8aded30054d0541aa8a72d786356e5fe43f0`。

| 核验对象 | 父侧独立复算 |
| --- | --- |
| 实际 Git blob | 当前 M3 14889、起始 8225、primary 1110；新增文档 6663；仅四个产品文件变化 |
| 主与补充 payload | 6645 与 15 文件；manifest 逐项匹配，均不包含自己 |
| 原始执行证据 | 49 XML 每个 testcase/outcome/issues/time；51 完整快照原字节相等，其中 24 对属于最终源码 |
| 最终矩阵 | backend 2080、API 492、integrity 131、boundaries 67、原42互补42、UI54，均无失败/错误/跳过 |
| 保留失败 | 原互补 6P/36F；所有中间失败、setup 与辅助错误不覆盖、不与最终分母相加 |
| 浏览器原件 | 176 ZIP / 5816 members 的 CRC、SHA、事件与实际网络正文；共272资产比对，最终136 |
| 最终真实 PG 生产构建 | 17场景×2视口=34，16手机健康场景真实横滚、2实际 pinned Trace 视口 |
| 历史原件 | 7005 files / 19 manifests / 270 XML / 826 ZIP / 29194 members；旧352-source清单对原Git版本 |
| 资源 | 47精确UUID库实际 remaining0；共享PG16.15/57432/PID16852保留；62049/62050/62051关闭 |
| 运行环境 | Python3.11.17、58dist、39声明+5修复floor；两当前树tracked/index/venv/cache和runtime首末一致 |
| 秘密扫描 | 两actual值、15999 current Git原件、1002ZIP/35010members、1TAR/358members；有效命中0 |

秘密模式只分类旧固定 Git blob 的 scanner assertion 两行，未扩大白名单。
Redis 自有非持久服务经身份/配置验证后 SHUTDOWN NOSAVE；子进程 key 账本不完整，
不能说逐 key 删除。原 raw XML/log/HTML 空格不重写；正常 hook 超时不等于完整扫描通过。

实际查看四张关键图，判断及截图 SHA 在 parent-visual-notes.json。
合法 metrics Active 左侧手机图来源文本裁切，不称整段可见；合法 leaf Active 图两来源标签可见。
Active fixture 的 is_current=false/head仍Canary 如实保留，不能称实际晋级写入。
父侧另标记 fresh SPEC 需探测真实 health worker 的 hard_failures/前序硬违规窗口，
这里只列检查议题，不预判其展示为 PASS 或 FAIL。

新增历史费用准备完整原件随本次持久归档：124固定 Git 原件/108manifest条目/8历史价格源码；
五轮147请求、八轮251请求，分别0.50906508–1.01813016与0.76513228–1.53026456元估价。
两者有重叠、只重复6例；Agent50另82请求，语义仍paused/null。
原v1缺确认字段、最早manifest缺data_role均保留，未回填旧档。
费用按2026-10-25历史冻结价格，不是当前价或供应商账单；C34旧联网费用仍unknown。

本轮0新模型、actual USD 0；全局HTTP数unknown。未Docker/CI实跑、未正式v3资格或教学效果验证。
完整父核、实施者交接提交后的raw与代码、历史费用原件均位于同层
`task9-frozen-metrics-parent-evidence/`。本报告与manifest不循环包含自身提交身份；
新提交之后的真实HEAD/日志交下一波归档。
