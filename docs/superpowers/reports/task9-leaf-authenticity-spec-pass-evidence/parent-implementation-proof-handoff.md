# 新冻结父侧核验与独立复审接续

实际版本：review `9fcd6b62c95fa50e39c1ee264dcefc5574e0f50f`，
product/parent `1b8e4b745126c92cfd56f9f021388dd615d98791`，
product parent `855d5c6660343c24df0bef5ad4cf77160e83c566`。
357 source SHA `14b51acad62316892fb77ab407d00a61bd1eff20352c7c88aff22f635cb6f813`。

父侧两个独立复算脚本及 JSON：

- `/tmp/m3-task9-leaf-authenticity-parent-verify.py`
- `/tmp/m3-task9-leaf-authenticity-parent-verification.json`
- `/tmp/m3-task9-leaf-authenticity-parent-browser-check.py`
- `/tmp/m3-task9-leaf-authenticity-parent-browser-verification.json`

实际复算 6503 当前与 5492 历史 Git blobs；五产品路径、1009 新文档路径正确。
核心 997 payload manifest SHA
`37449214c2bb58d5c4e4119d2b0bda5915b39368e136d35b5fe6c2d6c0b3dfbf`，
payload `c44505192c92ed41c69a6027c4f564af421262ecd6a485f534201d2487e7bb5f`，
报告 `6d623c64406c84a7e20e75bdb9e7746fde1bdf16994a149c38c191d5b17fdbdf`。

28 XML 逐 testcase 复算；full1911/API362 中均包含新增47 GET用例；
30 完整快照字节一致；84 ZIP CRC、2982成员 SHA/事件 JSON、
104实际JS/CSS响应正文、26 production detail JSON与Trace原正文一致。
26记录=24最终合法场景+2无效场景名尝试，不能相加为26最终通过。
156 browser GET与104显式context GET仅已记录范围，全HTTP unknown。
4图实际查看；12 mobile 观察到横滚增量，current metrics捕获未实滚，
不能为该场景授横滚证明。手机Trace图来自frontendfixture，不是PGproduction。

26自有UUID DB已不存在；62584/85/86关闭；共享PG57432/PID16852保留。
runtime58dist/39decl+5floor、两树tracked/index/venv/cache只读核验。
实际secret2values无命中；正常hook2秒timeout不能当完整hook扫描成功。
有效RED7local+5同类Active+33newGET与无效配置/辅助脚本错误均保留。
本人两次辅助读取/断言错误也在JSON，未生成产品失败结论。
模型0、实际模型费用0、全HTTP unknown。

这些是归档来源证明，不能替代独立SPEC/CODE验收。
新独立SPEC已运行：`m3_task9_leaf_authenticity_fresh_wholespec`，
结果待 `/tmp/m3-task9-leaf-authenticity-spec-result.md`。
父侧须核验本人新SPEC完整raw；仅PASS且NEWdocs归档后freshWHOLECODE。
review运行期间禁止移动HEAD，Task10/M1/final仍待Task9验收。
后续SPEC留档时一并保留本页、两个脚本/JSON与无效尝试记录；旧档不可覆盖。
