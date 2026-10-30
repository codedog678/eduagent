# M3 Trusted Policy Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a PostgreSQL-authoritative policy promotion plane with Judge v3, immutable evidence gates, run-time policy pinning, controlled Shadow/Canary traffic, deterministic health evaluation, and transactional rollback.

**Architecture:** Promotion state lives in immutable PostgreSQL snapshots behind one CAS-protected environment head. Run admission consumes a signed rehearsal token, assigns a stable/candidate cohort with HMAC, and persists the deployment, policy, and namespace before publishing work; retries, lease takeovers, business execution, and expert jobs inherit that binding. Shadow and Canary executions use isolated rehearsal stores, append observations, and feed a deterministic evaluator that can move the environment head back to the previous stable policy in one transaction.

**Tech Stack:** Python 3.11, Pydantic v2, SQLAlchemy async, PostgreSQL 16, Redis Streams, FastAPI, Prometheus, React 18, TypeScript, Ant Design, pytest, Docker Compose.

---

## Scope and File Map

### Judge and qualification evidence

| File | Responsibility |
| --- | --- |
| `python/evals/optimization/judge_v3.py` | Strict verdict/reason/evidence schema, one repair, unknown normalization, diagnostics |
| `python/evals/optimization/scoring.py` | Call Judge v3 and preserve raw/repair evidence in scored rows |
| `python/evals/optimization/gates.py` | Recompute Judge v3 rows and reject unknown or incompatible protocol |
| `python/evals/optimization/calibration.py` | Verify v3 calibration evidence and unknown rate |
| `python/evals/optimization/campaign.py` | Export immutable qualification receipt material for PostgreSQL registration |
| `python/tests/evals/test_judge_v3.py` | Schema, consistency, repair, unknown, evidence-reference tests |
| `python/tests/evals/test_rsi_campaign.py` | Campaign-to-receipt binding and one-use holdout regression tests |

### Promotion control plane

| File | Responsibility |
| --- | --- |
| `python/core/distributed/promotion_contracts.py` | Deployment states, thresholds, commands, assignments, observations, reports |
| `python/core/distributed/promotion_models.py` | Artifact, receipt, deployment, head, nonce, observation, window, audit, shadow ORM tables |
| `python/core/distributed/promotion_repository.py` | Immutable registration, CAS transitions, token consumption, observation and rollback transactions |
| `python/core/distributed/promotion_service.py` | Gate verification and command orchestration |
| `python/core/distributed/promotion_cli.py` | Separate write-capable registration, transition, token, health, and report commands |
| `python/core/distributed/runtime.py` | M3 schema upgrade and runtime service wiring |
| `python/config/settings.py` | Promotion enablement, secrets, thresholds, stream, and isolated-store settings |
| `python/tests/distributed/test_promotion_contracts.py` | Strict contract and threshold tests |
| `python/tests/distributed/test_promotion_repository.py` | PostgreSQL authority, immutability, CAS, gate, and rollback tests |

### Admission and execution pinning

| File | Responsibility |
| --- | --- |
| `python/core/distributed/policy_assignment.py` | Token verification, nonce digest, HMAC bucket, environment assignment |
| `python/core/distributed/rehearsal_store.py` | Namespace validation and isolated SQLite path routing |
| `python/core/distributed/models.py` | Immutable Run assignment fields |
| `python/core/distributed/repository.py` | Admission lock, assignment transaction, RunClaim binding, terminal observation hook |
| `python/core/distributed/dispatcher.py` | Route production and rehearsal Run Outbox events to separate streams |
| `python/core/distributed/broker.py` | Dedicated rehearsal Run stream |
| `python/core/distributed/contracts.py` | Frozen execution binding contract |
| `python/core/distributed/worker.py` | Pass the persisted binding and record terminal outcomes |
| `python/core/distributed/executor.py` | Execute with a pinned policy and namespaced business store |
| `python/core/run_context.py` | Deployment/cohort/namespace context exposed to the coordinator |
| `python/core/harness.py` | Prefer the trusted distributed binding over file policy resolution |
| `python/core/distributed/expert_contracts.py` | Deployment and namespace in parent authority and expert snapshots |
| `python/core/distributed/expert_models.py` | Persist expert deployment and namespace |
| `python/core/distributed/expert_repository.py` | Revalidate expert binding against the parent Run |
| `python/api/distributed_routes.py` | Read the signed rehearsal token header at admission |
| `python/tests/distributed/test_policy_assignment.py` | Token, nonce, HMAC and replay tests |
| `python/tests/distributed/test_policy_pinning.py` | Retry, takeover, harness and expert inheritance tests |

### Shadow, health, Ops, and evidence

| File | Responsibility |
| --- | --- |
| `python/core/distributed/shadow_worker.py` | PostgreSQL-authoritative claim/execute/complete loop for no-production-commit Shadow jobs |
| `python/core/distributed/policy_health.py` | Deterministic windows, baseline comparison, hold/pass/fail, transactional rollback |
| `python/core/distributed/metrics.py` | Assignment, gate, observation and rollback Prometheus instruments |
| `python/core/distributed/ops_contracts.py` | Redacted promotion response models |
| `python/core/distributed/ops_queries.py` | Read-only deployment, gate, health, cohort and audit projections |
| `python/api/ops_routes.py` | Read-only promotion endpoints |
| `frontend/src/ops/PoliciesView.tsx` | Deployment timeline, gates, health and rollback evidence |
| `frontend/src/ops/OpsApp.tsx` | Add Policies navigation |
| `frontend/src/ops/api.ts` | Promotion query methods |
| `frontend/src/ops/types.ts` | Promotion response types |
| `frontend/src/ops/ops.css` | Compact status, metric and timeline styles |
| `python/tests/distributed/test_shadow_worker.py` | Shadow idempotency, isolation and recovery tests |
| `python/tests/distributed/test_policy_health.py` | Frozen windows, thresholds, late samples and rollback races |
| `python/tests/distributed/test_promotion_ops_api.py` | Read-only, bounded and redacted API tests |
| `frontend/e2e/ops.spec.ts` | Policies view smoke and responsive assertions |
| `python/tests/integration/test_policy_promotion.py` | Real PostgreSQL/Redis/multi-worker healthy and rollback rehearsal |
| `tools/run_policy_rehearsal.py` | Controlled request driver and evidence exporter |
| `docs/engineering/trusted-policy-promotion.md` | Protocol, commands, failure matrix, evidence and non-claims |

## Task 1: Upgrade the Judge to a Fail-Closed v3 Contract

**Files:**
- Create: `python/evals/optimization/judge_v3.py`
- Create: `python/tests/evals/test_judge_v3.py`
- Modify: `python/evals/optimization/scoring.py`
- Modify: `python/evals/optimization/gates.py`
- Modify: `python/evals/optimization/calibration.py`
- Modify: `python/evals/optimization/protocol.py`
- Modify: `python/evals/optimization/campaign.py`

- [ ] **Step 1: Write failing Judge v3 contract tests**

