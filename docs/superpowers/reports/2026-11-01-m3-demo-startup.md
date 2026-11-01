# M3 后 Expert 演示命令兼容验证

记录时间：2026-11-01T10:39:18Z。基础 revision：
`fd6f5196a5f552e47fe8fb3972849aedc3609f8b`。
范围仅为两个演示脚本、共用请求构造器、README 运行说明和本报告。
Task8 的健康评估实现不在此次修复或验收范围。

## 事实与修复

旧脚本仅执行 `metadata.create_all + upgrade_m1_schema`，既缺少 M3 稳定策略
引导，又缺少正常 worker 启动需要的 schema version/hash marker。实际红灯首先
发生在受理：`ArtifactUnavailable`，尚未到达 worker 启动。
原错误见 [admission 红灯](demo-startup-admission-red.log)。

换为完整 `migrate_schema(engine, 120)` 后，受理成功，专家请求因仍使用
硬编码策略且未继承 deployment/namespace，被现有父 Run 绑定校验拒绝：
`ExpertFencingViolation: expert policy binding differs from parent`。
两条命令的原错误分别见 [demo](demo-startup-binding-red.log)、
[benchmark](benchmark-startup-binding-red.log)。

共用构造器现从 `claim.policy_binding` 校验并继承快照和执行权限的固定字段。
迁移仅作用于脚本创建、独占的临时数据库，不改变正常 runtime 的只读启动协议。
不添加可跳过绑定校验的演示分支。

## 实跑

实际解释器：`/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python`。
Python 3.11.17、PostgreSQL 16.15、Redis 8.10.3、macOS arm64。
在 `eduagent-m3` 工作树执行如下两条命令，各自创建不同的数据库及 stream：

```bash
DISTRIBUTED_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:55432/postgres \
DISTRIBUTED_REDIS_URL=redis://127.0.0.1:56379/0 \
LLM_PROVIDER=template MEMORY_RETRIEVAL_MODE=lexical MEMORY_WORKER_ENABLED=false \
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  tools/demo_expert_failover.py

DISTRIBUTED_DATABASE_URL=postgresql+asyncpg://postgres@127.0.0.1:55432/postgres \
DISTRIBUTED_REDIS_URL=redis://127.0.0.1:56379/0 \
LLM_PROVIDER=template MEMORY_RETRIEVAL_MODE=lexical MEMORY_WORKER_ENABLED=false \
/Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  tools/benchmark_expert_plane.py --requests 30 --concurrency 4
```

两条命令均 exit 0。原始 JSON 逐字保留：

| 命令 | 实际证据 | 结果 |
| --- | --- | --- |
| 强杀专家后接管 | [demo JSON](demo-startup-final.json) | token 1→2；1 accepted；1 lease_expired rejected；parent result 为 null；学习存储前后摘要一致 |
| template 基准 | [benchmark JSON](benchmark-startup-final.json) | 30 请求、3 warmup、并发 4；errors=0；queue peak=30 |

基准 p95：enqueue-to-start 349.034ms，端到端 433.308ms；
吞吐 50.362 requests/s，owner lock 代理值 0.026383s。
这是本机此次 template 控制面测量，不代表远程模型容量或完整父业务执行。
两份 JSON 均报告 provider_request_count=0、cost_status=unknown、
estimated_cost_usd=null；没有真实模型调用或模型表现提升证据。
被强杀的 attempt 仍保留 unknown usage，不能把未知费用改成零。

两份 JSON 的 `working_tree` 均为 dirty，diff SHA-256 为
`c771c252dc0144fa4d27a774c1e13144e9f48cf294a8734a68b9e2504517fed3`。
该值对应实际执行时尚未提交的三文件修复，不宣称是已提交 HEAD 实跑；
随后新增的 README、报告及 Task8 文件不属于该执行摘要。
执行源码和原始结果的 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| tools/demo_expert_failover.py | 84a1c95bed643435631aa0f0b0ee43d835e32a88696f4b41fb537bbe306b5b61 |
| tools/benchmark_expert_plane.py | 6fa984a398f59be50320dd11a5bcccd0b37593d19eee6e7b9f08b29274e8c02b |
| tools/expert_plane_support.py | 5eb501b1b5d067dcb340a82c390c67f46bc87c2dc0874b7a3030dfe2c7b49df6 |
| demo-startup-final.json | 80ca668824322bf4ced09711ce448e3c0e6733704cda0eae6cf92a2a0842a2d8 |
| benchmark-startup-final.json | 93d15b1ca5cf8895d6604c9053a79e6f39965a2e0ffba4af03a9e78a04e03606 |

完成后查询 PostgreSQL catalog，无 `eduagent_expert_%` 数据库残留；
脚本 `finally` 清理工作进程/任务、专用 Redis stream、连接及临时目录。
`git diff --check` 通过。此次直接执行 README 两条真实基础设施命令，
不将此前后端 1,290 项通过归为此次新测试结果。

## 独立审查

新只读审查代理检查最终三文件 diff、隔离数据库、完整迁移、固定字段继承、
清理和最终 JSON，结论 **PASS，无 blocking P1/P2**。
审查指出 README 原裸命令依赖解释器、URL 与数据库创建权限；现已明确这些
前提，并保留端口替换说明。本证据为 template 工程验证，
`evidence_role=development_validation`、`release_eligible=false`，
不能替代 Judge v3 正式资格、真实模型演练或教学效果实验。
