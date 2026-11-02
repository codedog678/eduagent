# Task9 恢复实现进度

- [x] 完整读取交接、批准设计、计划全文和失败报告。
- [x] 保存继承补丁/测试原字节，当前两树/source/index/venv/cache 快照。
- [x] 独立核验旧 398 raw + manifest SHA/Gitblob；冻结基线 353 source Gitblob。
- [x] 新 runtime 实际安装并 pip check；实体复制 frontend modules。
- [x] 恢复自有 loopback PG57432/Redis57379；PG socket 路径超长与 Redis PID 就绪读取竞态原样分类。
- [x] BASELINE_REPLAY：new47=16PASS/31FAIL，integrity47=42PASS/5FAIL，metadata17=11PASS/6FAIL，production poison 双视口=0PASS/2FAIL，均有效断言。
- [x] 最终 M3 new47=47PASS；Node20 build PASS（首轮 snapshot 输出失败未执行，v2 实际成功）。
- [ ] 核对最小修复，最终 new/full/API/integrity/metadata/build/UI/6production GREEN。
- [ ] 样本/费用/请求/中断分类、截图人工检查、资源精确清理与前后快照。
- [ ] NEW 产品 freeze、全 source Gitblob、同字节完整报告及新 raw 归档 NEW commit。

本实现者不进行 SPEC/CODE 验收，不启动 Task10/Agent50，不请求真实模型。
旧 dependency audit raw 已丢失，旧 context 不替代本次安装/执行。