Create tests named:

- `test_valid_v3_judgment_normalizes_to_existing_score_shape`
- `test_verdict_reason_and_criteria_must_agree`
- `test_evidence_refs_must_exist_in_current_payload`
- `test_one_bounded_repair_can_fix_schema_only`
- `test_second_invalid_response_becomes_unknown_with_diagnostics`
- `test_unknown_never_counts_as_task_success`

Use a fixed semantic criterion and tool decision:

```python
VALID = {
    "verdict": "pass",
    "reason_codes": ["all_criteria_passed"],
    "criterion_results": [
        {
            "criterion_id": "semantic:H5",
            "verdict": "pass",
            "evidence_refs": ["response:s1"],
            "rationale": "The response cites the observed behavior.",
        },
        {
            "criterion_id": "decision:s1",
            "verdict": "pass",
            "evidence_refs": ["call:s1:0"],
            "rationale": "The required call is present and scoped.",
        },
    ],
}
```

Assert that a top-level `pass` containing a failed criterion, a `pass` with
`insufficient_evidence`, an unknown evidence reference, extra JSON fields, or
an empty rationale fails validation. Model a fake text service returning two
invalid responses and assert one repair call plus `verdict == "unknown"`.

- [ ] **Step 2: Run the new tests and verify failure**

```bash
cd python
python -m pytest tests/evals/test_judge_v3.py -q
```

Expected: collection fails because `evals.optimization.judge_v3` does not exist.

- [ ] **Step 3: Implement strict v3 validation and one repair**

Define frozen contracts and the deterministic validator:

```python
class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"

class CriterionResult(FrozenModel):
    criterion_id: str = Field(min_length=1, max_length=128)
    verdict: Verdict
    evidence_refs: list[str] = Field(max_length=8)
    rationale: str = Field(min_length=1, max_length=600)

class JudgeV3Result(FrozenModel):
    schema_version: Literal[3] = 3
    verdict: Verdict
    reason_codes: list[str] = Field(min_length=1, max_length=8)
    criterion_results: list[CriterionResult] = Field(min_length=1)

class JudgeOutcome(FrozenModel):
    result: JudgeV3Result
    raw_response: str
    repair_response: str | None
    validation_errors: list[str]
    repaired: bool
```

`validate_result()` must compare exact expected criterion IDs, reject duplicate
criteria, allow only payload-provided evidence references, and enforce:

```python
expected = (
    Verdict.FAIL if Verdict.FAIL in verdicts
    else Verdict.UNKNOWN if Verdict.UNKNOWN in verdicts
    else Verdict.PASS
)
if result.verdict != expected:
    raise ValueError("top-level verdict contradicts criterion verdicts")
if result.verdict == Verdict.PASS and result.reason_codes != ["all_criteria_passed"]:
    raise ValueError("pass verdict has incompatible reason codes")
```

The complete reason-code allowlist is `all_criteria_passed`,
`criterion_failed`, `insufficient_evidence`, `invalid_schema`, and
`inconsistent_output`. Pass permits only `all_criteria_passed`; fail requires
`criterion_failed`; unknown permits only the remaining three.

`judge_once()` calls the frozen v3 prompt. On validation failure it makes one
repair call containing only the invalid JSON, validation errors, allowed
criterion IDs, and allowed evidence refs. A second failure returns an explicit
unknown result with one unknown criterion per expected ID and preserves both
raw responses.

- [ ] **Step 4: Integrate v3 without losing replay evidence**

Replace the direct `Judgment.model_validate_json()` path in `scoring.py` with
`judge_once()`. Convert v3 criteria into the existing semantic/decision shape
for `combine_judgment`, but add these immutable fields to each scored row:

```python
{
    "judge_protocol_version": 3,
    "judge_verdict": outcome.result.verdict,
    "judge_reason_codes": outcome.result.reason_codes,
    "raw_judgment_v3": outcome.result.model_dump(mode="json"),
    "judge_diagnostics": {
        "raw_response": outcome.raw_response,
        "repair_response": outcome.repair_response,
        "validation_errors": outcome.validation_errors,
        "repaired": outcome.repaired,
    },
}
```

When the verdict is unknown, return `task_success=False`, `score=0`,
`review_status="unknown"` and keep automatic results unchanged. Update
`verify_raw_row()` and `verify_manifest()` to replay v3 validation and reject
unknown rows for qualification. Increment the frozen protocol schema and
scorer digest so v2 evidence cannot silently satisfy v3 gates. Define
`JUDGE_MAX_CALLS = 2`; campaign preflight and comparison reservation must use
that worst case, while the settled ledger records whether one or two Judge
calls actually occurred.

- [ ] **Step 5: Run focused and existing evaluation tests**

```bash
cd python
python -m pytest \
  tests/evals/test_judge_v3.py \
  tests/evals/test_policy_optimization.py \
  tests/evals/test_rsi_campaign.py -q
```

Expected: all selected tests pass; fixtures using the old protocol fail only
when intentionally asserted as incompatible.

- [ ] **Step 6: Commit Judge v3**

```bash
git add python/evals/optimization python/tests/evals
git commit -m "feat(evals): add fail-closed judge v3"
```

## Task 2: Add Promotion Contracts, Tables, and Schema Upgrade

**Files:**
- Create: `python/core/distributed/promotion_contracts.py`
- Create: `python/core/distributed/promotion_models.py`
- Create: `python/tests/distributed/test_promotion_contracts.py`
- Modify: `python/core/distributed/models.py`
- Modify: `python/core/distributed/expert_models.py`
- Modify: `python/core/distributed/runtime.py`
- Modify: `python/config/settings.py`
- Modify: `python/tests/distributed/test_repository.py`

- [ ] **Step 1: Write failing metadata and contract tests**

Assert strict enums and frozen defaults:

```python
class DeploymentState(StrEnum):
    REGISTERED = "registered"
    SHADOW = "shadow"
    CANARY = "canary"
    ACTIVE = "active"
    FROZEN = "frozen"
    ROLLED_BACK = "rolled_back"

DEFAULT_THRESHOLDS = {
    "candidate_min_runs": 20,
    "stable_min_runs": 20,
    "window_max_runs": 50,
    "commit_failure_rate": "0.05",
    "terminal_failure_rate": "0.10",
    "latency_increase_rate": "0.50",
    "mean_cost_increase_rate": "0.30",
    "unknown_rate": "0.10",
    "relative_epsilon": "0.000001",
}
```

Test `traffic_basis_points` bounds, UTC timestamps, SHA-256 fields, unknown
fields, invalid state transitions, and immutable threshold hashes. Extend the
metadata assertion to require all M3 tables and new Run/expert columns. Add
PostgreSQL tests proving UPDATE and DELETE fail for artifacts, receipts,
deployments, observations, health windows and audit events, while the
environment head remains CAS-updatable.

- [ ] **Step 2: Run tests and verify failure**

