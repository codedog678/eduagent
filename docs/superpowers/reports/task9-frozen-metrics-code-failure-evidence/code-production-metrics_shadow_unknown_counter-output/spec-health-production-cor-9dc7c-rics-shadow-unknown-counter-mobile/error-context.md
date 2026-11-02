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
      - strong [ref=e10]: EduAgent Ops
    - navigation "Ops 导航" [ref=e11]:
      - link "Runs" [ref=e12] [cursor=pointer]:
        - /url: "#/runs"
      - link "Trace" [ref=e15] [cursor=pointer]:
        - /url: "#/runs"
      - link "Workers" [ref=e20] [cursor=pointer]:
        - /url: "#/workers"
      - link "Policies" [ref=e24] [cursor=pointer]:
        - /url: "#/policies"
    - button "锁定控制台并清除会话 token" [ref=e28] [cursor=pointer]:
      - generic [ref=e34]: 锁定
  - main [ref=e35]:
    - generic [ref=e36]:
      - generic [ref=e37]:
        - text: OPERATIONS
        - heading "Policies" [level=1] [ref=e38]
      - generic [ref=e39]: Read only
    - region "Policies 只读证据" [ref=e44]:
      - generic [ref=e45]:
        - generic [ref=e46]:
          - generic [ref=e48] [cursor=pointer]:
            - generic [ref=e49]:
              - generic: 全部环境
              - combobox "策略环境" [ref=e50]
            - img "down" [ref=e52]
          - generic [ref=e56] [cursor=pointer]:
            - generic [ref=e57]:
              - generic: 全部状态
              - combobox "策略状态" [ref=e58]
            - img "down" [ref=e60]
          - button "重置" [ref=e64] [cursor=pointer]
        - button "刷新" [ref=e70] [cursor=pointer]
      - generic [ref=e78]:
        - tablist [ref=e79]:
          - generic [ref=e81]:
            - tab "部署" [selected] [ref=e83] [cursor=pointer]
            - tab "健康窗口" [ref=e85] [cursor=pointer]
            - tab "审计时间线" [ref=e87] [cursor=pointer]
        - generic:
          - generic:
            - tabpanel "部署"
      - region "策略证据列表" [ref=e88]:
        - table [ref=e95]:
          - rowgroup [ref=e105]:
            - row [ref=e106]:
              - columnheader "Deployment" [ref=e107]
              - columnheader "环境 / 版本" [ref=e108]
              - columnheader "状态" [ref=e109]
              - columnheader "当前部署" [ref=e110]
              - columnheader "Stable / Candidate" [ref=e111]
              - columnheader "Candidate 流量" [ref=e112]
              - columnheader "Cohort 运行数" [ref=e113]
              - columnheader "创建时间" [ref=e114]
          - rowgroup [ref=e115]:
            - row [ref=e116]:
              - cell [ref=e117]:
                - link "查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62" [ref=e118] [cursor=pointer]:
                  - /url: "#/policies/3ccf6ab5-8591-4194-984c-e6aaa8922d62"
                  - code [ref=e119]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
              - cell "rehearsal 版本 4" [ref=e120]:
                - generic [ref=e121]:
                  - generic [ref=e122]: rehearsal
                  - strong [ref=e123]: 版本 4
              - cell "shadow" [ref=e124]
              - cell "current 当前版本 4" [ref=e129]:
                - generic [ref=e130]:
                  - generic [ref=e131]: current
                  - generic [ref=e132]: 当前版本 4
              - cell [ref=e133]:
                - generic [ref=e134]:
                  - code [ref=e135]: S 778de32838c9
                  - code [ref=e136]: C 2537b3d6216e
              - cell "0%" [ref=e137]
              - cell "S 0 · C 0 · Shadow 0" [ref=e138]
              - cell "2026/11/2 07:39:09" [ref=e139]
            - row [ref=e140]:
              - cell [ref=e141]:
                - link "查看策略 c16dbb3d-f5a7-4af7-94f1-46e3521b5ddc" [ref=e142] [cursor=pointer]:
                  - /url: "#/policies/c16dbb3d-f5a7-4af7-94f1-46e3521b5ddc"
                  - code [ref=e143]: c16dbb3d-f5a7-4af7-94f1-46e3521b5ddc
              - cell "rehearsal 版本 3" [ref=e144]:
                - generic [ref=e145]:
                  - generic [ref=e146]: rehearsal
                  - strong [ref=e147]: 版本 3
              - cell "registered" [ref=e148]
              - cell "historical 当前版本 4" [ref=e153]:
                - generic [ref=e154]:
                  - generic [ref=e155]: historical
                  - generic [ref=e156]: 当前版本 4
              - cell [ref=e157]:
                - generic [ref=e158]:
                  - code [ref=e159]: S 778de32838c9
                  - code [ref=e160]: C 2537b3d6216e
              - cell "0%" [ref=e161]
              - cell "S 0 · C 0 · Shadow 0" [ref=e162]
              - cell "2026/11/2 07:39:09" [ref=e163]
            - row [ref=e164]:
              - cell [ref=e165]:
                - link "查看策略 00000000-0000-0000-0000-000000000002" [ref=e166] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                  - code [ref=e167]: 00000000-0000-0000-0000-000000000002
              - cell "rehearsal 版本 1" [ref=e168]:
                - generic [ref=e169]:
                  - generic [ref=e170]: rehearsal
                  - strong [ref=e171]: 版本 1
              - cell "registered" [ref=e172]
              - cell "historical 当前版本 4" [ref=e177]:
                - generic [ref=e178]:
                  - generic [ref=e179]: historical
                  - generic [ref=e180]: 当前版本 4
              - cell [ref=e181]:
                - generic [ref=e182]:
                  - code [ref=e183]: S 778de32838c9
                  - code [ref=e184]: C 不可用
              - cell "0%" [ref=e185]
              - cell "S 0 · C 0 · Shadow 0" [ref=e186]
              - cell "2026/11/2 07:39:09" [ref=e187]
            - row [ref=e188]:
              - cell [ref=e189]:
                - link "查看策略 00000000-0000-0000-0000-000000000001" [ref=e190] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                  - code [ref=e191]: 00000000-0000-0000-0000-000000000001
              - cell "production 版本 1" [ref=e192]:
                - generic [ref=e193]:
                  - generic [ref=e194]: production
                  - strong [ref=e195]: 版本 1
              - cell "registered" [ref=e196]
              - cell "current 当前版本 1" [ref=e201]:
                - generic [ref=e202]:
                  - generic [ref=e203]: current
                  - generic [ref=e204]: 当前版本 1
              - cell [ref=e205]:
                - generic [ref=e206]:
                  - code [ref=e207]: S 778de32838c9
                  - code [ref=e208]: C 不可用
              - cell "0%" [ref=e209]
              - cell "S 21 · C 0 · Shadow 0" [ref=e210]
              - cell "2026/11/2 07:39:09" [ref=e211]
            - row [ref=e212]:
              - cell [ref=e213]:
                - link "查看策略 1fa57fbb-41ea-4a5e-a032-b55dc8564aaf" [ref=e214] [cursor=pointer]:
                  - /url: "#/policies/1fa57fbb-41ea-4a5e-a032-b55dc8564aaf"
                  - code [ref=e215]: 1fa57fbb-41ea-4a5e-a032-b55dc8564aaf
              - cell "rehearsal 版本 2" [ref=e216]:
                - generic [ref=e217]:
                  - generic [ref=e218]: rehearsal
                  - strong [ref=e219]: 版本 2
              - cell "canary" [ref=e220]
              - cell "historical 当前版本 4" [ref=e225]:
                - generic [ref=e226]:
                  - generic [ref=e227]: historical
                  - generic [ref=e228]: 当前版本 4
              - cell [ref=e229]:
                - generic [ref=e230]:
                  - code [ref=e231]: S 778de32838c9
                  - code [ref=e232]: C f6a0a8ebd8ff
              - cell "50%" [ref=e233]
              - cell "S 0 · C 0 · Shadow 0" [ref=e234]
              - cell "2026/11/1 00:00:00" [ref=e235]
      - generic "Policies 游标分页" [ref=e236]:
        - button "上一页" [disabled] [ref=e237]
        - generic [ref=e238]: 第 1 页
        - button "下一页" [disabled] [ref=e239]
      - region "策略版本详情" [ref=e240]:
        - generic [ref=e241]:
          - heading "策略版本详情" [level=3] [ref=e242]
          - link "关闭详情" [ref=e243] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e246]:
          - rowgroup [ref=e247]:
            - row [ref=e248]:
              - rowheader "Deployment" [ref=e249]
              - cell [ref=e250]:
                - code [ref=e252]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
            - row [ref=e253]:
              - rowheader "环境 / 版本" [ref=e254]
              - cell [ref=e255]:
                - generic [ref=e256]:
                  - text: rehearsal · 版本 4
                  - generic [ref=e257]: shadow
            - row [ref=e261]:
              - rowheader "当前部署" [ref=e262]
              - cell [ref=e263]:
                - generic [ref=e264]:
                  - link "查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62" [ref=e265] [cursor=pointer]:
                    - /url: "#/policies/3ccf6ab5-8591-4194-984c-e6aaa8922d62"
                    - code [ref=e266]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
                  - text: · 当前版本 4
            - row [ref=e267]:
              - rowheader "Stable hash" [ref=e268]
              - cell [ref=e269]:
                - code [ref=e271]: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
            - row [ref=e272]:
              - rowheader "Candidate hash" [ref=e273]
              - cell [ref=e274]:
                - code [ref=e276]: 2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76
            - row [ref=e277]:
              - rowheader "流量 / Cohort" [ref=e278]
              - cell "0% candidate · Stable 0 / Candidate 0 / Shadow 0" [ref=e279]
            - row [ref=e281]:
              - rowheader "Actor / Reason" [ref=e282]
              - cell "redacted / redacted" [ref=e283]
            - row [ref=e285]:
              - rowheader "创建" [ref=e286]
              - cell "2026/11/2 07:39:09" [ref=e287]
        - paragraph [ref=e288]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e289]
        - generic [ref=e290]:
          - generic [ref=e291]:
            - term [ref=e292]: candidate_min_runs
            - definition [ref=e293]: "20"
          - generic [ref=e294]:
            - term [ref=e295]: stable_min_runs
            - definition [ref=e296]: "20"
          - generic [ref=e297]:
            - term [ref=e298]: window_max_runs
            - definition [ref=e299]: "50"
          - generic [ref=e300]:
            - term [ref=e301]: commit_failure_rate
            - definition [ref=e302]: "0.05"
          - generic [ref=e303]:
            - term [ref=e304]: terminal_failure_rate
            - definition [ref=e305]: "0.10"
          - generic [ref=e306]:
            - term [ref=e307]: latency_increase_rate
            - definition [ref=e308]: "0.50"
          - generic [ref=e309]:
            - term [ref=e310]: mean_cost_increase_rate
            - definition [ref=e311]: "0.30"
          - generic [ref=e312]:
            - term [ref=e313]: unknown_rate
            - definition [ref=e314]: "0.10"
          - generic [ref=e315]:
            - term [ref=e316]: relative_epsilon
            - definition [ref=e317]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e318]
        - paragraph [ref=e319]: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
        - generic [ref=e320]:
          - generic [ref=e321]:
            - text: campaign_eligibility
            - generic [ref=e322]: passed
          - generic [ref=e326]:
            - text: formal_holdout
            - generic [ref=e327]: passed
          - generic [ref=e331]:
            - text: harness_qualification
            - generic [ref=e332]: passed
          - generic [ref=e336]:
            - text: judge_calibration
            - generic [ref=e337]: passed
        - table [ref=e347]:
          - rowgroup [ref=e356]:
            - row [ref=e357]:
              - columnheader "Gate" [ref=e358]
              - columnheader "状态" [ref=e359]
              - columnheader "健康来源" [ref=e360]
              - columnheader "样本" [ref=e361]
              - columnheader "成本 USD" [ref=e362]
              - columnheader "Issuer" [ref=e363]
              - columnheader "签发时间" [ref=e364]
          - rowgroup [ref=e365]:
            - row [ref=e366]:
              - cell "campaign_eligibility" [ref=e367]
              - cell "passed" [ref=e368]
              - cell "artifact 资格证据" [ref=e373]
              - cell "21" [ref=e374]
              - cell "1.25000000" [ref=e375]
              - cell "redacted" [ref=e376]
              - cell "2026/10/30 08:00:01" [ref=e377]
            - row [ref=e378]:
              - cell "formal_holdout" [ref=e379]
              - cell "passed" [ref=e380]
              - cell "artifact 资格证据" [ref=e385]
              - cell "23" [ref=e386]
              - cell "1.25000000" [ref=e387]
              - cell "redacted" [ref=e388]
              - cell "2026/10/30 08:00:03" [ref=e389]
            - row [ref=e390]:
              - cell "harness_qualification" [ref=e391]
              - cell "passed" [ref=e392]
              - cell "artifact 资格证据" [ref=e397]
              - cell "24" [ref=e398]
              - cell "1.25000000" [ref=e399]
              - cell "redacted" [ref=e400]
              - cell "2026/10/30 08:00:04" [ref=e401]
            - row [ref=e402]:
              - cell "judge_calibration" [ref=e403]
              - cell "passed" [ref=e404]
              - cell "artifact 资格证据" [ref=e409]
              - cell "22" [ref=e410]
              - cell "1.25000000" [ref=e411]
              - cell "redacted" [ref=e412]
              - cell "2026/10/30 08:00:02" [ref=e413]
            - row [ref=e414]:
              - cell "shadow_health" [ref=e415]
              - cell "passed" [ref=e416]
              - cell "本部署窗口 查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62 版本 4 · pass · 来源最新窗口 Window 82754dc65ec06e5aebab43e1851dcf8173fa2ef0495009a1fb7fbec4aa9f7686 2026/11/2 07:39:09" [ref=e421]:
                - generic [ref=e422]:
                  - strong [ref=e423]: 本部署窗口
                  - link "查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62" [ref=e424] [cursor=pointer]:
                    - /url: "#/policies/3ccf6ab5-8591-4194-984c-e6aaa8922d62"
                    - code [ref=e425]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
                  - generic [ref=e426]: 版本 4 · pass · 来源最新窗口
                  - code [ref=e427]: Window 82754dc65ec06e5aebab43e1851dcf8173fa2ef0495009a1fb7fbec4aa9f7686
                  - generic [ref=e428]: 2026/11/2 07:39:09
              - cell "20" [ref=e429]
              - cell "0.40000000" [ref=e430]
              - cell "redacted" [ref=e431]
              - cell "2026/11/2 07:39:09" [ref=e432]
        - heading "最新健康窗口" [level=3] [ref=e433]
        - paragraph [ref=e434]:
          - generic [ref=e435]: pass
          - text: 2026/11/2 07:39:09 · 指标协议 v1
        - paragraph [ref=e439]: 触发阈值：无。未知指标保持未知，不作为零值。
        - table [ref=e446]:
          - rowgroup [ref=e451]:
            - row [ref=e452]:
              - columnheader "指标" [ref=e453]
              - columnheader "Candidate" [ref=e454]
              - columnheader "Stable" [ref=e455]
          - rowgroup [ref=e456]:
            - row [ref=e457]:
              - cell "run_count" [ref=e458]
              - cell "20" [ref=e459]
              - cell "20" [ref=e460]
            - row [ref=e461]:
              - cell "commit_failure_rate" [ref=e462]
              - cell "0" [ref=e463]
              - cell "0" [ref=e464]
            - row [ref=e465]:
              - cell "terminal_failure_rate" [ref=e466]
              - cell "0" [ref=e467]
              - cell "0" [ref=e468]
            - row [ref=e469]:
              - cell "p95_latency" [ref=e470]
              - cell "1.000000" [ref=e471]
              - cell "1.000000" [ref=e472]
            - row [ref=e473]:
              - cell "mean_cost" [ref=e474]
              - cell "0.01000000" [ref=e475]
              - cell "0.01000000" [ref=e476]
            - row [ref=e477]:
              - cell "structured_decision_count" [ref=e478]
              - cell "200" [ref=e479]
              - cell "200" [ref=e480]
            - row [ref=e481]:
              - cell "unknown_decision_count" [ref=e482]
              - cell "0" [ref=e483]
              - cell "0" [ref=e484]
            - row [ref=e485]:
              - cell "unknown_rate" [ref=e486]
              - cell "0" [ref=e487]
              - cell "0" [ref=e488]
            - row [ref=e489]:
              - cell "fault_injected_count" [ref=e490]
              - cell "0" [ref=e491]
              - cell "0" [ref=e492]
            - row [ref=e493]:
              - cell "injected_commit_failure_count" [ref=e494]
              - cell "0" [ref=e495]
              - cell "0" [ref=e496]
            - row [ref=e497]:
              - cell "natural_failure_count" [ref=e498]
              - cell "0" [ref=e499]
              - cell "0" [ref=e500]
            - row [ref=e501]:
              - cell "latency_increase_rate" [ref=e502]
              - cell "0" [ref=e503]
              - cell "未知" [ref=e504]
            - row [ref=e505]:
              - cell "mean_cost_increase_rate" [ref=e506]
              - cell "0" [ref=e507]
              - cell "未知" [ref=e508]
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e509]
        - list [ref=e510]:
          - listitem [ref=e511]:
            - generic [ref=e519]:
              - strong [ref=e520]: promotion_transitioned
              - generic [ref=e521]: registered → shadow
              - generic [ref=e522]: 2026/11/2 07:39:09 · rehearsal
              - link "查看策略 3ccf6ab5-8591-4194-984c-e6aaa8922d62" [ref=e523] [cursor=pointer]:
                - /url: "#/policies/3ccf6ab5-8591-4194-984c-e6aaa8922d62"
                - code [ref=e524]: 3ccf6ab5-8591-4194-984c-e6aaa8922d62
              - generic [ref=e525]: "actor: redacted · reason: redacted"
        - paragraph [ref=e526]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
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