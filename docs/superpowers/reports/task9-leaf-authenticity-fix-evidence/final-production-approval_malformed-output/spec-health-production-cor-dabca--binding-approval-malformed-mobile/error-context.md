# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: spec-health.spec.ts >> production correct health binding approval_malformed
- Location: live-e2e/spec-health.spec.ts:14:1

# Error details

```
Error: invalid latest approval or broken audit must not borrow older green consumption

expect(received).toEqual(expected) // deep equality

- Expected  -  1
+ Received  + 44

- Array []
+ Array [
+   Object {
+     "cost": "0.40000000",
+     "evidence_hash": "df220b649aba7ff4439fb5559daf90db38b1d3a2c937a067669381d7653c91f7",
+     "gate_type": "canary_health",
+     "health_source": Object {
+       "deployment_id": "297e333a-2ed7-48c1-bd05-826ae1606e38",
+       "deployment_version": 5,
+       "evaluated_at": "2026-11-02T06:21:05.397588Z",
+       "is_latest_window": true,
+       "relation": "consumed_chain",
+       "thresholds_hash": "35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f",
+       "window_decision": "pass",
+       "window_id": "a16384e7411cff9c5d0d88de8106a561ecea06568d5969a4381cf09bb3f8c3f2",
+     },
+     "issued_at": "2026-11-02T06:21:05.397588Z",
+     "issuer": "redacted",
+     "policy_hash": "2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76",
+     "receipt_id": "26f116c3-d12a-4521-80b5-d84acd772e90",
+     "sample_count": 20,
+     "status": "passed",
+   },
+   Object {
+     "cost": "0.40000000",
+     "evidence_hash": "935e0fba6090279dd3cd511853acf4241c63cd93d621547b1dc3d81cf4d81e60",
+     "gate_type": "shadow_health",
+     "health_source": Object {
+       "deployment_id": "4e3e4706-a5d5-4dff-9cde-c51e0ca0da66",
+       "deployment_version": 4,
+       "evaluated_at": "2026-11-02T06:21:05.281617Z",
+       "is_latest_window": true,
+       "relation": "consumed_chain",
+       "thresholds_hash": "35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f",
+       "window_decision": "pass",
+       "window_id": "b9bda59cb4f34b6768230db8a341cfc9566f0271d58cbe81c89a83f3664599a7",
+     },
+     "issued_at": "2026-11-02T06:21:05.281617Z",
+     "issuer": "redacted",
+     "policy_hash": "2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76",
+     "receipt_id": "05e7ba74-7936-46b2-b393-de429d002169",
+     "sample_count": 20,
+     "status": "passed",
+   },
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
                - link "查看策略 d21ce845-a939-4a30-a589-1713e1667512" [ref=e118] [cursor=pointer]:
                  - /url: "#/policies/d21ce845-a939-4a30-a589-1713e1667512"
                  - code [ref=e119]: d21ce845-a939-4a30-a589-1713e1667512
              - cell "rehearsal 版本 6" [ref=e120]:
                - generic [ref=e121]:
                  - generic [ref=e122]: rehearsal
                  - strong [ref=e123]: 版本 6
              - cell "active" [ref=e124]
              - cell "current 当前版本 6" [ref=e129]:
                - generic [ref=e130]:
                  - generic [ref=e131]: current
                  - generic [ref=e132]: 当前版本 6
              - cell [ref=e133]:
                - generic [ref=e134]:
                  - code [ref=e135]: S 778de32838c9
                  - code [ref=e136]: C 2537b3d6216e
              - cell "100%" [ref=e137]
              - cell "S 0 · C 0 · Shadow 0" [ref=e138]
              - cell "2026/11/2 06:21:05" [ref=e139]
            - row [ref=e140]:
              - cell [ref=e141]:
                - link "查看策略 297e333a-2ed7-48c1-bd05-826ae1606e38" [ref=e142] [cursor=pointer]:
                  - /url: "#/policies/297e333a-2ed7-48c1-bd05-826ae1606e38"
                  - code [ref=e143]: 297e333a-2ed7-48c1-bd05-826ae1606e38
              - cell "rehearsal 版本 5" [ref=e144]:
                - generic [ref=e145]:
                  - generic [ref=e146]: rehearsal
                  - strong [ref=e147]: 版本 5
              - cell "canary" [ref=e148]
              - cell "historical 当前版本 6" [ref=e153]:
                - generic [ref=e154]:
                  - generic [ref=e155]: historical
                  - generic [ref=e156]: 当前版本 6
              - cell [ref=e157]:
                - generic [ref=e158]:
                  - code [ref=e159]: S 778de32838c9
                  - code [ref=e160]: C 2537b3d6216e
              - cell "50%" [ref=e161]
              - cell "S 0 · C 0 · Shadow 0" [ref=e162]
              - cell "2026/11/2 06:21:05" [ref=e163]
            - row [ref=e164]:
              - cell [ref=e165]:
                - link "查看策略 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66" [ref=e166] [cursor=pointer]:
                  - /url: "#/policies/4e3e4706-a5d5-4dff-9cde-c51e0ca0da66"
                  - code [ref=e167]: 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66
              - cell "rehearsal 版本 4" [ref=e168]:
                - generic [ref=e169]:
                  - generic [ref=e170]: rehearsal
                  - strong [ref=e171]: 版本 4
              - cell "shadow" [ref=e172]
              - cell "historical 当前版本 6" [ref=e177]:
                - generic [ref=e178]:
                  - generic [ref=e179]: historical
                  - generic [ref=e180]: 当前版本 6
              - cell [ref=e181]:
                - generic [ref=e182]:
                  - code [ref=e183]: S 778de32838c9
                  - code [ref=e184]: C 2537b3d6216e
              - cell "0%" [ref=e185]
              - cell "S 0 · C 0 · Shadow 0" [ref=e186]
              - cell "2026/11/2 06:21:05" [ref=e187]
            - row [ref=e188]:
              - cell [ref=e189]:
                - link "查看策略 3209df6e-86d8-4fa1-b381-026cebd9302e" [ref=e190] [cursor=pointer]:
                  - /url: "#/policies/3209df6e-86d8-4fa1-b381-026cebd9302e"
                  - code [ref=e191]: 3209df6e-86d8-4fa1-b381-026cebd9302e
              - cell "rehearsal 版本 3" [ref=e192]:
                - generic [ref=e193]:
                  - generic [ref=e194]: rehearsal
                  - strong [ref=e195]: 版本 3
              - cell "registered" [ref=e196]
              - cell "historical 当前版本 6" [ref=e201]:
                - generic [ref=e202]:
                  - generic [ref=e203]: historical
                  - generic [ref=e204]: 当前版本 6
              - cell [ref=e205]:
                - generic [ref=e206]:
                  - code [ref=e207]: S 778de32838c9
                  - code [ref=e208]: C 2537b3d6216e
              - cell "0%" [ref=e209]
              - cell "S 0 · C 0 · Shadow 0" [ref=e210]
              - cell "2026/11/2 06:21:05" [ref=e211]
            - row [ref=e212]:
              - cell [ref=e213]:
                - link "查看策略 00000000-0000-0000-0000-000000000002" [ref=e214] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000002"
                  - code [ref=e215]: 00000000-0000-0000-0000-000000000002
              - cell "rehearsal 版本 1" [ref=e216]:
                - generic [ref=e217]:
                  - generic [ref=e218]: rehearsal
                  - strong [ref=e219]: 版本 1
              - cell "registered" [ref=e220]
              - cell "historical 当前版本 6" [ref=e225]:
                - generic [ref=e226]:
                  - generic [ref=e227]: historical
                  - generic [ref=e228]: 当前版本 6
              - cell [ref=e229]:
                - generic [ref=e230]:
                  - code [ref=e231]: S 778de32838c9
                  - code [ref=e232]: C 不可用
              - cell "0%" [ref=e233]
              - cell "S 0 · C 0 · Shadow 0" [ref=e234]
              - cell "2026/11/2 06:21:05" [ref=e235]
            - row [ref=e236]:
              - cell [ref=e237]:
                - link "查看策略 00000000-0000-0000-0000-000000000001" [ref=e238] [cursor=pointer]:
                  - /url: "#/policies/00000000-0000-0000-0000-000000000001"
                  - code [ref=e239]: 00000000-0000-0000-0000-000000000001
              - cell "production 版本 1" [ref=e240]:
                - generic [ref=e241]:
                  - generic [ref=e242]: production
                  - strong [ref=e243]: 版本 1
              - cell "registered" [ref=e244]
              - cell "current 当前版本 1" [ref=e249]:
                - generic [ref=e250]:
                  - generic [ref=e251]: current
                  - generic [ref=e252]: 当前版本 1
              - cell [ref=e253]:
                - generic [ref=e254]:
                  - code [ref=e255]: S 778de32838c9
                  - code [ref=e256]: C 不可用
              - cell "0%" [ref=e257]
              - cell "S 60 · C 0 · Shadow 0" [ref=e258]
              - cell "2026/11/2 06:21:05" [ref=e259]
            - row [ref=e260]:
              - cell [ref=e261]:
                - link "查看策略 ee895571-0ac5-41f9-a73f-cb5360af7252" [ref=e262] [cursor=pointer]:
                  - /url: "#/policies/ee895571-0ac5-41f9-a73f-cb5360af7252"
                  - code [ref=e263]: ee895571-0ac5-41f9-a73f-cb5360af7252
              - cell "rehearsal 版本 2" [ref=e264]:
                - generic [ref=e265]:
                  - generic [ref=e266]: rehearsal
                  - strong [ref=e267]: 版本 2
              - cell "canary" [ref=e268]
              - cell "historical 当前版本 6" [ref=e273]:
                - generic [ref=e274]:
                  - generic [ref=e275]: historical
                  - generic [ref=e276]: 当前版本 6
              - cell [ref=e277]:
                - generic [ref=e278]:
                  - code [ref=e279]: S 778de32838c9
                  - code [ref=e280]: C 97689ad93155
              - cell "50%" [ref=e281]
              - cell "S 0 · C 0 · Shadow 0" [ref=e282]
              - cell "2026/11/1 00:00:00" [ref=e283]
      - generic "Policies 游标分页" [ref=e284]:
        - button "上一页" [disabled] [ref=e285]
        - generic [ref=e286]: 第 1 页
        - button "下一页" [disabled] [ref=e287]
      - region "策略版本详情" [ref=e288]:
        - generic [ref=e289]:
          - heading "策略版本详情" [level=3] [ref=e290]
          - link "关闭详情" [ref=e291] [cursor=pointer]:
            - /url: "#/policies"
        - table [ref=e294]:
          - rowgroup [ref=e295]:
            - row [ref=e296]:
              - rowheader "Deployment" [ref=e297]
              - cell [ref=e298]:
                - code [ref=e300]: d21ce845-a939-4a30-a589-1713e1667512
            - row [ref=e301]:
              - rowheader "环境 / 版本" [ref=e302]
              - cell [ref=e303]:
                - generic [ref=e304]:
                  - text: rehearsal · 版本 6
                  - generic [ref=e305]: active
            - row [ref=e309]:
              - rowheader "当前部署" [ref=e310]
              - cell [ref=e311]:
                - generic [ref=e312]:
                  - link "查看策略 d21ce845-a939-4a30-a589-1713e1667512" [ref=e313] [cursor=pointer]:
                    - /url: "#/policies/d21ce845-a939-4a30-a589-1713e1667512"
                    - code [ref=e314]: d21ce845-a939-4a30-a589-1713e1667512
                  - text: · 当前版本 6
            - row [ref=e315]:
              - rowheader "Stable hash" [ref=e316]
              - cell [ref=e317]:
                - code [ref=e319]: 778de32838c91cc035331681df449ecebdbf06632e4648b0611776a07b2cedc9
            - row [ref=e320]:
              - rowheader "Candidate hash" [ref=e321]
              - cell [ref=e322]:
                - code [ref=e324]: 2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76
            - row [ref=e325]:
              - rowheader "流量 / Cohort" [ref=e326]
              - cell "100% candidate · Stable 0 / Candidate 0 / Shadow 0" [ref=e327]
            - row [ref=e329]:
              - rowheader "Actor / Reason" [ref=e330]
              - cell "redacted / redacted" [ref=e331]
            - row [ref=e333]:
              - rowheader "创建" [ref=e334]
              - cell "2026/11/2 06:21:05" [ref=e335]
        - paragraph [ref=e336]: Actor 和 reason 原文已隐藏；通过事件类型、触发阈值和版本时间关联回滚事实。历史运行不会随当前策略变更。
        - heading "冻结阈值" [level=3] [ref=e337]
        - generic [ref=e338]:
          - generic [ref=e339]:
            - term [ref=e340]: candidate_min_runs
            - definition [ref=e341]: "20"
          - generic [ref=e342]:
            - term [ref=e343]: stable_min_runs
            - definition [ref=e344]: "20"
          - generic [ref=e345]:
            - term [ref=e346]: window_max_runs
            - definition [ref=e347]: "50"
          - generic [ref=e348]:
            - term [ref=e349]: commit_failure_rate
            - definition [ref=e350]: "0.05"
          - generic [ref=e351]:
            - term [ref=e352]: terminal_failure_rate
            - definition [ref=e353]: "0.10"
          - generic [ref=e354]:
            - term [ref=e355]: latency_increase_rate
            - definition [ref=e356]: "0.50"
          - generic [ref=e357]:
            - term [ref=e358]: mean_cost_increase_rate
            - definition [ref=e359]: "0.30"
          - generic [ref=e360]:
            - term [ref=e361]: unknown_rate
            - definition [ref=e362]: "0.10"
          - generic [ref=e363]:
            - term [ref=e364]: relative_epsilon
            - definition [ref=e365]: "0.000001"
        - heading "Gate Receipts" [level=3] [ref=e366]
        - paragraph [ref=e367]: 收据是历史证据，不代表可发布资格。健康证据按来源部署和冻结窗口关联；已消费前序证据不是本部署的新观测通过，旧窗口 pass 不覆盖最新 hold / fail。
        - generic [ref=e368]:
          - generic [ref=e369]:
            - text: shadow_health
            - generic [ref=e370]: passed
          - generic [ref=e374]:
            - text: canary_health
            - generic [ref=e375]: passed
          - generic [ref=e379]:
            - text: promotion_approval
            - generic [ref=e380]: passed
        - table [ref=e390]:
          - rowgroup [ref=e399]:
            - row [ref=e400]:
              - columnheader "Gate" [ref=e401]
              - columnheader "状态" [ref=e402]
              - columnheader "健康来源" [ref=e403]
              - columnheader "样本" [ref=e404]
              - columnheader "成本 USD" [ref=e405]
              - columnheader "Issuer" [ref=e406]
              - columnheader "签发时间" [ref=e407]
          - rowgroup [ref=e408]:
            - row [ref=e409]:
              - cell "campaign_eligibility" [ref=e410]
              - cell "passed" [ref=e411]
              - cell "artifact 资格证据" [ref=e416]
              - cell "21" [ref=e417]
              - cell "1.25000000" [ref=e418]
              - cell "redacted" [ref=e419]
              - cell "2026/10/30 08:00:01" [ref=e420]
            - row [ref=e421]:
              - cell "canary_health" [ref=e422]
              - cell "passed" [ref=e423]
              - cell "已消费前序证据（非本部署新观测） 查看策略 297e333a-2ed7-48c1-bd05-826ae1606e38 版本 5 · pass · 来源最新窗口 Window a16384e7411cff9c5d0d88de8106a561ecea06568d5969a4381cf09bb3f8c3f2 2026/11/2 06:21:05" [ref=e428]:
                - generic [ref=e429]:
                  - strong [ref=e430]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 297e333a-2ed7-48c1-bd05-826ae1606e38" [ref=e431] [cursor=pointer]:
                    - /url: "#/policies/297e333a-2ed7-48c1-bd05-826ae1606e38"
                    - code [ref=e432]: 297e333a-2ed7-48c1-bd05-826ae1606e38
                  - generic [ref=e433]: 版本 5 · pass · 来源最新窗口
                  - code [ref=e434]: Window a16384e7411cff9c5d0d88de8106a561ecea06568d5969a4381cf09bb3f8c3f2
                  - generic [ref=e435]: 2026/11/2 06:21:05
              - cell "20" [ref=e436]
              - cell "0.40000000" [ref=e437]
              - cell "redacted" [ref=e438]
              - cell "2026/11/2 06:21:05" [ref=e439]
            - row [ref=e440]:
              - cell "formal_holdout" [ref=e441]
              - cell "passed" [ref=e442]
              - cell "artifact 资格证据" [ref=e447]
              - cell "23" [ref=e448]
              - cell "1.25000000" [ref=e449]
              - cell "redacted" [ref=e450]
              - cell "2026/10/30 08:00:03" [ref=e451]
            - row [ref=e452]:
              - cell "harness_qualification" [ref=e453]
              - cell "passed" [ref=e454]
              - cell "artifact 资格证据" [ref=e459]
              - cell "24" [ref=e460]
              - cell "1.25000000" [ref=e461]
              - cell "redacted" [ref=e462]
              - cell "2026/10/30 08:00:04" [ref=e463]
            - row [ref=e464]:
              - cell "judge_calibration" [ref=e465]
              - cell "passed" [ref=e466]
              - cell "artifact 资格证据" [ref=e471]
              - cell "22" [ref=e472]
              - cell "1.25000000" [ref=e473]
              - cell "redacted" [ref=e474]
              - cell "2026/10/30 08:00:02" [ref=e475]
            - row [ref=e476]:
              - cell "promotion_approval" [ref=e477]
              - cell "passed" [ref=e478]
              - cell "artifact 资格证据" [ref=e483]
              - cell "20" [ref=e484]
              - cell "0E-8" [ref=e485]
              - cell "redacted" [ref=e486]
              - cell "2026/11/2 06:21:05" [ref=e487]
            - row [ref=e488]:
              - cell "shadow_health" [ref=e489]
              - cell "passed" [ref=e490]
              - cell "已消费前序证据（非本部署新观测） 查看策略 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66 版本 4 · pass · 来源最新窗口 Window b9bda59cb4f34b6768230db8a341cfc9566f0271d58cbe81c89a83f3664599a7 2026/11/2 06:21:05" [ref=e495]:
                - generic [ref=e496]:
                  - strong [ref=e497]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66" [ref=e498] [cursor=pointer]:
                    - /url: "#/policies/4e3e4706-a5d5-4dff-9cde-c51e0ca0da66"
                    - code [ref=e499]: 4e3e4706-a5d5-4dff-9cde-c51e0ca0da66
                  - generic [ref=e500]: 版本 4 · pass · 来源最新窗口
                  - code [ref=e501]: Window b9bda59cb4f34b6768230db8a341cfc9566f0271d58cbe81c89a83f3664599a7
                  - generic [ref=e502]: 2026/11/2 06:21:05
              - cell "20" [ref=e503]
              - cell "0.40000000" [ref=e504]
              - cell "redacted" [ref=e505]
              - cell "2026/11/2 06:21:05" [ref=e506]
        - heading "最新健康窗口" [level=3] [ref=e507]
        - generic [ref=e508]:
          - img "No data" [ref=e510]
          - generic [ref=e516]: 暂无健康窗口，指标不可用
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e517]
        - list [ref=e518]:
          - listitem [ref=e519]:
            - generic [ref=e527]:
              - strong [ref=e528]: promotion_transitioned
              - generic [ref=e529]: canary → active
              - generic [ref=e530]: 2026/11/2 06:21:05 · rehearsal
              - link "查看策略 d21ce845-a939-4a30-a589-1713e1667512" [ref=e531] [cursor=pointer]:
                - /url: "#/policies/d21ce845-a939-4a30-a589-1713e1667512"
                - code [ref=e532]: d21ce845-a939-4a30-a589-1713e1667512
              - generic [ref=e533]: "actor: redacted · reason: redacted"
        - paragraph [ref=e534]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
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
  47  |   if (info.project.name === 'mobile' && scenario !== 'current') {
  48  |     const table = detail.locator('.ant-table-content').first()
  49  |     expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
  50  |     await table.hover()
  51  |     await page.mouse.wheel(1100, 0)
  52  |     await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)
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
  96  |   } else if (scenario.startsWith('leaf_')) {
  97  |     const gate = scenario === 'leaf_shadow_valid' ? 'shadow_health' : 'canary_health'
  98  |     const ownLeaf = health.find((r: { gate_type: string }) => r.gate_type === gate)
  99  |     expect(fixture.leaf_proof.authority_accepts).toBe(validLocal || validChain)
  100 |     if (validLocal || validChain) {
  101 |       expect(ownLeaf.receipt_id).toBe(fixture.leaf_proof.receipt_id)
  102 |       expect(ownLeaf.health_source.relation).toBe(validLocal ? 'local' : 'consumed_chain')
  103 |       expect(health).toHaveLength(scenario === 'leaf_shadow_valid' ? 1 : 2)
  104 |     } else if (scenario === 'leaf_local_bad') {
  105 |       expect(ownLeaf).toBeUndefined()
  106 |       expect(health).toHaveLength(1)
  107 |       expect(health[0].gate_type).toBe('shadow_health')
  108 |       expect(health[0].health_source.relation).toBe('consumed_chain')
  109 |     } else {
  110 |       expect(health).toEqual([])
  111 |       await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  112 |     }
  113 |   } else if (validChain) {
  114 |     expect(health).toHaveLength(2)
  115 |     expect(health.every((r: { status: string; health_source: { relation: string } }) =>
  116 |       r.status === 'passed' && r.health_source.relation === 'consumed_chain')).toBe(true)
  117 |   } else {
> 118 |     expect(health, 'invalid latest approval or broken audit must not borrow older green consumption').toEqual([])
      |                                                                                                       ^ Error: invalid latest approval or broken audit must not borrow older green consumption
  119 |     await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  120 |   }
  121 | })
  122 | 
```