```bash
cd python
python -m pytest \
  tests/distributed/test_promotion_contracts.py \
  tests/distributed/test_repository.py::test_distributed_metadata_contains_run_and_expert_plane_tables -q
```

Expected: import failure and missing-table assertions.

- [ ] **Step 3: Define strict promotion contracts**

Implement `FrozenContract(extra="forbid", frozen=True)` models:

```python
class PolicyThresholds(FrozenContract):
    candidate_min_runs: int = Field(default=20, ge=1, le=10000)
    stable_min_runs: int = Field(default=20, ge=1, le=10000)
    window_max_runs: int = Field(default=50, ge=1, le=10000)
    commit_failure_rate: Decimal = Field(default=Decimal("0.05"), gt=0, le=1)
    terminal_failure_rate: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    latency_increase_rate: Decimal = Field(default=Decimal("0.50"), gt=0)
    mean_cost_increase_rate: Decimal = Field(default=Decimal("0.30"), gt=0)
    unknown_rate: Decimal = Field(default=Decimal("0.10"), gt=0, le=1)
    relative_epsilon: Decimal = Field(default=Decimal("0.000001"), gt=0)

    @property
    def digest(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))
```

Also define `PolicyArtifact`, `GateReceipt`, `DeploymentSnapshot`,
`PolicyExecutionBinding`, `PromotionCommand`, `PolicyObservation`,
`HealthDecision`, and `RehearsalClaims`. Use string decimals for canonical
JSON and explicit `Literal` values for gate types and cohorts.

Freeze the execution binding shape because every later task reuses it:

```python
class PolicyComponents(FrozenContract):
    retrieval_rules: str = Field(min_length=1, max_length=6000)

class PolicyExecutionBinding(FrozenContract):
    deployment_id: UUID
    environment: Literal["production", "rehearsal"]
    effective_policy_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    components: PolicyComponents
    policy_cohort: Literal["stable", "candidate", "shadow"]
    assignment_key_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    assignment_reason: str = Field(min_length=1, max_length=128)
    state_namespace: str = Field(min_length=1, max_length=128)
    rehearsal_id: str | None = Field(default=None, max_length=128)
    rehearsal_fault_profile: Literal["none", "latency", "commit_failure"] = "none"
```

- [ ] **Step 4: Add ORM models and immutable assignment columns**

Create tables:

```text
policy_artifacts
policy_gate_receipts
policy_deployments
policy_environment_heads
rehearsal_token_nonces
policy_observations
policy_health_windows
policy_audit_events
policy_shadow_executions
```

Use `(environment, version)`, `(policy_hash, gate_type, evidence_hash)`,
`command_id`, observation key, nonce digest, and `(parent_run_id,
deployment_id)` unique constraints. Add `deployment_id`,
`effective_policy_hash`, `policy_cohort`, `assignment_key_hash`,
`assignment_reason`, `state_namespace`, and `rehearsal_id` to
`DistributedRun`; also persist `rehearsal_fault_profile` with default `none`.
Add `deployment_id` and `state_namespace` to
`DistributedExpertJob`. Register promotion metadata from `models.py`.

- [ ] **Step 5: Add safe schema upgrade and settings**

Add `upgrade_m3_schema()` after `create_all()`. It must:

1. Add new columns with `IF NOT EXISTS`.
2. Insert deterministic builtin policy and initial `production` and
   `rehearsal` deployment snapshots.
3. Backfill historical Runs as `stable`, namespace `production`,
   reason `legacy_backfill`.
4. Backfill expert jobs from their parent Runs.
5. Set required columns `NOT NULL` only after backfill.
6. Add foreign keys and indexes idempotently.
7. Install idempotent `BEFORE UPDATE OR DELETE` rejection triggers on all
   append-only M3 tables; only environment heads and active Shadow rows are
   mutable.

Add settings:

```python
promotion_enabled: bool = False
promotion_rehearsal_secret: SecretStr = SecretStr("")
promotion_assignment_secret: SecretStr = SecretStr("")
promotion_rehearsal_store_root: str = str(PROJECT_ROOT / "data/rehearsal")
promotion_rehearsal_stream: str = "eduagent:rehearsal-runs"
promotion_rehearsal_consumer_group: str = "eduagent-rehearsal-run-workers"
promotion_shadow_stream: str = "eduagent:policy-shadow"
promotion_shadow_consumer_group: str = "eduagent-policy-shadow-workers"
promotion_shadow_lease_seconds: float = Field(default=15, ge=3, le=300)
promotion_shadow_heartbeat_seconds: float = Field(default=3, ge=.5, le=60)
promotion_shadow_poll_seconds: float = Field(default=.25, gt=0, le=60)
promotion_health_poll_seconds: float = Field(default=1, gt=0, le=300)
promotion_token_ttl_seconds: int = Field(default=300, ge=30, le=3600)
promotion_fault_injection_enabled: bool = False
promotion_injected_latency_seconds: float = Field(default=2, ge=0, le=30)
```

When promotion is enabled, require distributed mode and both secrets with at
least 32 characters. Never include secret values in validation messages.

- [ ] **Step 6: Run tests and commit**

```bash
cd python
python -m pytest \
  tests/distributed/test_promotion_contracts.py \
  tests/distributed/test_repository.py \
  tests/distributed/test_contracts.py -q
```

Expected: all selected tests pass, including two consecutive calls to
`upgrade_m3_schema()` on the same database.

```bash
git add python/core/distributed python/config/settings.py python/tests
git commit -m "feat(policy): add promotion schema and contracts"
```

## Task 3: Register Immutable Artifacts and Qualification Receipts

**Files:**
- Create: `python/core/distributed/promotion_repository.py`
- Create: `python/core/distributed/promotion_service.py`
- Create: `python/tests/distributed/test_promotion_repository.py`
- Modify: `python/evals/optimization/campaign.py`
- Modify: `python/tests/evals/test_rsi_campaign.py`

- [ ] **Step 1: Write failing registration and receipt tests**

Cover:

- identical artifact registration is idempotent;
- same hash with different body is rejected;
- simulation and exploratory campaigns cannot issue release receipts;
- calibration, development, holdout and harness receipts bind campaign,
  protocol, runtime, source revision, model identity, data role and cost;
- `failed` or `unknown` receipts never satisfy a gate;
- a newer failed/unknown receipt invalidates an older pass for the same
  policy/gate/protocol binding;
- changed campaign evidence is rejected when re-opened;
- old file-registry eligibility alone does not create PostgreSQL eligibility.

Use a real `Campaign` test fixture and assert the exported shape:

```python
material = campaign.qualification_material()
assert material["artifact"]["policy_hash"] == campaign.policy_artifact()["policy_hash"]
assert {r["gate_type"] for r in material["receipts"]} == {
    "campaign_eligibility",
    "judge_calibration",
    "formal_holdout",
    "harness_qualification",
}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
cd python
python -m pytest \
  tests/distributed/test_promotion_repository.py \
  tests/evals/test_rsi_campaign.py -q
```

