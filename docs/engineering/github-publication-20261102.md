# GitHub 分支对比与发布归档：2026-11-02

## 核验结论

此前的主要问题是默认分支落后，不是 M3 提交丢失。核验时 GitHub 默认分支
`main` 位于 `be36daa`（M2），远程 M3 分支位于 `e4ea5c3`；最新本地 M3 位于
`f1b2a3e`，有 7 个面试材料提交未推送。GitHub 没有 PR 合并记录。

本地 `main` 位于 `2ff803c`，比远程 main 多两份 M3 设计/计划提交。
它是最新 M3 的祖先，已用 `git merge --ff-only --no-overwrite-ignore` 快进到
`f1b2a3e`。这保留所有提交、原有源码版本和历史评测证据。

本轮发布目标是把 `main` 与 `feature/m3-trusted-policy-promotion` 同步到同一
归档提交。最终 SHA 以包含本文件的提交及 GitHub 分支引用为准，不能将
历史 CI 的 SHA 当作本轮发布 SHA。

## 各分支与最新版本的关系

表中差异以核验时最新本地版本 `f1b2a3e` 为基准。

| 分支/工作树 | 核验时 SHA | 最新版是否包含其历史 | 差异与处理 |
| --- | --- | --- | --- |
| GitHub `main` | `be36daa` | 是 | 落后 83 个提交；76 个已在远程 M3，7 个仅在本地；本轮快进发布 |
| 本地 `main` | `2ff803c` | 是 | 落后 81 个提交；已有两份设计提交不会丢失 |
| 远程 M3 | `e4ea5c3` | 是 | 代码和 Task 10 CI 留档已推送；缺少最新 7 个文档提交 |
| 本地 M3 | `f1b2a3e` | 是 | 本轮整合基线 |
| M2 本地/远程 | `be36daa` | 是 | 落后 83 个提交，保留作为历史里程碑 |
| M1 正式工作树 | `adba300` | 是 | 落后 98 个提交，保留历史分支 |
| 早期教育 Harness 远程分支 | `e70f51e` | 是 | 落后 155 个提交，保留历史分支 |
| M1 API 临时工作树 | `9a6b7eb` | patch 已包含 | 1 个独有 SHA，`git cherry` 返回 `-`：对应修改已在正式主线 |
| M1 runtime 临时工作树 | `30953db` | patch 已包含 | 5 个独有 SHA，`git cherry` 全返回 `-`：对应修改已在正式主线 |

`git cherry -v feature/m3-trusted-policy-promotion <旧分支>` 的 `-` 表示等价 patch
已存在，即使 SHA 因历史 cherry-pick 不同。这里没有需要重新 cherry-pick 的 M1
功能，不应重复应用。临时 worktree 被标记为 prunable，但本轮未删除工作树或分支。

## 当前内容与旧默认分支相比增加了什么

| 范围 | 旧默认分支 M2 | 最新内容与证据入口 |
| --- | --- | --- |
| 评测与资格 | 既有开发评测/优化 | Judge v3、unknown、资格回执、runtime/source/protocol 绑定；[协议](trusted-policy-promotion.md) |
| 策略控制面 | 无 M3 完整控制面 | artifact、deployment、签名命令、不可变 Run binding |
| 执行隔离 | Run/Expert Plane | rehearsal/Shadow 专用状态、权限复核、迟到结果拒绝 |
| 健康与回滚 | 无 M3 完整路径 | matched Canary、冻结健康窗口、事务化回滚、迟到 observation 审计 |
| Ops | M2 Runs/Experts/Workers | Policies 页面、版本关联、脱敏健康/回执/审计；Task 9 独立审查未完整封存 |
| 工程验证 | M2 接管/基准 | Task 10 真实多进程 SIGKILL、绑定保持、回滚、Compose smoke 和远程 CI |
| GitHub 叙事 | 教育产品先行 | Harness 主线、M0–M3、权威边界与可复现案例；[README](../../README.md) |
| 现场讲解 | 阶段性索引 | [30 秒/3 分钟/10 分钟讲解](interview-playbook.md)、[六组 L1–L4 技术追问](interview-technical-deep-dive.md) |

对比 `be36daa → f1b2a3e`，全部树差异为 14,023 个文件；其中 Python、
前端源码/E2E、tools、CI、Compose、环境示例、README 与工程说明合计 179 个文件，
增加 30,318 行、删除 554 行。巨大总数主要来自 Task 9 历史冻结审查证据，
其中包含重复源码、构建缓存和 raw audit，不代表新增了 14,023 个业务文件。
本轮保留这些已有远程档案的 hash/manifest 关系，不改写历史。后续应将审查快照
与运行源码分开管理，避免继续把缓存强制加入 Git；历史快照体积治理另行处理。

## 补齐未推送材料与遗漏证据

此前只在本地的 7 个提交如下，本轮随最新主线一起发布：

| 提交 | 内容 |
| --- | --- |
| `efdf9ad` | 面试叙事与技术深度设计 |
| `09d72a5` | 当前事实索引 |
| `2a39150` | README Harness 主线 |
| `4ba8895` | 现场讲解手册 |
| `3419471` | 技术深挖手册 |
| `f0c900c` | 实施计划 |
| `f1b2a3e` | Markdown 格式修正 |

