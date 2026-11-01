# M3 修复后离线 Harness 复核

执行时间：`2026-11-01T11:49:32.288416+00:00`。
运行代码：`a4691bf59f684dd4e6c068e60c98989de19f8281`，
当时 HEAD `ad858a2` 仅追加规格复审文档，运行代码与测试未变。

数据角色为 `test_fixture`，`release_eligible=false`；
provider/model 为 `template`，生成模式 `offline_builtin`。
新增外部模型请求 0，新增供应商费用 USD 0，失败 0，中断 0。
内置数据集校验通过，20 个场景全部通过。

```bash
PYTHONPATH="$PWD/python" \
  /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  -m evals.cli validate
PYTHONPATH="$PWD/python" \
  /Users/bytedance/Documents/trae_projects/eduagent/.venv/bin/python \
  -m evals.cli run --suite builtin \
  --output /tmp/eduagent-m3-a4691bf-builtin.json
```

[原始结果](2026-11-01-m3-a4691bf-builtin.json) SHA-256：
`d9e1864bd69ca153c70d7eeebd2c64b9c95b026f0dbb2e6051c7a12a91aa7c38`。
数据摘要：
`e40d50926599ed45202ac02be066b5efe5e65a9c826f355b5d9e964de1312bec`；
配置摘要：
`db0ac02ee6ff48b69ee1434f88c258e283256f182f1863e63ed0b5ca4ac67fa9`。

本次是项目自有的本地规则、执行和证据边界回归，不验证远程模型语义、
工具选择效果、Judge v3 正式资格、Docker/CI 或学生学习效果。
它是完整后端 1400 项矩阵之外的补充入口验证，不替代 Task8 代码审查及 Task9/10。