Expected: missing repository and `qualification_material()` failures.

- [ ] **Step 3: Implement immutable registration**

`PromotionRepository.register_qualification(material, actor, command_id)`
must open one transaction, revalidate canonical hashes, insert the artifact and
receipts with PostgreSQL `ON CONFLICT DO NOTHING`, compare any existing body,
append an audit event, and create the first `registered` snapshot with stable
pointing to the current rehearsal stable policy:

```python
async def register_qualification(
    self,
    material: QualificationMaterial,
    *,
    actor: str,
    command_id: str,
) -> DeploymentSnapshot:
    ...
```

No caller may pass `passed=True` without the complete immutable receipt body.
The repository accepts only `data_role="holdout_validated"` and v3 Judge
protocol for candidate registration.

- [ ] **Step 4: Export qualification material from Campaign**

Add `Campaign.qualification_material()` after `verify_eligibility()`. Re-read
all evidence from disk, recompute receipt and artifact hashes, and return
Pydantic-valid material. Include the shared budget summary rather than a
caller-provided cost:

```python
{
    "schema_version": 1,
    "campaign_id": self.data["id"],
    "campaign_binding": self.binding,
    "artifact": self.policy_artifact(),
    "receipts": receipts,
    "budget": self.budget.summary(),
}
```

Do not change `PolicyRegistry`; it remains the explicit local-only compatibility
path until distributed promotion is enabled.

- [ ] **Step 5: Run tests and commit**

```bash
cd python
python -m pytest \
  tests/distributed/test_promotion_repository.py \
  tests/evals/test_rsi_campaign.py \
  tests/test_rsi_policy_runtime.py -q
```

Expected: all selected tests pass and simulated campaigns still cannot produce
qualification material.

```bash
git add python/core/distributed/promotion_repository.py \
  python/core/distributed/promotion_service.py \
  python/evals/optimization/campaign.py \
  python/tests
git commit -m "feat(policy): bind promotion to qualification evidence"
```

## Task 4: Implement the CAS-Protected Promotion State Machine

**Files:**
- Create: `python/core/distributed/promotion_cli.py`
- Modify: `python/core/distributed/promotion_repository.py`
- Modify: `python/core/distributed/promotion_service.py`
- Modify: `python/core/distributed/runtime.py`
- Modify: `python/tests/distributed/test_promotion_repository.py`

- [ ] **Step 1: Write failing transition, concurrency and audit tests**

Create tests for every allowed edge:

```text
registered -> shadow
shadow -> canary
canary -> active
registered|shadow|canary|active -> frozen
canary|active -> rolled_back
```

Assert all other edges fail. Add concurrent commands with the same
`expected_version`; exactly one must update the head. Assert repeated
`command_id` returns the original snapshot, a different payload with the same
ID conflicts, and missing gate receipts produce an immutable rejected audit
event without changing the head.

- [ ] **Step 2: Run the state-machine tests and verify failure**

```bash
cd python
python -m pytest \
  tests/distributed/test_promotion_repository.py \
  -k "transition or concurrent or audit or command" -q
```

Expected: transition methods are missing.

- [ ] **Step 3: Implement gate verification and transactional transitions**

Define required gates:

```python
REQUIRED_EXTERNAL_GATES = {
    DeploymentState.SHADOW: {
        "campaign_eligibility",
        "judge_calibration",
        "formal_holdout",
        "harness_qualification",
    },
    DeploymentState.CANARY: {"shadow_health"},
    DeploymentState.ACTIVE: {"canary_health"},
}
```

`PromotionCommandService.transition()` must lock
`policy_environment_heads`, compare `expected_version`, verify required
receipts against policy/protocol/runtime/source, insert a new immutable
snapshot, update the head with `WHERE current_version=:expected`, append an
audit event, and insert a deployment-change Outbox event in one transaction.
Candidate traffic is 0 for registered/shadow/frozen/rolled_back, bounded to
`1..9999` for canary, and 10000 for active.

`activate` also creates the `promotion_approval` receipt from the authenticated
command actor, nonempty reason, command ID and current canary-health binding in
that same transaction. The approval is evidence produced by the explicit
command, not a pre-existing receipt that would make activation circular.

- [ ] **Step 4: Add a separate write CLI**

Provide commands:

```text
register-campaign --campaign PATH --actor ID --command-id ID
start-shadow --environment rehearsal --expected-version N
start-canary --environment rehearsal --expected-version N --basis-points N
activate --environment rehearsal --expected-version N
freeze --environment rehearsal --expected-version N --reason TEXT
rollback --environment rehearsal --expected-version N --reason TEXT
issue-token --rehearsal-id ID --namespace NS --learner-id ID --request-id ID
            --operation learning_task --fault-profile PROFILE --ttl-seconds N
show-head --environment rehearsal
```

The CLI builds only the promotion command service. It must not start HTTP,
workers or Ops routes. Commands print canonical JSON without secrets or
artifact components. The sole exception is `issue-token`, which returns the
short-lived bearer token to stdout with the expected cohort for that exact
learner/request; it never logs or persists the token and never returns either
signing secret.

- [ ] **Step 5: Run CLI/state tests and commit**

```bash
cd python
python -m pytest \
  tests/distributed/test_promotion_repository.py \
  tests/distributed/test_promotion_contracts.py -q
python -m core.distributed.promotion_cli --help
```

Expected: tests pass and help lists all commands.

```bash
git add python/core/distributed/promotion_*.py python/tests/distributed
git commit -m "feat(policy): add audited promotion state machine"
```

## Task 5: Assign and Persist Policy at Run Admission

**Files:**
- Create: `python/core/distributed/policy_assignment.py`
- Create: `python/tests/distributed/test_policy_assignment.py`
- Modify: `python/core/distributed/models.py`
- Modify: `python/core/distributed/repository.py`
- Modify: `python/core/distributed/dispatcher.py`
- Modify: `python/core/distributed/broker.py`
- Modify: `python/core/distributed/runtime.py`
- Modify: `python/core/distributed/cli.py`
- Modify: `python/api/distributed_routes.py`
- Modify: `python/tests/distributed/test_api.py`
- Modify: `python/tests/distributed/helpers.py`

- [ ] **Step 1: Write failing token, HMAC and admission tests**

Use fixed secrets and timestamps. Cover:

- normal requests select the production stable snapshot;
- valid token selects rehearsal and consumes nonce once;
- expired, future, altered, wrong-operation, wrong learner/request, stale
  deployment version and reused tokens are rejected;
- unknown fault profiles and fault injection while disabled are rejected;
- a signed fault profile can affect only a candidate rehearsal Run and is
  persisted for audit;
- HMAC fixed vectors map to exact buckets;
- bucket below basis points selects candidate, equality selects stable;
- repeated `(learner_id, request_id)` returns the original assignment without
  consuming a second token;
- concurrent identical admission creates one Run and one nonce consumption;
- conflicting input remains HTTP 409;
- missing, tampered or runtime-incompatible selected artifacts fail admission
  and freeze the still-current rehearsal deployment exactly once;
