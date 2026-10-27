# RSI R3–R6 工程交付与运行说明

日期：2026-10-27。实现范围：受控离线改进闭环。真实校准、独立留出和生产发布尚未执行；当前没有获得晋级策略，不宣称递归收益。

## 已接通的链路

| 环节 | 实现与实际边界 |
| --- | --- |
| 输入 | FailureQueue只接收公开证据摘要、能力组、白名单错误码、development角色。拒绝holdout角色，不接收学生正文/标识或答案；导入真实日志仍须先人工确认资料角色。 |
| 搜索 | 复用GEPA 0.1.4和原Harness Adapter，父版本来自内置基线或已验收注册策略；仅12条检索/历史训练例反思。失败计数作为附加反馈，固定训练资料不自动替换。 |
| 开发 | 14例、3次配对；TSR提高或持平且工具决策提高；至少2/3次同方向，自动检查零成对回归、能力组不下降。 |
| 留出 | 18例、每能力3例；要求材料摘要和近重复审阅人；整体TSR与目标能力同时提高。逐题证据留在验收目录，不进入反思。 |
| 整链 | 复用LongTaskExecutor，Coordinator开启，6条旧任务×3次×2策略；共享预算、逐例恢复、原始轨迹重评分、D01–D08、教学准确性和答案泄露审阅。旧6条属于回归开发资料。 |
| 注册 | 策略包绑定父版本、固定组件、提案器、协议、模型/运行配置、源码、证据摘要。注册重新核验门槛；simulation配置无法授予真实资格。 |
| 加载 | 活跃指针原子替换；run固定版本。待答问题查创建run，计划/测验存创建版本，缺包或版本冲突明确失败。Tutor使用该版本检索组件，专家交付继承同一run版本；专家提示和权限仍固定。 |
| 回退 | 切换active指针，保留策略包、事件、评测和学习状态。默认关闭自动回退；默认50条窗口、至少20条，提交失败率≥10%触发。已确认权限突破可立即触发；普通工具拒绝不是权限突破。 |
| 循环 | 最大代数、最少新样本、累计费用/请求、连续停滞/故障边界；下一代继承合格父版本。没有校准/新留出/教学审阅时进入等待，不自行生成“已通过”证据。 |

## 命令入口

在项目Python环境中，从`python/`运行：

```text
python -m evals.optimization.cli prepare --output /path/protocol.json
python -m evals.optimization.campaign_cli prepare --output /path/campaign \
  --protocol /path/protocol.json --registry /path/registry --config /path/config.json
python -m evals.optimization.campaign_cli status --campaign /path/campaign
```

上述准备/查看命令不调用模型。真实运行命令须显式添加`--allow-remote`，本次没有执行：

```text
python -m evals.optimization.campaign_cli run --campaign /path/campaign \
  --holdout /path/holdout.jsonl --allow-remote
python -m evals.optimization.campaign_cli harness --campaign /path/campaign --allow-remote
python -m evals.optimization.campaign_cli run --campaign /path/campaign \
  --harness-evidence /path/harness-reviewed.json --allow-remote
```

`harness`先跑断网确定性合同，输出`harness-pending-review.json`。教学审阅必须覆盖18个候选案例/重复，记录`case_id`、`repeat`、`observed_hash`、`reviewer`、`reviewer_kind`、`rationale`、`accuracy_passed`、`no_answer_leak`和`disputed`。助手审阅不可标为人工金标准。补齐证据后`run`重新验收并注册，不激活策略。

`release --enable-release`与`rollback --enable-release`是独立操作。服务端须显式配置`POLICY_LOADING_ENABLED=true`和`POLICY_REGISTRY_PATH`，且实际模型及运行参数匹配策略包。`POLICY_AUTO_ROLLBACK_ENABLED`默认false。未配置时保留原行为。

## 冻结配置

配置必须包含`max_requests`、`max_cny`、`source_revision`、`runtime_hash`、`deployment_runtime_hash`、`calibration_manifest`、`simulation`、`max_metric_calls`、`minibatch`。真实配置还需`calibration_sha256`；校准原始评估必须记录实际`judge_identity`并与当前DeepSeek Flash、thinking disabled匹配。

源码摘要来自`evals.live_runner.code_revision()["python_source_sha256"]`。组件/部署摘要由`evals.optimization.runtime.component_runtime_hash()`和`deployment_runtime_hash()`在预设运行参数下生成，包含provider/model身份。变更代码、裁判、模型或固定组件后重新冻结基线；不能继承不兼容策略。

留出前额外要求`holdout_review_sha256`与`holdout_reviewer`。这些是可追溯审阅声明，不是自动语义去重算法。真实18条材料仍待准备，本轮测试中的改名/追加文本夹具只用于检查入口，不是独立测试数据。

`loop --config /path/loop-config.json --allow-remote`复用上述命令链路。外层配置含`output`、`queue`、`registry`、`dataset`、`protocol`、`limits`、`campaign`；`limits`有`max_generations/min_new_samples/max_stagnation/max_failures/max_requests/max_cny`。可用`generations["0"]`等逐代提供新留出材料与证据路径。循环强制共用一个budget_id和账本；缺证据等待，补齐后恢复。当前没有创建定时任务或启动后台循环。

## 持久化、恢复与隔离

共享账本固定为`~/.eduagent/rsi/ledger.sqlite`，不在campaign输出目录内。CLI不提供更换账本参数；独立测试通过构造器注入临时库。账本冻结路径写入campaign绑定。留出按文件摘要和任务签名消费，同campaign/候选可恢复，其他目录/候选不可复用；手工删除或替换用户自己持有的数据库不属于密码学防篡改保证。

每个请求先提交预留再调用供应商，usage确认后结算；中断保留unknown标记和预留，补发新attempt另计。费用依旧为冻结价格估算，不是供应商账单。调用成功但usage丢失仍保留预留，不推断零费用。

搜索冻结为每个候选/案例复用首次完整结果；开发/留出各自独立三次重复。比较按完整侧结果保存，不完整配对不生成验收凭证。整批开始前检查最坏请求量；费用每次请求前保守预留，费用不足可能中途停止，已产生请求不会消失。

GEPA中断状态仅保存于本地campaign的`gepa/`，成功后清理。状态使用GEPA原生pickle，不能导入不可信外部状态目录；不提交二进制缓存。公开评估、失败、策略及预算归档保留。共享数据库、queue和服务数据库不入Git。

## 当前完成度

R1–R6的工程路径与确定性合同已交付。真实校准、独立留出、候选收益、影子/灰度及R7研究仍待实际实验。当前校准门禁会阻止真实campaign前进，这是预期结果。该实现不承诺每轮产生提升，也不把反复运行等同递归改进。
