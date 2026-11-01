# 前端构建链安全与兼容验证

验证日期：2026-11-01。基于 `c3f4bc9`，本次修改仅涉及前端依赖清单、
锁文件和本报告及审计快照；Policies 功能仍需 Task9 单独验收。

此前 `npm ci`、生产构建及现有 Ops 浏览器测试通过，但
[`npm audit` 原始结果](task9-toolchain-audit-before.json)包含 8 项
告警：5 high、2 moderate、1 low。直接依赖 Vite 5.4.21 及其 esbuild
依赖在受影响范围内；其他告警涉及 Babel、browser mapping、
browserslist、nanoid、PostCSS 和 source-map-js。

更新 Vite 到 7.3.7、React 插件到 5.2.0，并通过无 `--force` 的
`npm audit fix` 更新兼容的传递依赖。React 保持 18，现有 Vite 配置与
应用代码未变。Node engines 明确为 `^20.19.0 || >=22.12.0`。

| 验证 | 结果 |
| --- | --- |
| `npm ci` 从锁文件重新安装 | 138 packages 安装完成；0 vulnerabilities |
| `npm audit --json` | [原始结果](task9-toolchain-audit-after.json)：0 high / moderate / low / critical |
| Node 26.5.0，`npm run build` | TypeScript 与 Vite production build 通过 |
| 实际 Node 20.19.5，TypeScript 与 Vite production build | 通过，与 CI / Docker 的 Node 20 主版本兼容 |
| `npx playwright test e2e/ops.spec.ts --reporter=line,junit` | 8 passed，7.5 秒；desktop 4 / mobile 4；0 failure / error / skip |

浏览器用例覆盖分页、Run 与专家详情、Trace、stale worker、loading /
empty、错误重试、会话 token 与鉴权重试。网络响应为浏览器测试 fixture，
不等同于真实基础设施或正式候选发布证据。

复现 Node 20 的构建：

```bash
npm ci
npm exec --yes --package=node@20.19.5 -- node -e '
const {spawnSync}=require("node:child_process");
console.log("Build runtime:",process.version);
for (const file of ["node_modules/typescript/bin/tsc","node_modules/vite/bin/vite.js"]) {
  const result=spawnSync(process.execPath,file.includes("vite")?[file,"build"]:[file],{stdio:"inherit"});
  if(result.status!==0)process.exit(result.status||1);
}'
```

本机未运行 Docker 容器或 GitHub CI。生产构建仍提示一份共享 JS chunk
约 623 kB；构建通过并不证明加载性能最优。审计结论仅针对上述日期与
锁文件，后续依赖更新需重新审计。没有模型请求，也没有新增模型费用。

独立只读审查：**PASS，无 P1/P2/P3**。清单与锁文件一致；187 个 URL /
SRI 及依赖和 peer range 校验通过，34 份本地已有的变动 tarball 的内容
符合锁文件摘要，未下载其他平台的可选包。锁定 Node engines 均接受
20.19.5。CI / Docker 的浮动 Node 20 标签需解析到至少 20.19；
审查未重跑上述构建和浏览器测试，两份原始审计的数量和版本范围另行核对。