- unavailable PostgreSQL returns 503 rather than an unpersisted cached choice.

The fixed vector assertion must use:

```python
bucket = assignment_bucket(
    secret=b"a" * 32,
    environment="rehearsal",
    deployment_id="11111111-1111-1111-1111-111111111111",
    learner_id="student",
    request_id="request-1",
)
assert bucket == 4512
```

The assignment message is the UTF-8 values joined with one NUL byte in this
exact order. The expected value is the first eight HMAC digest bytes decoded
as an unsigned big-endian integer modulo 10000.

- [ ] **Step 2: Run tests and verify failure**

```bash
cd python
python -m pytest \
  tests/distributed/test_policy_assignment.py \
  tests/distributed/test_api.py -q
```

Expected: missing assignment module and header behavior.

- [ ] **Step 3: Implement signed token and deterministic assignment**

Use URL-safe base64 payload plus HMAC-SHA256:

```python
message = canonical_json({
    "rehearsal_id": claims.rehearsal_id,
    "namespace": claims.namespace,
    "deployment_id": claims.deployment_id,
    "deployment_version": claims.deployment_version,
    "learner_id": claims.learner_id,
    "request_id": claims.request_id,
    "operations": claims.operations,
    "nonce": claims.nonce,
    "issued_at": claims.issued_at,
    "expires_at": claims.expires_at,
    "fault_profile": claims.fault_profile,
})
signature = hmac.new(secret, message, hashlib.sha256).digest()
```

Store only `sha256(nonce)` and `sha256(assignment input)`. Compare signatures
with `hmac.compare_digest`. Derive the bucket from the first eight digest bytes
as unsigned big-endian modulo 10000:

```python
message = b"\x00".join(
    value.encode("utf-8")
    for value in (environment, deployment_id, learner_id, request_id)
)
digest = hmac.new(secret, message, hashlib.sha256).digest()
bucket = int.from_bytes(digest[:8], "big", signed=False) % 10000
```

Never log token, nonce, assignment secret, or raw assignment key.

`fault_profile` is one of `none`, `latency`, or `commit_failure`. It defaults
to `none`; non-none values require `promotion_fault_injection_enabled=true`
and are cleared to `none` for stable assignments even if the signed request
would otherwise land in the stable cohort.

- [ ] **Step 4: Make assignment part of the admission transaction**

Change:

```python
async def accept_with_replay(
    self,
    spec: DistributedRunRequest,
    *,
    rehearsal_token: str | None = None,
) -> tuple[DistributedRun, bool]:
```

Inside the transaction acquire an advisory lock derived from learner/request,
look up an existing Run first, and only for a new Run consume the nonce, lock
the environment head, compute the assignment, validate the selected artifact,
insert all fixed fields, lease and Outbox. Add `PolicyExecutionBinding` to
`RunClaim`; `_claim_from()` must copy persisted fields rather than resolving
the current head again. Production admission writes `run.accepted`; rehearsal
admission writes `run.rehearsal.accepted`.

Read `X-EduAgent-Rehearsal` in `submit_run()`. Map token failures to 401,
expired/replayed nonce to 409, missing/incompatible artifacts to 503, and
database failures to a retryable 503.

If selected artifact validation fails, call `freeze_if_current()` with the
locked deployment ID/version before returning 503. The freeze is idempotent
and may not affect a newer head.

- [ ] **Step 5: Run tests and commit**

```bash
cd python
python -m pytest \
  tests/distributed/test_policy_assignment.py \
  tests/distributed/test_repository.py \
  tests/distributed/test_api.py -q
```

Expected: all pass; replay tests assert byte-for-byte identical bindings.

```bash
git add python/core/distributed python/api/distributed_routes.py python/tests
git commit -m "feat(policy): pin policy during run admission"
```

## Task 6: Propagate the Binding Through Workers, Harness, and Experts

**Files:**
- Create: `python/core/distributed/rehearsal_store.py`
- Create: `python/tests/distributed/test_policy_pinning.py`
- Modify: `python/core/distributed/worker.py`
- Modify: `python/core/distributed/dispatcher.py`
- Modify: `python/core/distributed/runtime.py`
- Modify: `python/core/distributed/cli.py`
- Modify: `python/core/distributed/executor.py`
- Modify: `python/core/distributed/expert_contracts.py`
- Modify: `python/core/distributed/expert_models.py`
- Modify: `python/core/distributed/expert_repository.py`
- Modify: `python/core/run_context.py`
- Modify: `python/core/harness.py`
- Modify: `python/core/specialist_runtime.py`
- Modify: `python/tests/distributed/test_worker.py`
- Modify: `python/tests/distributed/test_expert_repository.py`

- [ ] **Step 1: Write failing inheritance and isolation tests**

Cover:

- first attempt and lease takeover receive the same deployment, policy,
  components, cohort and namespace;
- worker passes that binding to the executor;
- harness uses the pinned components even if the environment head changes;
- pending quiz/plan policy conflict still returns 409 rather than switching;
- expert snapshot and job match parent deployment, policy and namespace;
- forged expert binding is rejected before enqueue;
- production Run Workers reject rehearsal messages and Rehearsal Workers
  reject production messages;
- Outbox dispatch routes each environment to its dedicated Redis stream;
- production namespace resolves only the configured production store;
- rehearsal namespace rejects traversal, separators, Unicode confusables and
  paths outside the configured root.

Use an executor spy:

```python
class BindingExecutor:
    def __init__(self):
        self.bindings = []

    async def execute(self, spec, authority, binding):
        self.bindings.append(binding)
        return {"ok": True}
```

- [ ] **Step 2: Run tests and verify failure**

```bash
cd python
python -m pytest \
  tests/distributed/test_policy_pinning.py \
  tests/distributed/test_worker.py \
  tests/distributed/test_expert_repository.py -q
```

Expected: executor signature and binding assertions fail.

- [ ] **Step 3: Pass the persisted binding into business execution**

Change `RunExecutor.execute()` and `LearningTaskExecutor.execute()` to receive
`PolicyExecutionBinding`. Extend `RunExecutionAuthority` with
`deployment_id`, `effective_policy_hash`, `policy_cohort`,
`state_namespace`, and `rehearsal_id`; worker values must come from
`RunClaim.binding`.

`LearningHarness` accepts `pinned_policy` and `state_namespace`. Its
`resolve_policy()` first validates any pending quiz/plan pins against the
trusted binding, then returns the persisted policy components. It may use
`PolicyRegistry` only when no distributed binding exists.

- [ ] **Step 4: Route rehearsal state to an isolated store**

Implement:

