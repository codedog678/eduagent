# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: spec-health.spec.ts >> production correct health binding metrics_shadow_unknown_counter
- Location: live-e2e/spec-health.spec.ts:14:1

# Error details

```
Error: authority-rejected metric leaf must not become green Ops evidence

expect(received).toEqual(expected) // deep equality

- Expected  - 1
+ Received  + 3

- Array []
+ Array [
+   "shadow_health",
+ ]
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - link "EduAgent Ops 首页" [ref=e5] [cursor=pointer]:
      - /url: "#/runs"
      - generic [ref=e9]:
        - strong [ref=e10]: EduAgent Ops
        - generic [ref=e11]: 只读运行面板
    - navigation "Ops 导航" [ref=e12]:
      - link "Runs" [ref=e13] [cursor=pointer]:
        - /url: "#/runs"
      - link "Trace" [ref=e16] [cursor=pointer]:
        - /url: "#/runs"
      - link "Workers" [ref=e21] [cursor=pointer]:
        - /url: "#/workers"
      - link "Policies" [ref=e25] [cursor=pointer]:
        - /url: "#/policies"
    - button "锁定控制台并清除会话 token" [ref=e29] [cursor=pointer]:
      - generic [ref=e35]: 锁定
  - main [ref=e36]:
    - generic [ref=e37]:
      - generic [ref=e38]:
        - text: OPERATIONS
        - heading "Policies" [level=1] [ref=e39]
      - generic [ref=e40]: Read only
    - region "Policies 只读证据" [ref=e45]:
      - generic [ref=e46]:
        - generic [ref=e47]:
          - generic [ref=e49] [cursor=pointer]:
            - generic [ref=e50]:
              - generic: 全部环境
              - combobox "策略环境" [ref=e51]
            - img "down" [ref=e53]
          - generic [ref=e57] [cursor=pointer]:
            - generic [ref=e58]:
              - generic: 全部状态
              - combobox "策略状态" [ref=e59]
            - img "down" [ref=e61]
          - button "重置" [ref=e65] [cursor=pointer]
        - button "刷新" [ref=e71] [cursor=pointer]
      - generic [ref=e79]:
        - tablist [ref=e80]:
          - generic [ref=e82]:
            - tab "部署" [selected] [ref=e84] [cursor=pointer]
            - tab "健康窗口" [ref=e86] [cursor=pointer]
            - tab "审计时间线" [ref=e88] [cursor=pointer]
        - generic:
          - generic:
            - tabpanel "部署"
      - region "策略证据列表" [ref=e89]:
        - table [ref=e96]:
          - rowgroup [ref=e106]:
            - row [ref=e107]:
              - columnheader "Deployment" [ref=e108]
              - columnheader "环境 / 版本" [ref=e109]
              - columnheader "状态" [ref=e110]
              - columnheader "当前部署" [ref=e111]
              - columnheader "Stable / Candidate" [ref=e112]
              - columnheader "Candidate 流量" [ref=e113]
              - columnheader "Cohort 运行数" [ref=e114]
              - columnheader "创建时间" [ref=e115]
          - rowgroup [ref=e116]:
            - row [ref=e117]:
              - cell [ref=e118]:
                - link "查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62" [ref=e119] [cursor=pointer]:
                  - /url: "#/policies/3ccf6ab5-8591-4194-984c-e6aaa8922d62"
                  - code [ref=e120]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
              - cell "rehearsal 版本 4" [ref=e121]:
                - generic [ref=e122]:
                  - generic [ref=e123]: rehearsal
                  - strong [ref=e124]: 版本 4
              - cell "shadow" [ref=e125]
              - cell "current 当前版本 4" [ref=e130]:
                - generic [ref=e131]:
                  - generic [ref=e132]: current
                  - generic [ref=e133]: 当前版本 4
              - cell [ref=e134]:
                - generic [ref=e135]:
                  - code [ref=e136]: S 778de32838c9
                  - code [ref=e137]: C 2537b3d6216e
              - cell "0%" [ref=e138]
              - cell "S 0 · C 0 · Shadow 0" [ref=e139]
              - cell "2026/11/2 07:39:09" [ref=e140]
            - row [ref=e141]:
              - cell [ref=e142]:
                - link "查看策略 c16dbb3d-f5a7-4af7-94f1-46e3521b5ddc" [ref=e143] [cursor=pointer]:
                  - /url: "#/policies/c16dbb3d-f5a7-4af7-94f1-46e3521b5ddc"
                  - code [ref=e144]: c16dbb3d-f5a7-4af7-94f1-46e3521b5ddc
              - cell "rehearsal 版本 3" [ref=e145]:
                - generic [ref=e146]:
                  - generic [ref=e147]: rehearsal
                  - strong [ref=e148]: 版本 3
              - cell "registered" [ref=e149]
              - cell "historical 当前版本 4" [ref=e154]:
                - generic [ref=e155]:
                  - generic [ref=e156]: historical
                  - generic [ref=e157]: 当前版本 4
              - cell [ref=e158]:
                - generic [ref=e159]:
                  - code [ref=e160]: S 778de32838c9
                  - code [ref=e161]: C 2537b3d6216e
              - cell "0%" [ref=e162]
              - cell "S 0 · C 0 · Shadow 0" [ref=e163]
              - cell "2026/11/2 07:39:09" [ref=e164]
            - row [ref=e165]:
              - cell [ref=e166]:
                - link "查看策略 00000000-0000-0000-0000-000000000002" [ref=e167] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                  - code [ref=e168]: 00000000-0000-0000-0000-000000000002
              - cell "rehearsal 版本 1" [ref=e169]:
                - generic [ref=e170]:
                  - generic [ref=e171]: rehearsal
                  - strong [ref=e172]: 版本 1
              - cell "registered" [ref=e173]
              - cell "historical 当前版本 4" [ref=e178]:
                - generic [ref=e179]:
                  - generic [ref=e180]: historical
                  - generic [ref=e181]: 当前版本 4
              - cell [ref=e182]:
                - generic [ref=e183]:
                  - code [ref=e184]: S 778de32838c9
                  - code [ref=e185]: C 不可用
              - cell "0%" [ref=e186]
              - cell "S 0 · C 0 · Shadow 0" [ref=e187]
              - cell "2026/11/2 07:39:09" [ref=e188]
            - row [ref=e189]:
              - cell [ref=e190]:
                - link "查看策略 00000000-0000-0000-0000-000000000001" [ref=e191] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                  - code [ref=e192]: 00000000-0000-0000-0000-000000000001
              - cell "production 版本 1" [ref=e193]:
                - generic [ref=e194]:
                  - generic [ref=e195]: production
                  - strong [ref=e196]: 版本 1
              - cell "registered" [ref=e197]
              - cell "current 当前版本 1" [ref=e202]:
                - generic [ref=e203]:
                  - generic [ref=e204]: current
                  - generic [ref=e205]: 当前版本 1
              - cell [ref=e206]:
                - generic [ref=e207]:
                  - code [ref=e208]: S 778de32838c9
                  - code [ref=e209]: C 不可用
              - cell "0%" [ref=e210]
              - cell "S 21 · C 0 · Shadow 0" [ref=e211]
              - cell "2026/11/2 07:39:09" [ref=e212]
            - row [ref=e213]:
              - cell [ref=e214]:
                - link "查看策略 1fa57fbb-41ea-4a5e-a032-b55dc8564aaf" [ref=e215] [cursor=pointer]:
                  - /url: "#/policies/1fa57fbb-41ea-4a5e-a032-b55dc8564aaf"
                  - code [ref=e216]: 1fa57fbb-41ea-4a5e-a032-b55dc8564aaf
              - cell "rehearsal 版本 2" [ref=e217]:
                - generic [ref=e218]:
                  - generic [ref=e219]: rehearsal
                  - strong [ref=e220]: 版本 2
              - cell "canary" [ref=e221]
              - cell "historical 当前版本 4" [ref=e226]:
                - generic [ref=e227]:
                  - generic [ref=e228]: historical
                  - generic [ref=e229]: 当前版本 4
              - cell [ref=e230]:
                - generic [ref=e231]:
                  - code [ref=e232]: S 778de32838c9
                  - code [ref=e233]: C f6a0a8ebd8ff
              - cell "50%" [ref=e234]
              - cell "S 0 · C 0 · Shadow 0" [ref=e235]
              - cell "2026/11/1 00:00:00" [ref=e236]
      - generic "Policies 游标分页" [ref=e237]:
        - button "上一页" [disabled] [ref=e238]
        - generic [ref=e239]: 第 1 页
        - button "下一页" [disabled] [ref=e240]
      - region "策略版本详情" [ref=e241]:
        - generic [ref=e242]:
          - heading "策略版本详情" [level=3] [ref=e243]
          - link "关闭详情" [ref=e244] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e247]:
          - rowgroup [ref=e248]:
            - row [ref=e249]:
              - rowheader "Deployment" [ref=e250]
              - cell [ref=e251]:
                - code [ref=e253]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
            - row [ref=e254]:
              - rowheader "环境 / 版本" [ref=e255]
              - cell [ref=e256]:
                - generic [ref=e257]:
                  - text: rehearsal · 版本 4
                  - generic [ref=e258]: shadow
            - row [ref=e262]:
              - rowheader "当前部署" [ref=e263]
              - cell [ref=e264]:
                - generic [ref=e265]:
                  - link "查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62" [ref=e266] [cursor=pointer]:
                    - /url: "#/policies/3ccf6ab5-8591-4194-984c-e6aaa8922d62"
                    - code [ref=e267]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
                  - text: · 当前版本 4
            - row [ref=e268]:
              - rowheader "Stable hash" [ref=e269]
              - cell [ref=e270]:
                - code [ref=e272]: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
            - row [ref=e273]:
              - rowheader "Candidate hash" [ref=e274]
              - cell [ref=e275]:
                - code [ref=e277]: 2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76
            - row [ref=e278]:
              - rowheader "流量 / Cohort" [ref=e279]
              - cell "0% candidate · Stable 0 / Candidate 0 / Shadow 0" [ref=e280]
            - row [ref=e282]:
              - rowheader "Actor / Reason" [ref=e283]
              - cell "redacted / redacted" [ref=e284]
            - row [ref=e286]:
              - rowheader "创建" [ref=e287]
              - cell "2026/11/2 07:39:09" [ref=e288]
        - paragraph [ref=e289]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e290]
        - generic [ref=e291]:
          - generic [ref=e292]:
            - term [ref=e293]: candidate_min_runs
            - definition [ref=e294]: "20"
          - generic [ref=e295]:
            - term [ref=e296]: stable_min_runs
            - definition [ref=e297]: "20"
          - generic [ref=e298]:
            - term [ref=e299]: window_max_runs
            - definition [ref=e300]: "50"
          - generic [ref=e301]:
            - term [ref=e302]: commit_failure_rate
            - definition [ref=e303]: "0.05"
          - generic [ref=e304]:
            - term [ref=e305]: terminal_failure_rate
            - definition [ref=e306]: "0.10"
          - generic [ref=e307]:
            - term [ref=e308]: latency_increase_rate
            - definition [ref=e309]: "0.50"
          - generic [ref=e310]:
            - term [ref=e311]: mean_cost_increase_rate
            - definition [ref=e312]: "0.30"
          - generic [ref=e313]:
            - term [ref=e314]: unknown_rate
            - definition [ref=e315]: "0.10"
          - generic [ref=e316]:
            - term [ref=e317]: relative_epsilon
            - definition [ref=e318]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e319]
        - paragraph [ref=e320]: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
        - generic [ref=e321]:
          - generic [ref=e322]:
            - text: campaign_eligibility
            - generic [ref=e323]: passed
          - generic [ref=e327]:
            - text: formal_holdout
            - generic [ref=e328]: passed
          - generic [ref=e332]:
            - text: harness_qualification
            - generic [ref=e333]: passed
          - generic [ref=e337]:
            - text: judge_calibration
            - generic [ref=e338]: passed
        - table [ref=e348]:
          - rowgroup [ref=e357]:
            - row [ref=e358]:
              - columnheader "Gate" [ref=e359]
              - columnheader "状态" [ref=e360]
              - columnheader "健康来源" [ref=e361]
              - columnheader "样本" [ref=e362]
              - columnheader "成本 USD" [ref=e363]
              - columnheader "Issuer" [ref=e364]
              - columnheader "签发时间" [ref=e365]
          - rowgroup [ref=e366]:
            - row [ref=e367]:
              - cell "campaign_eligibility" [ref=e368]
              - cell "passed" [ref=e369]
              - cell "artifact 资格证据" [ref=e374]
              - cell "21" [ref=e375]
              - cell "1.25000000" [ref=e376]
              - cell "redacted" [ref=e377]
              - cell "2026/10/30 08:00:01" [ref=e378]
            - row [ref=e379]:
              - cell "formal_holdout" [ref=e380]
              - cell "passed" [ref=e381]
              - cell "artifact 资格证据" [ref=e386]
              - cell "23" [ref=e387]
              - cell "1.25000000" [ref=e388]
              - cell "redacted" [ref=e389]
              - cell "2026/10/30 08:00:03" [ref=e390]
            - row [ref=e391]:
              - cell "harness_qualification" [ref=e392]
              - cell "passed" [ref=e393]
              - cell "artifact 资格证据" [ref=e398]
              - cell "24" [ref=e399]
              - cell "1.25000000" [ref=e400]
              - cell "redacted" [ref=e401]
              - cell "2026/10/30 08:00:04" [ref=e402]
            - row [ref=e403]:
              - cell "judge_calibration" [ref=e404]
              - cell "passed" [ref=e405]
              - cell "artifact 资格证据" [ref=e410]
              - cell "22" [ref=e411]
              - cell "1.25000000" [ref=e412]
              - cell "redacted" [ref=e413]
              - cell "2026/10/30 08:00:02" [ref=e414]
            - row [ref=e415]:
              - cell "shadow_health" [ref=e416]
              - cell "passed" [ref=e417]
              - cell "本部署窗口 查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62 版本 4 · pass · 来源最新窗口 Window 82754dc65ec06e5aebab43e1851dcf8173fa2ef0495009a1fb7fbec4aa9f7686 2026/11/2 07:39:09" [ref=e422]:
                - generic [ref=e423]:
                  - strong [ref=e424]: 本部署窗口
                  - link "查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62" [ref=e425] [cursor=pointer]:
                    - /url: "#/policies/3ccf6ab5-8591-4194-984c-e6aaa8922d62"
                    - code [ref=e426]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
                  - generic [ref=e427]: 版本 4 · pass · 来源最新窗口
                  - code [ref=e428]: Window 82754dc65ec06e5aebab43e1851dcf8173fa2ef0495009a1fb7fbec4aa9f7686
                  - generic [ref=e429]: 2026/11/2 07:39:09
              - cell "20" [ref=e430]
              - cell "0.40000000" [ref=e431]
              - cell "redacted" [ref=e432]
              - cell "2026/11/2 07:39:09" [ref=e433]
        - heading "最新健康窗口" [level=3] [ref=e434]
        - paragraph [ref=e435]:
          - generic [ref=e436]: pass
          - text: 2026/11/2 07:39:09 · 指标协议 v1
        - paragraph [ref=e440]: 触发阈值：无。未知指标保持未知，不作为零值。
        - table [ref=e447]:
          - rowgroup [ref=e452]:
            - row [ref=e453]:
              - columnheader "指标" [ref=e454]
              - columnheader "Candidate" [ref=e455]
              - columnheader "Stable" [ref=e456]
          - rowgroup [ref=e457]:
            - row [ref=e458]:
              - cell "run_count" [ref=e459]
              - cell "20" [ref=e460]
              - cell "20" [ref=e461]
            - row [ref=e462]:
              - cell "commit_failure_rate" [ref=e463]
              - cell "0" [ref=e464]
              - cell "0" [ref=e465]
            - row [ref=e466]:
              - cell "terminal_failure_rate" [ref=e467]
              - cell "0" [ref=e468]
              - cell "0" [ref=e469]
            - row [ref=e470]:
              - cell "p95_latency" [ref=e471]
              - cell "1.000000" [ref=e472]
              - cell "1.000000" [ref=e473]
            - row [ref=e474]:
              - cell "mean_cost" [ref=e475]
              - cell "0.01000000" [ref=e476]
              - cell "0.01000000" [ref=e477]
            - row [ref=e478]:
              - cell "structured_decision_count" [ref=e479]
              - cell "200" [ref=e480]
              - cell "200" [ref=e481]
            - row [ref=e482]:
              - cell "unknown_decision_count" [ref=e483]
              - cell "0" [ref=e484]
              - cell "0" [ref=e485]
            - row [ref=e486]:
              - cell "unknown_rate" [ref=e487]
              - cell "0" [ref=e488]
              - cell "0" [ref=e489]
            - row [ref=e490]:
              - cell "fault_injected_count" [ref=e491]
              - cell "0" [ref=e492]
              - cell "0" [ref=e493]
            - row [ref=e494]:
              - cell "injected_commit_failure_count" [ref=e495]
              - cell "0" [ref=e496]
              - cell "0" [ref=e497]
            - row [ref=e498]:
              - cell "natural_failure_count" [ref=e499]
              - cell "0" [ref=e500]
              - cell "0" [ref=e501]
            - row [ref=e502]:
              - cell "latency_increase_rate" [ref=e503]
              - cell "0" [ref=e504]
              - cell "未知" [ref=e505]
            - row [ref=e506]:
              - cell "mean_cost_increase_rate" [ref=e507]
              - cell "0" [ref=e508]
              - cell "未知" [ref=e509]
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e510]
        - list [ref=e511]:
          - listitem [ref=e512]:
            - generic [ref=e520]:
              - strong [ref=e521]: promotion_transitioned
              - generic [ref=e522]: registered → shadow
              - generic [ref=e523]: 2026/11/2 07:39:09 · rehearsal
              - link "查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62" [ref=e524] [cursor=pointer]:
                - /url: "#/policies/3ccf6ab5-8591-4194-984c-e6aaa8922d62"
                - code [ref=e525]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
              - generic [ref=e526]: "actor: redacted · reason: redacted"
        - paragraph [ref=e527]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
  2   | import { readFileSync, writeFileSync } from 'node:fs'
  3   | import { createHash } from 'node:crypto'
  4   | import { join } from 'node:path'
  5   | 
  6   | const own = '/tmp/m3-task9-whole-code-e8c530ed-1f7b-4826-85cc-098395a0c814'
  7   | const scenario = process.env.SPEC_SCENARIO!
  8   | const historical = scenario.startsWith('history')
  9   | const validChain = scenario === 'genuine_valid' || scenario === 'leaf_active_valid'
  10  | const validLocal = scenario === 'leaf_local_valid' || scenario === 'leaf_shadow_valid'
  11  | const tag = process.env.SPEC_RUN_TAG || scenario
  12  | const fixture = JSON.parse(readFileSync(join(own, `live-fixture-${tag}.json`), 'utf8'))
  13  | 
  14  | test(`production correct health binding ${scenario}`, async ({ page, request }, info) => {
  15  |   const requests: { method: string; url: string }[] = []
  16  |   const errors: string[] = []
  17  |   page.on('request', r => requests.push({ method: r.method(), url: r.url() }))
  18  |   page.on('pageerror', e => errors.push(e.message))
  19  |   page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  20  |   const response = await request.get(`/ops-api/ops/policies/deployments/${fixture.id}`)
  21  |   expect(response.status()).toBe(200)
  22  |   const body = await response.json()
  23  |   await page.goto(`/ops/#/policies/${fixture.id}`)
  24  |   const detail = page.getByRole('region', { name: '策略版本详情' })
  25  |   await expect(detail.getByText(fixture.policy_hash, { exact: true }).first()).toBeVisible()
  26  |   await expect(detail.getByText(/收据是历史证据，不代表可发布资格/)).toBeVisible()
  27  |   const sourceText = await detail.locator('strong').allTextContents()
  28  |   const source = detail.getByText(historical
  29  |     ? '本部署窗口'
  30  |     : '已消费前序证据（非本部署新观测）', { exact: true }).first()
  31  |   if (historical || validChain || validLocal) {
  32  |     const visibleSource = validLocal ? detail.getByText('本部署窗口', { exact: true }).first() : source
  33  |     await expect(visibleSource).toBeVisible()
  34  |     await visibleSource.scrollIntoViewIfNeeded()
  35  |     const box = await visibleSource.boundingBox()
  36  |     expect(box).not.toBeNull()
  37  |     expect(box!.x).toBeGreaterThanOrEqual(0)
  38  |     expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  39  |     await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
  40  |       animations: 'disabled' })
  41  |   }
  42  |   await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
  43  |     animations: 'disabled' })
  44  |   const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  45  |   const scrollBefore = await detail.locator('.ant-table-content').evaluateAll(
  46  |     els => els.map(el => ({ left: el.scrollLeft, width: el.clientWidth, fullWidth: el.scrollWidth })))
  47  |   if (info.project.name === 'mobile') {
  48  |     const table = detail.locator('.ant-table-content').first()
  49  |     expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
  50  |     await table.hover()
  51  |     await page.mouse.wheel(1100, 0)
  52  |     await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(scrollBefore[0].left)
  53  |   }
  54  |   const hashes: Record<string, string> = {}
  55  |   const assetEvidence: { url: string; bytes: number; sha256: string; status: number }[] = []
  56  |   for (const url of [...new Set(requests.map(r => r.url).filter(u => /\/assets\/.*\.(css|js)$/.test(u)))]) {
  57  |     const asset = await request.get(url)
  58  |     const bytes = await asset.body()
  59  |     expect(bytes.equals(readFileSync(join(own, 'frontend/dist', new URL(url).pathname)))).toBe(true)
  60  |     hashes[url] = createHash('sha256').update(bytes).digest('hex')
  61  |     assetEvidence.push({ url, bytes: bytes.length, sha256: hashes[url], status: asset.status() })
  62  |   }
  63  |   expect(Object.keys(hashes).length).toBeGreaterThan(0)
  64  |   expect(requests.every(r => r.method === 'GET')).toBe(true)
  65  |   expect(errors).toEqual([])
  66  |   expect(overflow).toBeLessThanOrEqual(1)
  67  |   await page.screenshot({ path: `${own}/screenshots/production-${tag}-${info.project.name}.png`,
  68  |     fullPage: true, animations: 'disabled' })
  69  |   await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}.png`,
  70  |     animations: 'disabled' })
  71  |   writeFileSync(`${own}/production-${tag}-${info.project.name}.json`,
  72  |     JSON.stringify({ scenario, body, sourceText, requests, errors, overflow, hashes,
  73  |       assetEvidence, scrollBefore,
  74  |       scrollAfter: await detail.locator('.ant-table-content').evaluateAll(
  75  |         els => els.map(el => ({ left: el.scrollLeft, width: el.clientWidth, fullWidth: el.scrollWidth }))),
  76  |       requestContext: { detailGet: response.status(), assetGets: assetEvidence.length },
  77  |       viewport: page.viewportSize(),
  78  |     }, null, 2) + '\n')
  79  |   const health = body.gate_receipts.filter((r: { health_source: unknown }) => r.health_source)
  80  |   if (scenario === 'current') {
  81  |     expect(body.is_current).toBe(true)
  82  |     expect(body.latest_health_window.decision).toBe('hold')
  83  |     expect(health).toEqual([])
  84  |     await expect(detail.getByText('passed', { exact: true })).toHaveCount(0)
  85  |   } else if (historical) {
  86  |     expect(body.is_current).toBe(false)
  87  |     expect(health).toHaveLength(1)
  88  |     expect(health[0].receipt_id).toBe(fixture.old_receipt)
  89  |     expect(health[0].health_source.deployment_id).toBe(fixture.old)
  90  |     expect(health[0].health_source.window_id).toBe(fixture.old_window)
  91  |     const newer = await request.get(`/ops-api/ops/policies/deployments/${fixture.current}`)
  92  |     const newBody = await newer.json()
  93  |     expect(newBody.latest_health_window.decision).toBe('pass')
  94  |     expect(newBody.gate_receipts.find((r: { gate_type: string }) => r.gate_type === 'canary_health').receipt_id)
  95  |       .not.toBe(fixture.old_receipt)
  96  |   } else if (scenario.startsWith('metrics_')) {
  97  |     const valid = scenario === 'metrics_active_valid'
  98  |     expect(fixture.leaf_proof.authority_accepts).toBe(valid)
  99  |     const expected = valid ? ['canary_health', 'shadow_health']
  100 |       : scenario.startsWith('metrics_canary_') ? ['shadow_health'] : []
  101 |     expect(health.map((r: { gate_type: string }) => r.gate_type).sort(),
> 102 |       'authority-rejected metric leaf must not become green Ops evidence').toEqual(expected)
      |                                                                            ^ Error: authority-rejected metric leaf must not become green Ops evidence
  103 |   } else if (scenario.startsWith('leaf_')) {
  104 |     const gate = scenario === 'leaf_shadow_valid' ? 'shadow_health' : 'canary_health'
  105 |     const ownLeaf = health.find((r: { gate_type: string }) => r.gate_type === gate)
  106 |     expect(fixture.leaf_proof.authority_accepts).toBe(validLocal || validChain)
  107 |     if (validLocal || validChain) {
  108 |       expect(ownLeaf.receipt_id).toBe(fixture.leaf_proof.receipt_id)
  109 |       expect(ownLeaf.health_source.relation).toBe(validLocal ? 'local' : 'consumed_chain')
  110 |       expect(health).toHaveLength(scenario === 'leaf_shadow_valid' ? 1 : 2)
  111 |     } else if (scenario === 'leaf_local_bad') {
  112 |       expect(ownLeaf).toBeUndefined()
  113 |       expect(health).toHaveLength(1)
  114 |       expect(health[0].gate_type).toBe('shadow_health')
  115 |       expect(health[0].health_source.relation).toBe('consumed_chain')
  116 |     } else {
  117 |       expect(health).toEqual([])
  118 |       await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  119 |     }
  120 |   } else if (validChain) {
  121 |     expect(health).toHaveLength(2)
  122 |     expect(health.every((r: { status: string; health_source: { relation: string } }) =>
  123 |       r.status === 'passed' && r.health_source.relation === 'consumed_chain')).toBe(true)
  124 |   } else {
  125 |     expect(health, 'invalid latest approval or broken audit must not borrow older green consumption').toEqual([])
  126 |     await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  127 |   }
  128 | })
  129 | 
```