还发现 [Task 7 过程记录](../superpowers/reports/2026-11-01-m3-task7-shadow.md)
提及的 11 份 JUnit XML 被忽略规则排除，未进入 Git。本轮原样归档它们，
合计 379,698 bytes；复制前后 SHA-256 相同。失败、中断和成功证据均保留，
没有重跑、修改测试数量或把这些历史结果归到当前代码。

| 文件 | testcase | failure | SHA-256 |
| --- | ---: | ---: | --- |
| [task7-crossplane-backend.xml](../superpowers/reports/task7-crossplane-backend.xml) | 1290 | 0 | `566338ecf93c416f52aaafa451670e087c80f6a61824412c7bc93a8db53d732e` |
| [task7-crossplane-green-final.xml](../superpowers/reports/task7-crossplane-green-final.xml) | 90 | 0 | `cedd71194618718782ac0b33b54ec80035cba1ed7ed4f7b9c825da755dc593e1` |
| [task7-crossplane-green.xml](../superpowers/reports/task7-crossplane-green.xml) | 82 | 0 | `8672136f780c5e498b0838b2b0e0ce1423e4d72214c4977e0a915b7f962bc2c9` |
| [task7-crossplane-matrix.xml](../superpowers/reports/task7-crossplane-matrix.xml) | 289 | 0 | `f01063b080b7303de89373ec667adea20c918ad6ff2e7fec387a7fbc0a37da2b` |
| [task7-crossplane-red-final.xml](../superpowers/reports/task7-crossplane-red-final.xml) | 82 | 70 | `2660060287a58341bc9183fdada87dc79d799c8bb8c52a5c5558acef52a2c38b` |
| [task7-crossplane-red.xml](../superpowers/reports/task7-crossplane-red.xml) | 82 | 70 | `714f02fb5df256ac1de3dbba710cf919e522b0caf35205c086099eba08c601a1` |
| [task7-crossplane-state-red.xml](../superpowers/reports/task7-crossplane-state-red.xml) | 4 | 4 | `953a2f1890fa49f707f3a6b932826db871882cc2120ccb59df21c4efbf4af688` |
| [task7-fix-green-final.xml](../superpowers/reports/task7-fix-green-final.xml) | 20 | 0 | `c82e6e8548664a7aa39808e49750946e3c6df71cd359498f16dab647cc51e44e` |
| [task7-fix-green.xml](../superpowers/reports/task7-fix-green.xml) | 20 | 0 | `b42c801d5a7bf4a6664451c3a84a8298f43cbe186be9d276f2624851c1bc3b7d` |
| [task7-fix-matrix.xml](../superpowers/reports/task7-fix-matrix.xml) | 199 | 0 | `1d632739ae3e6a9949f4d1a775e95e0f4d107d9fc56942beee12bc2605c0cc8c` |
| [task7-fix-repeat.xml](../superpowers/reports/task7-fix-repeat.xml) | 20 | 0 | `7d1102f07a248296b3028c994b610181aa5e8ec3cbe6ab4395da74d8a6eec270` |

`.gitignore` 增加精确白名单，允许本轮面试材料、设计、计划、归档记录和 Task 7
XML 正常跟踪，其他缓存、数据库和本地密钥仍遵循原有忽略规则。

## 验证与可复盘入口

- 所有正式历史分支均为最新主线祖先，或经 `git cherry` 证实 patch 等价；
- 主线快进不产生重写提交、强推或额外合并冲突；
- Task 7 XML 可解析，逐文件 hash 与原工作树相同；
- 新增文件进行凭据模式检查，结果只报告命中数，不回显敏感内容；
- 提交前验证新增相对链接在目标 Git 树中可见，不能只以本地存在为通过；
- 正文执行 `git diff --check`；两份历史失败 XML 中共四行原始异常输出带尾随
  空白，原样保留以维持上述 hash，不对运行证据做格式重写；
- 远程发布用同一个提交更新 `main` 与 M3，随后核对两分支 SHA、GitHub README
  与本地 blob 一致；
- 本轮没有模型请求，也不把这次 Git 同步算作新的运行时评测。

已通过的源码绑定 CI：
[实现 `f8b8e3c` 的 CI](https://github.com/codedog678/eduagent/actions/runs/41457794154)，
[文档 `e4ea5c3` 的 CI](https://github.com/codedog678/eduagent/actions/runs/41460144960)。
发布后的 CI 属于新 SHA，必须单独查看，不能沿用历史 success。

正式验收限制继续以 [Task 10 记录](m3-policy-promotion-acceptance.md)为准：
Task 9 独立审查未完整封存；正式 Judge v3 eligible campaign rehearsal 未执行；
fixture 工程验证不能证明模型或学生学习效果。

## 后续工作入口

默认从 `main` 开始工作，新任务再开一个短期分支。M1/M2/早期教育分支只作为历史
定位，本轮没有删除它们。展示当前成果时使用仓库首页，而不是旧里程碑分支。

```bash
git fetch origin
git rev-list --left-right --count origin/main...origin/feature/m3-trusted-policy-promotion
git diff --quiet origin/main origin/feature/m3-trusted-policy-promotion
git log -8 --oneline origin/main
```

若本轮发布完成，前两条比较分别应输出 `0 0`、退出状态 `0`。