```python
NAMESPACE = re.compile(r"^rehearsal-[a-z0-9][a-z0-9-]{0,62}$")

class RehearsalStoreRouter:
    def path_for(self, binding: PolicyExecutionBinding) -> Path:
        if binding.state_namespace == "production":
            return self.production_path
        if not NAMESPACE.fullmatch(binding.state_namespace):
            raise ValueError("invalid rehearsal namespace")
        candidate = (self.rehearsal_root / binding.state_namespace / "harness.sqlite3").resolve()
        candidate.relative_to(self.rehearsal_root.resolve())
        candidate.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return candidate
```

The path is server-derived and never copied from request payload. Add the
namespace and deployment to RunContext trace metadata.

- [ ] **Step 5: Separate production and rehearsal worker capabilities**

Extend `OutboxDispatcher` with a fixed topic-to-broker map. Build a dedicated
rehearsal broker and add `rehearsal-worker` to the CLI. Worker construction
must receive `allowed_environment`; before claim/execution it verifies the
persisted binding matches that capability. Compose rehearsal workers mount
only `promotion_rehearsal_store_root`; ordinary Run Workers do not mount it.
Both paths retain PostgreSQL leases and fencing, so two Rehearsal Workers can
take over the same expired Run without changing its binding.

- [ ] **Step 6: Revalidate expert inheritance**

Add deployment and namespace fields to `ExpertSnapshot` and persisted expert
jobs. In `create_or_replay()`, compare request values to the locked parent Run:

```python
if (
    request.snapshot.effective_policy_hash != run.effective_policy_hash
    or request.snapshot.deployment_id != run.deployment_id
    or request.snapshot.state_namespace != run.state_namespace
):
    raise ExpertFencingViolation("expert policy binding differs from parent")
```

Keep the existing parent fencing, learner, deadline and source checks.

- [ ] **Step 7: Run tests and commit**

```bash
cd python
python -m pytest \
  tests/distributed/test_policy_pinning.py \
  tests/distributed/test_worker.py \
  tests/distributed/test_expert_repository.py \
  tests/test_learning_harness.py \
  tests/test_rsi_policy_runtime.py -q
```

Expected: all pass, including takeover after changing the current deployment.

```bash
git add python/core python/tests
git commit -m "feat(policy): inherit trusted binding through execution"
```

## Task 7: Add Durable, Commit-Isolated Shadow Execution

**Files:**
- Create: `python/core/distributed/shadow_worker.py`
- Create: `python/tests/distributed/test_shadow_worker.py`
- Modify: `python/core/distributed/promotion_models.py`
- Modify: `python/core/distributed/promotion_repository.py`
- Modify: `python/core/distributed/rehearsal_store.py`
- Modify: `python/core/distributed/runtime.py`
- Modify: `python/core/distributed/cli.py`
- Modify: `python/core/distributed/repository.py`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Write failing Shadow job tests**

Cover:

- accepting a primary Run under a Shadow deployment creates exactly one
  `(parent_run_id, deployment_id)` shadow execution after primary completion;
- Redis/outbox duplication does not duplicate execution rows;
- claim increments a shadow fencing token and expired work is reclaimable;
- candidate uses the frozen parent payload and candidate policy;
- candidate writes only to
  `rehearsal_root/shadow/<deployment>/<parent-run>/harness.sqlite3`;
- primary result and learner store are unchanged by Shadow success/failure;
- stale worker cannot complete a reclaimed Shadow job;
- raw student content and model output are not copied into observations.

- [ ] **Step 2: Run tests and verify failure**

```bash
cd python
python -m pytest tests/distributed/test_shadow_worker.py -q
```

Expected: missing worker and repository methods.

- [ ] **Step 3: Implement PostgreSQL-authoritative Shadow jobs**

`policy_shadow_executions` contains parent Run, deployment, candidate policy,
input hash, status, attempt count, fencing token, owner, lease expiry, usage
summary, error code and timestamps. Add repository methods:

```python
async def enqueue_shadow(self, parent_run_id: str) -> ShadowExecution
async def claim_shadow(self, worker_id: str, lease_seconds: float) -> ShadowClaim | None
async def renew_shadow(self, shadow_id: str, worker_id: str, token: int, lease_seconds: float) -> None
async def complete_shadow(self, shadow_id: str, worker_id: str, token: int, summary: dict) -> None
async def fail_shadow(self, shadow_id: str, worker_id: str, token: int, error_code: str) -> None
async def reap_shadow(self, now: datetime) -> list[str]
```

Use `FOR UPDATE SKIP LOCKED`; PostgreSQL is authoritative, while a lightweight
Redis notification may wake workers. A completed primary Run enqueues Shadow
only when its persisted deployment state was `shadow`.

- [ ] **Step 4: Execute candidate in a disposable isolated store**

`ShadowWorker` loads the frozen parent request and candidate artifact, builds
a binding with cohort `shadow` and namespace
`shadow-<deployment-id>-<run-id>`, executes through `LearningTaskExecutor`,
records only status/latency/token/cost/count diagnostics, and removes the
temporary store after the observation transaction succeeds. The process must
not receive the production harness path.

Add CLI commands `shadow-worker` and `shadow-reaper`, plus Compose services
whose volume is mounted at `/app/shadow` only.

- [ ] **Step 5: Run tests and commit**

```bash
cd python
python -m pytest \
  tests/distributed/test_shadow_worker.py \
  tests/distributed/test_worker.py \
  tests/distributed/test_repository.py -q
docker compose --profile distributed config >/tmp/eduagent-m3-compose.yml
```

Expected: tests pass and Compose shows no production harness volume on the
Shadow worker.

```bash
git add python/core/distributed python/tests/distributed docker-compose.yml
git commit -m "feat(policy): add isolated durable shadow execution"
```

## Task 8: Record Deterministic Health Windows and Roll Back Transactionally

**Files:**
- Create: `python/core/distributed/policy_health.py`
- Create: `python/tests/distributed/test_policy_health.py`
- Modify: `python/core/distributed/promotion_repository.py`
- Modify: `python/core/distributed/promotion_service.py`
- Modify: `python/core/distributed/worker.py`
- Modify: `python/core/distributed/shadow_worker.py`
- Modify: `python/core/distributed/runtime.py`
- Modify: `python/core/distributed/cli.py`
- Modify: `python/core/distributed/metrics.py`

- [ ] **Step 1: Write failing observation and health tests**

Cover:

- observation key is the canonical JSON hash of
  `{run_id, deployment_id, cohort, metric_contract_version}` so
  paired stable/Shadow observations coexist while duplicate terminal
  notifications remain idempotent;
- retries create one terminal observation, not one per attempt;
- candidate and stable require at least 20 matching Runs;
- baseline shortage yields `hold`;
- nearest-rank p95 and Decimal cost calculations are deterministic;
- rate equal to threshold fails, below threshold passes;
- one confirmed permission violation immediately fails;
- two evaluators create one frozen window and one rollback;
- a late sample for the old deployment cannot move the new head;
- rollback keeps old Runs pinned and sends new Runs to stable.
- injected failures are stored as injected and never reported as naturally
  observed policy failures.

Use 20 candidate and 20 stable fixtures with explicit Decimal costs and
timestamps; never use random values.

