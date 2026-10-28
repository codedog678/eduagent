# 学习者并发与模型排队边界

## 设计

沿用用户确认的方向：不同学习者并行，同一学习者的完整执行、提交和回滚串行；模型请求共用有限额度并设置排队超时。

选用单进程按学习者加锁，并保留同步 SQLite 短事务。全局锁无法满足跨学习者并行；多进程与分布式锁会扩大状态一致性改造范围，本轮不采用。

- Harness 与 Agent 均使用按学习者分组的锁；无持有者和等待者时回收锁条目。Tutor 的尝试/提示计数使用 `(learner_id, 题目后缀)` 内存键，避免 `alice` 与 `alice:team` 被前缀匹配混入；持久化仍使用原题目后缀，旧检查点无需迁移。
- `HARNESS_QUEUE_TIMEOUT_SECONDS=10` 控制等待同一学习者的时间。未获得锁时返回 HTTP 503 和 `Retry-After: 1`，不创建运行记录，不执行操作；客户端可复用请求 ID 重试。
- 获得学习者锁后启动原业务执行期限；模型排队包含在当前业务、handler 和工具的已有期限内，以先到者为准。
- `LLM_MAX_CONCURRENCY=4` 限制单服务进程/事件循环内的远程模型请求，跨 LLMService 实例和模型供应商共享；覆盖普通生成、原生工具调用、embedding、rerank 和后台记忆摘录。旧 OpenAI/Anthropic HTTP 适配器及其 DeepSeek/MiniMax 子类同样使用该额度。
- `LLM_QUEUE_TIMEOUT_SECONDS=10` 控制等待模型额度的时间。额度仅在实际网络调用期间持有；排队超时不发请求，抛出 `model_queue_timeout`，前台运行回滚且可以重试。异常与取消均释放额度。后台作业保留失败原因并按既有机制重试。
- 保留单 worker 文件锁。SQLite 提交代码不包含 await，不让网络请求持有事务。
- 会话/主题归属在提交时再次核验，阻止不同学习者并发认领同一新 ID。
- 当前运行单独保存事件引用，结果与失败轨迹不依赖会被其他运行挤出的全局历史。
- Agent 状态反映并发中的处理数；模型健康信息提供上限、正在执行数、等待数与排队超时数。Trace 记录成功取得额度、排队超时和取消时的等待时间。
- 新配置纳入公开执行指纹并传入 Docker。

## 验收

使用受控异步事件和 mock transport，无真实模型调用：

1. 两个学习者能同时进入同一个 Tutor handler；同一学习者仍串行，重复请求只执行一次。
2. 一人失败/取消只回滚自己；另一人的状态、原文、事件与提交结果不受影响。
3. 学习者排队超时/取消不会执行操作，也不会遗留锁；重试仍可成功。
4. 多个 LLMService 与 embedding/rerank 共用上限，超时不发请求；取消等待或在途请求后额度可复用。
5. 模型排队遵守业务 deadline，普通生成不能把排队失败伪装为模板成功。
6. 并发会话 ID 冲突被拒绝，提交失败仍原子回滚；全局事件历史淘汰不会污染当前结果。
7. 原离线回归、配置与 API 检查通过。

## 验证记录

2026-10-29 完成实现与断网验证。

| 检查 | 结果 |
| --- | --- |
| 新增并发测试 | 42 passed，1.61 秒 |
| 完整后端回归 | 511 passed，14.08 秒 |
| 既有 warning | `tests/v2/test_agent_base.py` 中 `TestAgent` 带构造函数，pytest 不将其作为测试类收集 |
| 远程模型请求与新增模型费用 | 0；使用断网入口、注入 SDK 和 HTTP mock |

新增测试位于 `python/tests/test_harness_concurrency.py` 和 `python/tests/test_model_concurrency.py`。测试用异步屏障证明两个学习者同时进入真实 Tutor handler；另行验证 Tutor 已修改本地状态后失败/取消时的学习者隔离、会话/主题新 ID 并发认领冲突、重复请求重放、排队 503 重试、全局历史淘汰、冒号 ID、模型额度跨实例/适配器/embedding/rerank 共享，以及在途 SDK 请求取消后的额度回收。

本轮首次测试中的异步 fixture 未进入事件循环、测试快照引用被原地修改两项问题均已修正；最终结果使用完整重跑取得。

复现：

```bash
.venv/bin/python python/scripts/test_offline.py tests/test_harness_concurrency.py tests/test_model_concurrency.py -q
.venv/bin/python python/scripts/test_offline.py tests -q
```

配置写入 `.env.example`，Docker 透传三个新参数；配置变更重启后生效。验证范围是单 worker 异步执行正确性，未进行真实模型并发压测，不能据此声称吞吐或 P95 改善幅度。已有模型调用与策略评测报告保持历史原值；新配置进入运行与策略兼容指纹，旧策略包后续评测应使用新运行指纹。
