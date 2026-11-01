# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: spec-health.spec.ts >> production correct health binding genuine_malformed_latest_valid
- Location: live-e2e/spec-health.spec.ts:11:1

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
+     "evidence_hash": "90c7e54aeb6fa9a732579ae5d19fba0075fc6e276bd4b3b4adc92655def1d9a9",
+     "gate_type": "canary_health",
+     "health_source": Object {
+       "deployment_id": "2f203cff-46b2-4c18-9f1c-bc368b69dc2c",
+       "deployment_version": 5,
+       "evaluated_at": "2026-11-01T23:29:47.162668Z",
+       "is_latest_window": true,
+       "relation": "consumed_chain",
+       "thresholds_hash": "35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f",
+       "window_decision": "pass",
+       "window_id": "012ebe7f865d4e39c965c0c064ac8dd2d88dd95636040a13f923da6f153581b1",
+     },
+     "issued_at": "2026-11-01T23:29:47.162668Z",
+     "issuer": "redacted",
+     "policy_hash": "2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76",
+     "receipt_id": "6972ebfe-fdfe-467f-a3b2-c1788eacc9fc",
+     "sample_count": 20,
+     "status": "passed",
+   },
+   Object {
+     "cost": "0.40000000",
+     "evidence_hash": "564945524b113ffcaa55e94133e98671a5088f70a6bae6871da51709be062201",
+     "gate_type": "shadow_health",
+     "health_source": Object {
+       "deployment_id": "0b8abaa5-c40d-4abd-8237-962c1a406295",
+       "deployment_version": 4,
+       "evaluated_at": "2026-11-01T23:29:46.981451Z",
+       "is_latest_window": true,
+       "relation": "consumed_chain",
+       "thresholds_hash": "35cc4c7fdffb8c80dd9d55a4c38279f88aff86acef62e649a6592f5d7c73ca1f",
+       "window_decision": "pass",
+       "window_id": "f689da901257a0308d9528b5529acd93216d718019f0d35ada6ce09d0515c1f8",
+     },
+     "issued_at": "2026-11-01T23:29:46.981451Z",
+     "issuer": "redacted",
+     "policy_hash": "2537b3d6216e386297a9b26bd1ec76fd496bd815f2a58abf1402d4c5036c8c76",
+     "receipt_id": "4b52239e-800f-4b6e-8393-fd6aed843a3b",
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
                - link "查看策略 cc864aad-7574-4ba4-8f9d-8b57a0c9afad" [ref=e118] [cursor=pointer]:
                  - /url: "#/policies/cc864aad-7574-4ba4-8f9d-8b57a0c9afad"
                  - code [ref=e119]: cc864aad-7574-4ba4-8f9d-8b57a0c9afad
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
              - cell "2026/11/1 23:29:47" [ref=e139]
            - row [ref=e140]:
              - cell [ref=e141]:
                - link "查看策略 2f203cff-46b2-4c18-9f1c-bc368b69dc2c" [ref=e142] [cursor=pointer]:
                  - /url: "#/policies/2f203cff-46b2-4c18-9f1c-bc368b69dc2c"
                  - code [ref=e143]: 2f203cff-46b2-4c18-9f1c-bc368b69dc2c
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
              - cell "2026/11/1 23:29:46" [ref=e163]
            - row [ref=e164]:
              - cell [ref=e165]:
                - link "查看策略 0b8abaa5-c40d-4abd-8237-962c1a406295" [ref=e166] [cursor=pointer]:
                  - /url: "#/policies/0b8abaa5-c40d-4abd-8237-962c1a406295"
                  - code [ref=e167]: 0b8abaa5-c40d-4abd-8237-962c1a406295
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
              - cell "2026/11/1 23:29:46" [ref=e187]
            - row [ref=e188]:
              - cell [ref=e189]:
                - link "查看策略 31e1a0cc-c825-4ada-a4d4-1fd8ccef7932" [ref=e190] [cursor=pointer]:
                  - /url: "#/policies/31e1a0cc-c825-4ada-a4d4-1fd8ccef7932"
                  - code [ref=e191]: 31e1a0cc-c825-4ada-a4d4-1fd8ccef7932
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
              - cell "2026/11/1 23:29:46" [ref=e211]
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
              - cell "2026/11/1 23:29:46" [ref=e235]
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
              - cell "2026/11/1 23:29:46" [ref=e259]
            - row [ref=e260]:
              - cell [ref=e261]:
                - link "查看策略 aaaa3041-e499-436b-944f-943a6b55b5dc" [ref=e262] [cursor=pointer]:
                  - /url: "#/policies/aaaa3041-e499-436b-944f-943a6b55b5dc"
                  - code [ref=e263]: aaaa3041-e499-436b-944f-943a6b55b5dc
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
                  - code [ref=e280]: C 81b5722bd1bb
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
                - code [ref=e300]: cc864aad-7574-4ba4-8f9d-8b57a0c9afad
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
                  - link "查看策略 cc864aad-7574-4ba4-8f9d-8b57a0c9afad" [ref=e313] [cursor=pointer]:
                    - /url: "#/policies/cc864aad-7574-4ba4-8f9d-8b57a0c9afad"
                    - code [ref=e314]: cc864aad-7574-4ba4-8f9d-8b57a0c9afad
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
              - cell "2026/11/1 23:29:47" [ref=e335]
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
            - text: campaign_eligibility
            - generic [ref=e370]: passed
          - generic [ref=e374]:
            - text: canary_health
            - generic [ref=e375]: passed
          - generic [ref=e379]:
            - text: formal_holdout
            - generic [ref=e380]: passed
          - generic [ref=e384]:
            - text: harness_qualification
            - generic [ref=e385]: passed
          - generic [ref=e389]:
            - text: judge_calibration
            - generic [ref=e390]: passed
          - generic [ref=e394]:
            - text: shadow_health
            - generic [ref=e395]: passed
          - generic [ref=e399]:
            - text: promotion_approval
            - generic [ref=e400]: passed
        - table [ref=e410]:
          - rowgroup [ref=e419]:
            - row [ref=e420]:
              - columnheader "Gate" [ref=e421]
              - columnheader "状态" [ref=e422]
              - columnheader "健康来源" [ref=e423]
              - columnheader "样本" [ref=e424]
              - columnheader "成本 USD" [ref=e425]
              - columnheader "Issuer" [ref=e426]
              - columnheader "签发时间" [ref=e427]
          - rowgroup [ref=e428]:
            - row [ref=e429]:
              - cell "campaign_eligibility" [ref=e430]
              - cell "passed" [ref=e431]
              - cell "artifact 资格证据" [ref=e436]
              - cell "21" [ref=e437]
              - cell "1.25000000" [ref=e438]
              - cell "redacted" [ref=e439]
              - cell "2026/10/30 08:00:01" [ref=e440]
            - row [ref=e441]:
              - cell "canary_health" [ref=e442]
              - cell "passed" [ref=e443]
              - cell "已消费前序证据（非本部署新观测） 查看策略 2f203cff-46b2-4c18-9f1c-bc368b69dc2c 版本 5 · pass · 来源最新窗口 Window 012ebe7f865d4e39c965c0c064ac8dd2d88dd95636040a13f923da6f153581b1 2026/11/1 23:29:47" [ref=e448]:
                - generic [ref=e449]:
                  - strong [ref=e450]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 2f203cff-46b2-4c18-9f1c-bc368b69dc2c" [ref=e451] [cursor=pointer]:
                    - /url: "#/policies/2f203cff-46b2-4c18-9f1c-bc368b69dc2c"
                    - code [ref=e452]: 2f203cff-46b2-4c18-9f1c-bc368b69dc2c
                  - generic [ref=e453]: 版本 5 · pass · 来源最新窗口
                  - code [ref=e454]: Window 012ebe7f865d4e39c965c0c064ac8dd2d88dd95636040a13f923da6f153581b1
                  - generic [ref=e455]: 2026/11/1 23:29:47
              - cell "20" [ref=e456]
              - cell "0.40000000" [ref=e457]
              - cell "redacted" [ref=e458]
              - cell "2026/11/1 23:29:47" [ref=e459]
            - row [ref=e460]:
              - cell "formal_holdout" [ref=e461]
              - cell "passed" [ref=e462]
              - cell "artifact 资格证据" [ref=e467]
              - cell "23" [ref=e468]
              - cell "1.25000000" [ref=e469]
              - cell "redacted" [ref=e470]
              - cell "2026/10/30 08:00:03" [ref=e471]
            - row [ref=e472]:
              - cell "harness_qualification" [ref=e473]
              - cell "passed" [ref=e474]
              - cell "artifact 资格证据" [ref=e479]
              - cell "24" [ref=e480]
              - cell "1.25000000" [ref=e481]
              - cell "redacted" [ref=e482]
              - cell "2026/10/30 08:00:04" [ref=e483]
            - row [ref=e484]:
              - cell "judge_calibration" [ref=e485]
              - cell "passed" [ref=e486]
              - cell "artifact 资格证据" [ref=e491]
              - cell "22" [ref=e492]
              - cell "1.25000000" [ref=e493]
              - cell "redacted" [ref=e494]
              - cell "2026/10/30 08:00:02" [ref=e495]
            - row [ref=e496]:
              - cell "promotion_approval" [ref=e497]
              - cell "passed" [ref=e498]
              - cell "artifact 资格证据" [ref=e503]
              - cell "20" [ref=e504]
              - cell "0E-8" [ref=e505]
              - cell "redacted" [ref=e506]
              - cell "2026/11/1 23:29:47" [ref=e507]
            - row [ref=e508]:
              - cell "shadow_health" [ref=e509]
              - cell "passed" [ref=e510]
              - cell "已消费前序证据（非本部署新观测） 查看策略 0b8abaa5-c40d-4abd-8237-962c1a406295 版本 4 · pass · 来源最新窗口 Window f689da901257a0308d9528b5529acd93216d718019f0d35ada6ce09d0515c1f8 2026/11/1 23:29:46" [ref=e515]:
                - generic [ref=e516]:
                  - strong [ref=e517]: 已消费前序证据（非本部署新观测）
                  - link "查看策略 0b8abaa5-c40d-4abd-8237-962c1a406295" [ref=e518] [cursor=pointer]:
                    - /url: "#/policies/0b8abaa5-c40d-4abd-8237-962c1a406295"
                    - code [ref=e519]: 0b8abaa5-c40d-4abd-8237-962c1a406295
                  - generic [ref=e520]: 版本 4 · pass · 来源最新窗口
                  - code [ref=e521]: Window f689da901257a0308d9528b5529acd93216d718019f0d35ada6ce09d0515c1f8
                  - generic [ref=e522]: 2026/11/1 23:29:46
              - cell "20" [ref=e523]
              - cell "0.40000000" [ref=e524]
              - cell "redacted" [ref=e525]
              - cell "2026/11/1 23:29:46" [ref=e526]
        - heading "最新健康窗口" [level=3] [ref=e527]
        - generic [ref=e528]:
          - img "No data" [ref=e530]
          - generic [ref=e536]: 暂无健康窗口，指标不可用
        - heading "回滚 / 冻结审计时间线" [level=3] [ref=e537]
        - list [ref=e538]:
          - listitem [ref=e539]:
            - generic [ref=e547]:
              - strong [ref=e548]: promotion_transitioned
              - generic [ref=e549]: canary → active
              - generic [ref=e550]: 2026/11/1 23:29:47 · rehearsal
              - link "查看策略 cc864aad-7574-4ba4-8f9d-8b57a0c9afad" [ref=e551] [cursor=pointer]:
                - /url: "#/policies/cc864aad-7574-4ba4-8f9d-8b57a0c9afad"
                - code [ref=e552]: cc864aad-7574-4ba4-8f9d-8b57a0c9afad
              - generic [ref=e553]: "actor: redacted · reason: redacted"
        - paragraph [ref=e554]: 展示最近最多 100 条事件；完整分页证据见审计时间线页签。
```

# Test source

```ts
  1  | import { expect, test } from '@playwright/test'
  2  | import { readFileSync, writeFileSync } from 'node:fs'
  3  | import { createHash } from 'node:crypto'
  4  | import { join } from 'node:path'
  5  | 
  6  | const own = '/tmp/m3-task9-spec-feca62c7-189a-4708-b334-5456f6d79d93'
  7  | const scenario = process.env.SPEC_SCENARIO!
  8  | const tag = process.env.SPEC_RUN_TAG || scenario
  9  | const fixture = JSON.parse(readFileSync(join(own, `live-fixture-${scenario}.json`), 'utf8'))
  10 | 
  11 | test(`production correct health binding ${scenario}`, async ({ page, request }, info) => {
  12 |   const requests: { method: string; url: string }[] = []
  13 |   const errors: string[] = []
  14 |   page.on('request', r => requests.push({ method: r.method(), url: r.url() }))
  15 |   page.on('pageerror', e => errors.push(e.message))
  16 |   page.on('console', m => { if (m.type() === 'error') errors.push(m.text()) })
  17 |   const response = await request.get(`/ops-api/ops/policies/deployments/${fixture.id}`)
  18 |   expect(response.status()).toBe(200)
  19 |   const body = await response.json()
  20 |   await page.goto(`/ops/#/policies/${fixture.id}`)
  21 |   const detail = page.getByRole('region', { name: '策略版本详情' })
  22 |   await expect(detail.getByText(fixture.policy_hash, { exact: true }).first()).toBeVisible()
  23 |   await expect(detail.getByText(/收据是历史证据，不代表可发布资格/)).toBeVisible()
  24 |   const sourceText = await detail.locator('strong').allTextContents()
  25 |   const source = detail.getByText(scenario === 'history'
  26 |     ? '本部署窗口'
  27 |     : '已消费前序证据（非本部署新观测）', { exact: true }).first()
  28 |   if (scenario !== 'current') {
  29 |     await expect(source).toBeVisible()
  30 |     await source.scrollIntoViewIfNeeded()
  31 |     const box = await source.boundingBox()
  32 |     expect(box).not.toBeNull()
  33 |     expect(box!.x).toBeGreaterThanOrEqual(0)
  34 |     expect(box!.x + box!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  35 |     await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}-left.png`,
  36 |       animations: 'disabled' })
  37 |   }
  38 |   const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)
  39 |   if (info.project.name === 'mobile' && scenario !== 'current') {
  40 |     const table = detail.locator('.ant-table-content').first()
  41 |     expect(await table.evaluate(el => el.scrollWidth > el.clientWidth)).toBe(true)
  42 |     await table.hover()
  43 |     await page.mouse.wheel(1100, 0)
  44 |     await expect.poll(() => table.evaluate(el => el.scrollLeft)).toBeGreaterThan(0)
  45 |   }
  46 |   const hashes: Record<string, string> = {}
  47 |   for (const url of [...new Set(requests.map(r => r.url).filter(u => /\/assets\/.*\.(css|js)$/.test(u)))]) {
  48 |     const asset = await request.get(url)
  49 |     const bytes = await asset.body()
  50 |     expect(bytes.equals(readFileSync(join(own, 'frontend/dist', new URL(url).pathname)))).toBe(true)
  51 |     hashes[url] = createHash('sha256').update(bytes).digest('hex')
  52 |   }
  53 |   expect(Object.keys(hashes).length).toBeGreaterThan(0)
  54 |   expect(requests.every(r => r.method === 'GET')).toBe(true)
  55 |   expect(errors).toEqual([])
  56 |   expect(overflow).toBeLessThanOrEqual(1)
  57 |   await page.screenshot({ path: `${own}/screenshots/production-${tag}-${info.project.name}.png`,
  58 |     fullPage: true, animations: 'disabled' })
  59 |   await detail.screenshot({ path: `${own}/screenshots/detail-${tag}-${info.project.name}.png`,
  60 |     animations: 'disabled' })
  61 |   writeFileSync(`${own}/production-${tag}-${info.project.name}.json`,
  62 |     JSON.stringify({ scenario, body, sourceText, requests, errors, overflow, hashes }, null, 2) + '\n')
  63 |   const health = body.gate_receipts.filter((r: { health_source: unknown }) => r.health_source)
  64 |   if (scenario === 'current') {
  65 |     expect(body.is_current).toBe(true)
  66 |     expect(body.latest_health_window.decision).toBe('hold')
  67 |     expect(health).toEqual([])
  68 |     await expect(detail.getByText('passed', { exact: true })).toHaveCount(0)
  69 |   } else if (scenario === 'history') {
  70 |     expect(body.is_current).toBe(false)
  71 |     expect(health).toHaveLength(1)
  72 |     expect(health[0].receipt_id).toBe(fixture.old_receipt)
  73 |     expect(health[0].health_source.deployment_id).toBe(fixture.old)
  74 |     expect(health[0].health_source.window_id).toBe(fixture.old_window)
  75 |     const newer = await request.get(`/ops-api/ops/policies/deployments/${fixture.current}`)
  76 |     const newBody = await newer.json()
  77 |     expect(newBody.latest_health_window.decision).toBe('pass')
  78 |     expect(newBody.gate_receipts.find((r: { gate_type: string }) => r.gate_type === 'canary_health').receipt_id)
  79 |       .not.toBe(fixture.old_receipt)
  80 |   } else {
> 81 |     expect(health, 'invalid latest approval or broken audit must not borrow older green consumption').toEqual([])
     |                                                                                                       ^ Error: invalid latest approval or broken audit must not borrow older green consumption
  82 |     await expect(detail.getByText('已消费前序证据（非本部署新观测）', { exact: true })).toHaveCount(0)
  83 |   }
  84 | })
  85 | 
```