- [ ] **Step 2: Run tests and verify failure**

```bash
cd python
python -m pytest tests/distributed/test_policy_health.py -q
```

Expected: health evaluator and observation methods are missing.

- [ ] **Step 3: Record redacted terminal observations**

After a Run becomes terminal, call
`PolicyObservationRecorder.record_run(run_id)`. Derive status, latency and
commit outcome from PostgreSQL; aggregate token/cost from accepted expert
results; store counts for structured decisions and unknown decisions. The
recorder accepts no caller-provided policy/cohort/namespace values.

Allowed outcome values:

```python
{"completed", "commit_failed", "terminal_failed", "exhausted",
 "confirmed_permission_violation"}
```

Permission violation requires a server-generated diagnostic code; tool denial
alone is not a confirmed violation.

For a candidate Run with a signed fault profile, the worker sleeps the frozen
injected latency or raises `RehearsalInjectedCommitFailure` immediately before
the commit transition. The recorder maps that code to `commit_failed` and
sets `fault_injected=true`; no unsigned or stable Run can enter this branch.

- [ ] **Step 4: Implement deterministic evaluator and rollback**

For a Shadow deployment, compare `cohort=shadow` observations with the stable
primary observations from the same parent Runs. For Canary/Active, compare
`cohort=candidate` with stable observations from the same rehearsal, operation
distribution and metric contract. Sort evaluated observations by
`(observed_at, observation_key)`, take the last `window_max_runs`, and compute
rates with `Decimal`. Use:

```python
def nearest_rank(values: list[Decimal], percentile: Decimal) -> Decimal:
    ordered = sorted(values)
    rank = max(1, math.ceil(len(ordered) * percentile))
    return ordered[rank - 1]
```

Persist the exact observation keys, aggregates, threshold hash and decision.
For `fail`, call `rollback_if_current()` in the same transaction: advisory-lock
environment, lock head, verify deployment/version/window, insert immutable
`rolled_back` snapshot with candidate traffic 0, CAS-update head, append audit
and Outbox. For `pass`, issue a `shadow_health` or `canary_health` receipt.
For `hold`, write the window but issue no gate.

- [ ] **Step 5: Add health process and metrics**

Add CLI process `policy-health` that polls only when promotion is enabled.
Add bounded-label metrics:

```text
eduagent_policy_assignments_total{environment,cohort}
eduagent_policy_gate_decisions_total{gate,status}
eduagent_policy_health_decisions_total{environment,decision}
eduagent_policy_rollbacks_total{environment,trigger}
eduagent_policy_observation_latency_seconds{cohort}
eduagent_policy_observation_cost_usd{cohort}
```

Labels must never include learner, request, run, deployment or policy hashes.

- [ ] **Step 6: Run tests and commit**

```bash
cd python
python -m pytest \
  tests/distributed/test_policy_health.py \
  tests/distributed/test_instrumentation.py \
  tests/distributed/test_worker.py -q
```

Expected: all pass, including concurrent evaluator and late-sample cases.

```bash
git add python/core/distributed python/tests/distributed
git commit -m "feat(policy): add health gates and transactional rollback"
```

## Task 9: Expose Read-Only Promotion Evidence in Ops

**Files:**
- Modify: `python/core/distributed/ops_contracts.py`
- Modify: `python/core/distributed/ops_queries.py`
- Modify: `python/api/ops_routes.py`
- Create: `python/tests/distributed/test_promotion_ops_api.py`
- Modify: `frontend/src/ops/types.ts`
- Modify: `frontend/src/ops/api.ts`
- Create: `frontend/src/ops/PoliciesView.tsx`
- Modify: `frontend/src/ops/OpsApp.tsx`
- Modify: `frontend/src/ops/ops.css`
- Modify: `frontend/e2e/ops.spec.ts`

- [ ] **Step 1: Write failing bounded/read-only API tests**

Add endpoints:

```text
GET /ops/policies/deployments
GET /ops/policies/deployments/{deployment_id}
GET /ops/policies/health-windows
GET /ops/policies/audit
```

Test cursor pagination, `limit <= 100`, allow-listed environment/state filters,
invalid cursor/filter rejection, missing rows, auth reuse, and strict response
models. Assert no endpoint accepts POST/PUT/PATCH/DELETE and responses exclude
artifact components, token/nonce, learner/request IDs, raw prompts, raw model
outputs and secrets.

- [ ] **Step 2: Run API tests and verify failure**

```bash
cd python
python -m pytest \
  tests/distributed/test_promotion_ops_api.py \
  tests/distributed/test_ops_api.py -q
```

Expected: 404 for new endpoints.

- [ ] **Step 3: Implement redacted projections**

Add `OpsPolicyDeployment`, `OpsGateReceipt`, `OpsHealthWindow`,
`OpsAuditEvent`, page and detail models. Include deployment ID, truncated
policy hash for compact lists, full policy hash in detail, state, version,
cohort counts, thresholds, gate status, metric
aggregates, actor, reason and timestamps. Keep query methods in
`OpsQueries`; they open read-only sessions and never call
`PromotionCommandService`.

Extend existing Run summary/detail and Trace projections with deployment ID,
cohort, namespace class (`production` or `rehearsal`, never the raw namespace)
and full effective policy hash so one Run can be correlated across the
promotion timeline without exposing learner data.

- [ ] **Step 4: Build the Policies view**

Add a compact table/timeline view with:

- environment and state filters;
- current deployment, stable/candidate hashes and traffic percentage;
- gate receipt statuses;
- latest health window with candidate vs stable metrics;
- rollback/freeze audit timeline.

Use existing Ant Design and Ops layout patterns. Add a shield-check icon for
Policies, status icons with tooltips, no nested cards, and responsive table
overflow. Do not add mutation buttons.

- [ ] **Step 5: Run backend and frontend verification**

```bash
cd python
python -m pytest \
  tests/distributed/test_promotion_ops_api.py \
  tests/distributed/test_ops_api.py -q
cd ../frontend
npm run build
npx playwright test e2e/ops.spec.ts
```

Expected: backend tests, production build and desktop/mobile Ops tests pass.

- [ ] **Step 6: Commit Ops evidence surface**

```bash
git add python/core/distributed/ops_* python/api/ops_routes.py \
  python/tests/distributed/test_promotion_ops_api.py frontend
git commit -m "feat(ops): expose trusted promotion evidence"
```

## Task 10: Run the Controlled Rehearsal and Publish Verifiable Evidence

