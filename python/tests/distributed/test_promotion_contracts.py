from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from config.settings import Settings
from core.distributed.promotion_contracts import (
    DeploymentSnapshot,
    DeploymentState,
    GateReceipt,
    HealthDecision,
    PolicyArtifact,
    PolicyComponents,
    PolicyExecutionBinding,
    PolicyObservation,
    PolicyThresholds,
    PromotionCommand,
    RehearsalClaims,
)

HASH = "a" * 64
OTHER_HASH = "b" * 64
DEPLOYMENT_ID = UUID("11111111-1111-1111-1111-111111111111")
NOW = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)


def test_deployment_states_and_transitions_are_strict():
    assert [state.value for state in DeploymentState] == [
        "registered",
        "shadow",
        "canary",
        "active",
        "frozen",
        "rolled_back",
    ]
    assert DeploymentState.REGISTERED.can_transition_to(DeploymentState.SHADOW)
    assert DeploymentState.CANARY.can_transition_to(
        DeploymentState.ROLLED_BACK
    )
    assert not DeploymentState.REGISTERED.can_transition_to(
        DeploymentState.ACTIVE
    )
    assert not DeploymentState.ROLLED_BACK.can_transition_to(
        DeploymentState.CANARY
    )


def test_threshold_defaults_are_frozen_and_have_stable_digest():
    thresholds = PolicyThresholds()
    assert thresholds.model_dump(mode="json") == {
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
    assert len(thresholds.digest) == 64
    assert thresholds.digest == PolicyThresholds().digest
    with pytest.raises(ValidationError, match="frozen"):
        thresholds.commit_failure_rate = Decimal("0.01")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        PolicyThresholds(undocumented=True)


@pytest.mark.parametrize("traffic", [-1, 10001])
def test_deployment_rejects_traffic_outside_basis_point_range(traffic):
    with pytest.raises(ValidationError):
        deployment(traffic_basis_points=traffic)


def test_contracts_require_utc_timestamps_and_sha256_fields():
    with pytest.raises(ValidationError, match="aware UTC"):
        artifact(created_at=NOW.replace(tzinfo=None))
    with pytest.raises(ValidationError, match="aware UTC"):
        receipt(issued_at=NOW.astimezone(tz=None))
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        artifact(policy_hash="not-a-hash")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        observation(unknown=True)


def test_execution_binding_is_frozen_and_bounded():
    binding = PolicyExecutionBinding(
        deployment_id=DEPLOYMENT_ID,
        environment="rehearsal",
        effective_policy_hash=HASH,
        components=PolicyComponents(retrieval_rules="prefer verified sources"),
        policy_cohort="candidate",
        assignment_key_hash=OTHER_HASH,
        assignment_reason="canary_bucket",
        state_namespace="rehearsal:demo",
        rehearsal_id="demo",
    )
    assert binding.rehearsal_fault_profile == "none"
    with pytest.raises(ValidationError, match="frozen"):
        binding.policy_cohort = "stable"


def test_all_promotion_contract_shapes_validate():
    values = [
        artifact(),
        receipt(),
        deployment(),
        PromotionCommand(
            command_id="command-1",
            environment="rehearsal",
            expected_version=1,
            current_state="registered",
            target_state="shadow",
            traffic_basis_points=0,
            actor="operator",
            reason="qualification passed",
        ),
        observation(),
        HealthDecision(
            decision="hold",
            reasons=["stable sample is incomplete"],
            candidate_run_count=20,
            stable_run_count=10,
            evaluated_at=NOW,
        ),
        RehearsalClaims(
            rehearsal_id="demo",
            deployment_id=DEPLOYMENT_ID,
            deployment_version=1,
            learner_id="student",
            request_id="request-1",
            operation="learning_task",
            state_namespace="rehearsal:demo",
            allowed_operations=["learning_task"],
            fault_profile="none",
            nonce="nonce-1",
            issued_at=NOW,
            expires_at=NOW + timedelta(minutes=5),
        ),
    ]
    assert all(value.model_config["frozen"] for value in values)

    with pytest.raises(ValidationError, match="invalid deployment transition"):
        PromotionCommand(
            command_id="command-2",
            environment="rehearsal",
            expected_version=1,
            current_state="registered",
            target_state="active",
            traffic_basis_points=10000,
            actor="operator",
            reason="skip gates",
        )


def test_promotion_settings_require_distributed_mode_and_redacted_secrets():
    with pytest.raises(ValidationError, match="distributed run plane"):
        Settings(
            _env_file=None,
            promotion_enabled=True,
            promotion_rehearsal_secret="r" * 32,
            promotion_assignment_secret="a" * 32,
        )

    secret = "secret-that-must-never-appear"
    with pytest.raises(ValidationError) as error:
        Settings(
            _env_file=None,
            distributed_enabled=True,
            promotion_enabled=True,
            promotion_rehearsal_secret=secret,
            promotion_assignment_secret="short",
        )
    assert secret not in str(error.value)
    assert "short" not in str(error.value)

    settings = Settings(
        _env_file=None,
        distributed_enabled=True,
        promotion_enabled=True,
        promotion_rehearsal_secret="r" * 32,
        promotion_assignment_secret="a" * 32,
    )
    assert settings.promotion_rehearsal_secret.get_secret_value() == "r" * 32


def artifact(**updates):
    value = {
        "policy_hash": HASH,
        "parent_policy_hash": None,
        "components": PolicyComponents(retrieval_rules="builtin"),
        "fixed_components_hash": OTHER_HASH,
        "runtime_hash": HASH,
        "source_revision": "revision-1",
        "protocol_hash": OTHER_HASH,
        "proposer_hash": HASH,
        "data_role": "builtin",
        "evidence_bindings": {},
        "created_at": NOW,
    }
    value.update(updates)
    return PolicyArtifact.model_validate(value)


def receipt(**updates):
    value = {
        "receipt_id": UUID("22222222-2222-2222-2222-222222222222"),
        "policy_hash": HASH,
        "gate_type": "artifact_integrity",
        "status": "passed",
        "evidence_hash": OTHER_HASH,
        "protocol_hash": HASH,
        "runtime_hash": OTHER_HASH,
        "source_revision": "revision-1",
        "model_identity": "deterministic",
        "data_role": "builtin",
        "sample_count": 1,
        "cost": Decimal("0"),
        "details": {},
        "issued_at": NOW,
        "issuer": "system",
    }
    value.update(updates)
    return GateReceipt.model_validate(value)


def deployment(**updates):
    value = {
        "deployment_id": DEPLOYMENT_ID,
        "environment": "rehearsal",
        "version": 1,
        "state": "registered",
        "candidate_policy_hash": None,
        "stable_policy_hash": HASH,
        "previous_stable_deployment_id": None,
        "traffic_basis_points": 0,
        "assignment_salt_id": "builtin",
        "thresholds": PolicyThresholds(),
        "required_receipts": [],
        "command_id": "bootstrap-rehearsal",
        "reason": "bootstrap",
        "actor": "system",
        "created_at": NOW,
    }
    value.update(updates)
    return DeploymentSnapshot.model_validate(value)


def observation(**updates):
    value = {
        "observation_key": HASH,
        "run_id": UUID("33333333-3333-3333-3333-333333333333"),
        "deployment_id": DEPLOYMENT_ID,
        "policy_hash": OTHER_HASH,
        "cohort": "candidate",
        "state_namespace": "rehearsal:demo",
        "metric_contract_version": 1,
        "terminal_status": "completed",
        "latency_seconds": Decimal("1.25"),
        "input_tokens": 10,
        "output_tokens": 5,
        "cost": Decimal("0.01"),
        "commit_outcome": "succeeded",
        "permission_outcome": "allowed",
        "structured_result": "valid",
        "injected": False,
        "observed_at": NOW,
        "source_trace_id": "c" * 32,
    }
    value.update(updates)
    return PolicyObservation.model_validate(value)
