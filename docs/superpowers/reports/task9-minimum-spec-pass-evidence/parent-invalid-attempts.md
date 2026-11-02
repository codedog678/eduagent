父侧辅助核验失败留档（产品测试未失败）：

- Shell 5c3fe8b96c3799b04a0345be289c18ea，exit127：
  使用了不存在的 `/tmp/eduagent-m3-patched-runtime/bin/python3.11.17`。
  实际入口为 bin/python，版本3.11.17；没有安装或改动运行环境。
- Shell 66f48dd0d5699849363dde15e3683037，exit1：
  `assert json.loads(before) == state, label`，`AssertionError: api-final`。
  初始快照仅m3/primary，阶段快照增加execution声明；两树各字段全相同。
  修正为完整before/after字节相等、m3/primary全字段匹配初始快照，
  并核对execution精确内容，不缩减树/index/venv/cache保护范围。

两次均在归档目录创建之前终止，没有替换原始SPEC报告或执行日志。