**Files:**
- Create: `python/tests/integration/test_policy_promotion.py`
- Create: `tools/run_policy_rehearsal.py`
- Create: `docs/engineering/trusted-policy-promotion.md`
- Create: `docs/engineering/m3-policy-promotion-acceptance.md`
- Modify: `docker-compose.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `.gitignore`

- [ ] **Step 1: Write the real infrastructure integration test**

The test must use real PostgreSQL and Redis with two Rehearsal Run Workers,
one Shadow Worker and one health evaluator. Cover:

1. register a test-bound candidate and complete required test receipts;
2. start Shadow and prove candidate cannot alter primary result/state;
3. start 50/50 Canary and submit fixed requests until both cohorts have at
   least 20 matching Runs;
4. kill one Run Worker after claim and prove takeover retains the policy;
5. inject candidate commit failures at the frozen threshold;
6. observe automatic rollback;
7. prove an already accepted candidate Run remains candidate and a newly
   accepted Run becomes stable;
8. submit a late old-deployment observation and prove the head is unchanged.

Test-only receipts must be inserted by a fixture repository helper that is not
exported by runtime or CLI. Mark every generated integration artifact
`evidence_role="test_fixture"` and `release_eligible=false`.

- [ ] **Step 2: Run the integration test and verify initial failure**

```bash
cd python
DISTRIBUTED_TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent \
DISTRIBUTED_TEST_REDIS_URL=redis://localhost:6379/15 \
python -m pytest tests/integration/test_policy_promotion.py -q
```

Expected before final wiring: failure at the first missing process or
observation assertion.

- [ ] **Step 3: Implement the controlled rehearsal driver**

`tools/run_policy_rehearsal.py` accepts:

```text
--api-url
--ops-token
--campaign PATH
--actor
--candidate-basis-points
--healthy-runs
--failure-runs
--output DIR
```

It must refuse a simulation/exploratory campaign, use the write CLI for
registration/transitions, issue short-lived one-use tokens, submit fixed
synthetic learner requests sequentially, poll PostgreSQL-backed status/Ops,
inject only an explicit rehearsal failure mode, wait for rollback, and write:

```text
manifest.json
requests.jsonl
gate_receipts.jsonl
health_windows.jsonl
audit_timeline.jsonl
prometheus.txt
summary.md
```

The driver passes each token directly in memory to one HTTP request, redacts
subprocess stdout after parsing, and never writes bearer tokens or nonce
plaintext to any artifact.

Every artifact includes source revision, runtime/protocol/threshold hashes,
provider/model identity, data role, request/failed/interrupted counts and
cost. `summary.md` must contain:

```text
This is controlled rehearsal traffic, not production student traffic.
Operational guardrails do not establish learning-effect improvement.
```

- [ ] **Step 4: Add Compose processes and CI gates**

Add two Rehearsal Run Workers, Shadow worker/reaper and policy-health services
under the distributed profile. Rehearsal and Shadow processes get dedicated
volumes and no production harness mount; production Run Workers do not get
the rehearsal mount. Source secrets from environment and do not put secret
defaults in committed Compose. Extend integration CI with
`test_policy_promotion.py`; extend compose smoke with a fixture-only promotion
scenario whose artifact is uploaded and explicitly non-release-eligible.

Add secret scanning assertions for token/assignment secrets and raw rehearsal
tokens. Archive JUnit and rehearsal JSON even on failure.

- [ ] **Step 5: Document the protocol and interview walkthrough**

`docs/engineering/trusted-policy-promotion.md` must include:

- state and data-flow diagrams;
- table/invariant summary;
- Judge unknown and one-repair semantics;
- assignment formula and version inheritance;
- Shadow/Canary isolation;
- health formulas and rollback transaction;
- failure matrix;
- exact local/CI/formal-rehearsal commands;
- evidence field guide;
- explicit current limitations and non-claims.

Update README with a five-minute Harness walkthrough and an Agent-algorithm
walkthrough, both linking to evidence rather than quoting unverified metrics.

- [ ] **Step 6: Run the complete verification matrix**

```bash
cd python
python -m pytest tests -q -m "not distributed_integration"
python -m pytest \
  tests/distributed \
  tests/integration/test_distributed_failover.py \
  tests/integration/test_expert_failover.py \
  tests/integration/test_policy_promotion.py \
  --junitxml=/tmp/eduagent-m3-junit.xml -q
cd ../frontend
npm run build
npx playwright test e2e/ops.spec.ts
cd ..
docker compose --profile distributed config >/tmp/eduagent-m3-compose.yml
git diff --check
```

Expected: all test suites and builds pass; JUnit contains no failure/error;
Compose config includes all M3 processes without literal secrets; worktree
contains only intended evidence/docs changes.

- [ ] **Step 7: Run a formal rehearsal or record the external prerequisite**

When a real eligible campaign and configured model credentials are available:

```bash
python tools/run_policy_rehearsal.py \
  --api-url http://127.0.0.1:8890 \
  --ops-token "$OPS_API_TOKEN" \
  --campaign "$ELIGIBLE_CAMPAIGN" \
  --actor interview-rehearsal \
  --candidate-basis-points 5000 \
  --healthy-runs 48 \
  --failure-runs 20 \
  --output docs/engineering/evidence/m3-policy-rehearsal
```

Expected: `summary.md` reports a healthy window followed by one automatic
rollback and distinguishes actual model evidence from fixture-only CI
evidence. If qualification or credentials are unavailable, do not fabricate
receipts; commit the passing implementation/test evidence and record the exact
missing prerequisite, attempted command, timestamp and completed test evidence
in `docs/engineering/m3-policy-promotion-acceptance.md`.

- [ ] **Step 8: Commit implementation evidence**

```bash
git add .github/workflows/ci.yml .gitignore README.md docker-compose.yml \
  python tools/run_policy_rehearsal.py docs/engineering/trusted-policy-promotion.md \
  docs/engineering/m3-policy-promotion-acceptance.md
test ! -d docs/engineering/evidence/m3-policy-rehearsal || \
  git add docs/engineering/evidence/m3-policy-rehearsal
git commit -m "test(policy): publish controlled promotion evidence"
```

## Completion Audit

Before calling M3 complete, inspect current evidence against every design
acceptance item:

| Design requirement | Required evidence |
| --- | --- |
| PostgreSQL is publication authority | M3 tables, constraints, head CAS tests, no distributed file pointer reads |
| Run assignment is immutable | admission transaction, replay/takeover/expert inheritance tests |
| Judge v3 fails closed | schema/consistency/repair/unknown fixtures and calibration replay |
| Gates cannot be bypassed | transition rejection tests and immutable audit events |
| Controlled traffic is isolated | signed token, nonce, stream routing, worker capability, namespace/path tests and mount inspection |
| Health is deterministic | frozen observation keys, Decimal calculations and exact window replay |
| Rollback is race-safe | two-evaluator, late-sample and old/new Run integration evidence |
| Evidence is observable | Prometheus snapshot, Trace IDs, Ops projection and exported timeline |
| Claims are honest | release eligibility/data role/cost/failure fields and non-claim text |
| Delivery remains healthy | full backend, distributed, frontend, Compose and CI results |

Do not mark the project goal complete merely because M3 passes. Re-run the
broader interview-readiness audit from the root objective: current architecture
docs, reproducible demos, evidence links, README, failure analysis, cost
accounting, and both Harness/Agent-algorithm interview narratives must all
match the final code and evidence.
