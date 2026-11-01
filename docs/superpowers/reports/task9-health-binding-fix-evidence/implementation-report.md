# Task9 C1/P2 Health Binding Repair

Status: implementation frozen for parent fresh full Task9 SPEC, then CODE only
after SPEC PASS. This is not Task9 acceptance or release qualification.

Parent: `517c04f137ed93ebb042ec4ff027d120d3625847`.
Authorized tree: `/Users/bytedance/Documents/trae_projects/eduagent-m3`,
branch `feature/m3-trusted-policy-promotion`. Main eduagent is read-only.
The parent archives prior CODE FAIL; prior product version is e29bdb4.

## Source Semantics

- Qualification gates retain artifact policy/protocol/runtime/source binding
  and issued_at / created_at / receipt_id descending ordering. No passed filter.
- Health gates are separate, bounded read-only projections. A source must bind
  exact deployment ID/version, thresholds, canonical window identity and receipt
  evidence, metric contract/cohort/statistics, issuer/model/data role, and time.
- Selection occurs before validation. Latest bound failed/unknown is shown with
  its actual status; invalid latest never falls back to an older pass. A latest
  artifact/gate receipt whose deployment identity is absent or malformed blocks
  display conservatively rather than being silently skipped.
- Local Shadow/Canary/Active is preferred. Canary consumes Shadow only through
  the existing read-only predecessor helper plus typed audit relation. Active
  consumes the exact Canary receipt identified by matched approval/audit, with
  artifact, source, environment, versions, thresholds, salt, stable policy,
  command and timestamp consistency. Active projection does not replay health
  observations or re-evaluate release gates.
- Consumed sources are selected at the actual transition cutoff; later receipts
  cannot replace them. Broken chains do not borrow a same-artifact/adjacent pass.
- Closed `health_source` DTO exposes only relation, deployment ID/version,
  window ID, thresholds hash, window decision/evaluation time and latest flag.
  Raw receipt details/actor/reason/namespace never enter the public DTO.
- UI labels consumed evidence as not this deployment's new observations, and
  labels local older-window evidence explicitly. Latest hold/fail remains
  distinct. Ops evidence is not publication authorization.

## Final Verification

| Raw XML | Executions | PASS | Fail / Error / Skip |
| --- | ---: | ---: | --- |
| c1redvalid.xml | 2 | 0 | 2 / 0 / 0, effective RED before product edits |
| greenfinal.xml | 2 | 2 | 0 / 0 / 0 |
| relationsfreeze.xml | 138 | 138 | 0 / 0 / 0 |
| fullv2.xml | 1726 | 1726 | 0 / 0 / 0 |
| uifinalv2.xml | 54 | 54 | 0 / 0 / 0 |
| productioncurrentfinal.xml | 2 | 2 | 0 / 0 / 0 |
| productionhistoryfinal.xml | 2 | 2 | 0 / 0 / 0 |

Relations = new health regressions 42 + original Task9 API 77 + original Ops API
19. Original F1 nine cases all PASS in fullv2 and the API matrix, see f1-nine.json.
Node20 buildfinal passes; Vite retains the existing chunk-size warning.
Backend retains the existing TestAgent collection warning, zero skipped cases.

Production assets served through real HTTP/PG, not route mocks. Both viewports
verify current B is current/hold without borrowing A/pass, and historical A uses
exact RA/local/window while newer B has its own distinct passing receipt. HTTP
assets match built local bytes/SHA; browser requests are GET-only, page errors
zero, document overflow <= 1 px, mobile health table actually scrolls.
All four final screenshots were opened and visually checked. Historical mobile
screenshot is after horizontal scroll to the right, so source columns are off
screen by design; source visibility and relationship were asserted before scroll.

352 source file hashes use a noncircular sorted path/SHA recipe:
`78fb2d84827b0e9c32df1bebbee9d4840f5eff301100da0a9f5489a0146b4357`.
Original 351 baseline remains
`8561cf7f84c2ed1f30e548ccb5adba0ed891cca2b9efef3d9c0ad40bb91ea582`.
The new untracked regression was explicitly included in the final 352-file
manifest. Earlier per-invocation snapshot tracked-file identities have 351 files;
they are not mislabeled as the full 352-file final authority.

## Preserved Failure History

All original CODE FAIL/golden files remain untouched. This archive retains:
invalid c1red fixture (2 errors), effective c1redvalid (2 assertion failures),
relations (126 / 5 failures, unique receipt evidence fixture),
relationsv2 (126 PASS; superseded permissive malformed-list expectation),
relationsv3 (JSONB-vs-JSON implementation error),
relationsv4 (4 DTO serialization fixture failures),
relationsfinal (4 duplicate environment/version fixture failures),
full (1725 PASS / 1 nondeterministic receipt-ID tie fixture failure),
build/buildv2 compiler failures, uifull six failures, uifinal output-dir
collision, and initial production four PASS with displaced current-head fixture.
No failed XML, logs or original judgments were overwritten to obtain green.

The final malformed-list test requires unavailable, not old-pass fallback.
The Active synthetic chain includes a valid positive control and separate
no-audit/no-approval/wrong-command-hash/bool-version fail-closed cases, constructed
by append-only immutable records and real approval helper. No trigger disabling
or immutable deployment UPDATE was introduced by these new regressions.

## Cleanup And Limits

16 own invocation/service databases dropped, zero remaining; 496 recorded own
UUID streams had zero residual and remain absent. Both own service ports closed.
Primary tracked/index/source/venv metadata and source-side Vite cache/temp remain
byte/metadata unchanged across all recorded invocation boundaries.
Caches, physical copied dependencies and own temporary fixture databases are
not evidence and are removed after archiving; raw scripts/XML/logs/screenshots,
test-source copy, source hashes and failed browser traces are retained.

All observations are synthetic engineering fixtures, no student/model requests,
cost USD 0, no independent release qualification. No parent 1684 baseline credit,
no production-scale or multi-worker guarantee. Health evidence checks are bounded
metadata/source projections, not metric replay or authorization. Unknown source
identity can conservatively hide otherwise valid historical evidence; it cannot
create a green pass. Task10/Agent50 remain paused. No amend/push/skipped hooks or
git config changes.
