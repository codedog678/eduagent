import asyncio
import copy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.distributed.contracts import canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord,
    PolicyAuditEventRecord,
    PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord,
    PolicyGateReceiptRecord,
    RehearsalTokenNonceRecord,
)
from core.distributed.promotion_repository import (
    ImmutablePromotionConflict,
    PromotionRepository,
    QualificationRejected,
)
from core.distributed.promotion_service import (
    QualificationBudget,
    QualificationMaterial,
)
from evals.live_budget import PRICING
from evals.optimization.scoring import judge_protocol_digest

pytestmark = pytest.mark.distributed_integration

NOW = datetime(2026, 10, 30, 8, 0, tzinfo=UTC)
STABLE_HASH = "a" * 64
PROTOCOL_HASH = canonical_hash({"judge_protocol_version": 3})
RUNTIME_HASH = canonical_hash({"runtime": "qualified"})
FIXED_HASH = canonical_hash({"fixed": "components"})
PROPOSER_HASH = canonical_hash({"proposer": "gepa"})
REQUIRED_GATES = (
    "campaign_eligibility",
    "judge_calibration",
    "formal_holdout",
    "harness_qualification",
)


def qualification_material() -> QualificationMaterial:
    artifact_body = {
        "schema_version": 1,
        "parent_policy_hash": STABLE_HASH,
        "components": {"retrieval_rules": "先检索证据，再核对来源。"},
        "fixed_components_hash": FIXED_HASH,
        "runtime_hash": RUNTIME_HASH,
        "source_revision": "revision-qualified",
        "protocol_hash": PROTOCOL_HASH,
        "proposer_hash": PROPOSER_HASH,
        "data_role": "holdout_validated",
        "evidence_paths": {
            "campaign": "/tmp/qualified-campaign",
            "dev": "1" * 64,
            "holdout": "2" * 64,
            "harness": "3" * 64,
        },
        "created_at": NOW.isoformat(),
    }
    policy_hash = canonical_hash(artifact_body)
    budget = QualificationBudget.model_validate(
        {
            "max_requests": 1200,
            "max_cny": 10.0,
            "requests": 80,
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 200,
                "prompt_cache_hit_tokens": 300,
            },
            "estimated_peak_cny": 1.25,
            "estimated_off_peak_cny": 0.625,
            "unconfirmed_reservation_cny": 0.0,
            "billing_status": "estimate_only",
            "pricing": PRICING,
            "pricing_note": (
                "Default Flash rates; per-request pricing overrides apply "
                "when present."
            ),
            "roles": {"task": 40, "judge": 36, "reflection": 4},
        }
    ).model_dump(mode="json")
    receipts = []
    for index, gate_type in enumerate(REQUIRED_GATES, start=1):
        receipts.append(
            {
                "receipt_id": UUID(int=index),
                "policy_hash": policy_hash,
                "gate_type": gate_type,
                "status": "passed",
                "evidence_hash": canonical_hash(
                    {"gate": gate_type, "campaign": "campaign-1"}
                ),
                "protocol_hash": PROTOCOL_HASH,
                "runtime_hash": RUNTIME_HASH,
                "source_revision": "revision-qualified",
                "model_identity": (
                    '{"model":"judge-v3","provider":"test","thinking":false}'
                ),
                "data_role": "holdout_validated",
                "sample_count": 20 + index,
                "cost": Decimal("1.25"),
                "details": {
                    "campaign_id": "campaign-1",
                    "campaign_binding": "b" * 64,
                    "judge_protocol_version": 3,
                    "judge_protocol_hash": judge_protocol_digest(),
                    "budget": budget,
                },
                "issued_at": (NOW + timedelta(seconds=index)).isoformat(),
                "issuer": "campaign",
            }
        )
    return QualificationMaterial.model_validate(
        {
            "schema_version": 1,
            "campaign_id": "campaign-1",
            "campaign_binding": "b" * 64,
            "artifact": {
                "policy_hash": policy_hash,
                "parent_policy_hash": STABLE_HASH,
                "components": artifact_body["components"],
                "fixed_components_hash": FIXED_HASH,
                "runtime_hash": RUNTIME_HASH,
                "source_revision": "revision-qualified",
                "protocol_hash": PROTOCOL_HASH,
                "proposer_hash": PROPOSER_HASH,
                "data_role": "holdout_validated",
                "evidence_bindings": artifact_body["evidence_paths"],
                "created_at": NOW.isoformat(),
            },
            "receipts": receipts,
            "budget": budget,
        }
    )


def newer_material(
    material: QualificationMaterial,
    *,
    marker: str,
    issued_after: timedelta,
) -> QualificationMaterial:
    body = material.model_dump(mode="json")
    for index, receipt in enumerate(body["receipts"], start=1):
        receipt["receipt_id"] = str(uuid4())
        receipt["evidence_hash"] = canonical_hash(
            {"marker": marker, "gate": receipt["gate_type"]}
        )
        receipt["issued_at"] = (
            NOW + issued_after + timedelta(seconds=index)
        ).isoformat()
    return QualificationMaterial.model_validate(body)


@pytest.fixture
async def promotion_repo(raw_repo):
    repo = raw_repo
    async with repo.session_factory() as session, session.begin():
        head = PolicyDeploymentRecord(
            deployment_id=str(uuid4()),
            environment="rehearsal",
            version=1,
            state="active",
            candidate_policy_hash="b" * 64,
            stable_policy_hash=STABLE_HASH,
            previous_stable_deployment_id=None,
            traffic_basis_points=10000,
            assignment_salt_id="stable",
            thresholds={
                "candidate_min_runs": 20,
                "stable_min_runs": 20,
                "window_max_runs": 50,
                "commit_failure_rate": "0.05",
                "terminal_failure_rate": "0.10",
                "latency_increase_rate": "0.50",
                "mean_cost_increase_rate": "0.30",
                "unknown_rate": "0.10",
                "relative_epsilon": "0.000001",
            },
            thresholds_hash=canonical_hash(
                {
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
            ),
            required_receipts=[],
            command_id="fixture-rehearsal-head",
            reason="fixture",
            actor="test",
            created_at=NOW,
        )
        session.add(head)
        await session.flush()
        session.add(
            PolicyEnvironmentHeadRecord(
                environment="rehearsal",
                current_deployment_id=head.deployment_id,
                current_version=1,
                updated_at=NOW,
            )
        )
    return PromotionRepository(repo.session_factory, clock=lambda: NOW)


async def _counts(repository):
    async with repository.session_factory() as session:
        return {
            "artifacts": await session.scalar(
                select(func.count()).select_from(PolicyArtifactRecord)
            ),
            "receipts": await session.scalar(
                select(func.count()).select_from(PolicyGateReceiptRecord)
            ),
            "deployments": await session.scalar(
                select(func.count()).select_from(PolicyDeploymentRecord)
            ),
            "audits": await session.scalar(
                select(func.count()).select_from(PolicyAuditEventRecord)
            ),
        }


async def test_identical_registration_is_idempotent_and_binds_current_stable(
    promotion_repo,
):
    material = qualification_material()

    first = await promotion_repo.register_qualification(
        material,
        actor="release.operator",
        command_id="register-candidate-1",
    )
    second = await promotion_repo.register_qualification(
        material,
        actor="release.operator",
        command_id="register-candidate-1",
    )

    assert second == first
    assert first.state == "registered"
    assert first.version == 2
    assert first.candidate_policy_hash == material.artifact.policy_hash
    assert first.stable_policy_hash == "b" * 64
    assert set(first.required_receipts) == set(REQUIRED_GATES)
    assert await _counts(promotion_repo) == {
        "artifacts": 3,
        "receipts": 4,
        "deployments": 2,
        "audits": 1,
    }
    async with promotion_repo.session_factory() as session:
        audit = await session.scalar(
            select(PolicyAuditEventRecord).where(
                PolicyAuditEventRecord.command_id == "register-candidate-1"
            )
        )
    assert audit.details["material_hash"] == canonical_hash(
        material.model_dump(mode="json")
    )


async def test_concurrent_identical_command_returns_one_snapshot(
    promotion_repo,
):
    material = qualification_material()

    first, second = await asyncio.gather(
        promotion_repo.register_qualification(
            material,
            actor="release.operator",
            command_id="register-concurrent",
        ),
        promotion_repo.register_qualification(
            material,
            actor="release.operator",
            command_id="register-concurrent",
        ),
    )

    assert first == second
    assert await _counts(promotion_repo) == {
        "artifacts": 3,
        "receipts": 4,
        "deployments": 2,
        "audits": 1,
    }


async def test_head_lock_revalidates_latest_receipts_and_rejects_stale_material(
    promotion_repo,
):
    baseline = qualification_material()
    await promotion_repo.register_qualification(
        baseline,
        actor="release.operator",
        command_id="register-baseline",
    )
    stale = newer_material(
        baseline,
        marker="stale",
        issued_after=timedelta(hours=1),
    )
    latest = newer_material(
        baseline,
        marker="latest",
        issued_after=timedelta(hours=2),
    )
    stale_repo = PromotionRepository(
        promotion_repo.session_factory,
        clock=lambda: NOW,
    )
    prechecked = asyncio.Event()
    release_stale = asyncio.Event()
    original_verify = stale_repo._verify_latest_receipts
    verify_calls = 0

    async def pause_after_first_verify(session, material):
        nonlocal verify_calls
        verify_calls += 1
        await original_verify(session, material)
        if verify_calls == 1:
            prechecked.set()
            await release_stale.wait()

    stale_repo._verify_latest_receipts = pause_after_first_verify
    stale_task = asyncio.create_task(
        stale_repo.register_qualification(
            stale,
            actor="release.operator",
            command_id="register-stale",
        )
    )
    await asyncio.wait_for(prechecked.wait(), timeout=5)
    latest_snapshot = await promotion_repo.register_qualification(
        latest,
        actor="release.operator",
        command_id="register-latest",
    )
    release_stale.set()

    with pytest.raises(QualificationRejected, match="latest.*does not match"):
        await asyncio.wait_for(stale_task, timeout=5)

    assert latest_snapshot.candidate_policy_hash == latest.artifact.policy_hash
    assert verify_calls == 2


@pytest.mark.parametrize("changed", ["receipt", "budget"])
async def test_command_id_binds_complete_material_without_side_effects(
    promotion_repo,
    changed,
):
    original = qualification_material()
    await promotion_repo.register_qualification(
        original,
        actor="release.operator",
        command_id="register-material-bound",
    )
    before = await _counts(promotion_repo)
    body = original.model_dump(mode="json")
    if changed == "receipt":
        body["receipts"][0]["receipt_id"] = str(uuid4())
    else:
        body["budget"]["max_cny"] = 11.0
        for receipt in body["receipts"]:
            receipt["details"]["budget"]["max_cny"] = 11.0
    material = QualificationMaterial.model_validate(body)

    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await promotion_repo.register_qualification(
            material,
            actor="release.operator",
            command_id="register-material-bound",
        )

    assert await _counts(promotion_repo) == before


async def test_existing_same_hash_with_different_body_is_rejected(
    promotion_repo,
):
    material = qualification_material()
    artifact = material.artifact
    async with promotion_repo.session_factory() as session, session.begin():
        session.add(
            PolicyArtifactRecord(
                policy_hash=artifact.policy_hash,
                parent_policy_hash=artifact.parent_policy_hash,
                components={"retrieval_rules": "碰撞正文"},
                fixed_components_hash=artifact.fixed_components_hash,
                runtime_hash=artifact.runtime_hash,
                source_revision=artifact.source_revision,
                protocol_hash=artifact.protocol_hash,
                proposer_hash=artifact.proposer_hash,
                data_role=artifact.data_role,
                evidence_bindings=artifact.evidence_bindings,
                created_at=artifact.created_at,
            )
        )

    with pytest.raises(ImmutablePromotionConflict, match="artifact"):
        await promotion_repo.register_qualification(
            material,
            actor="release.operator",
            command_id="register-collision",
        )


async def test_existing_same_receipt_evidence_with_different_body_is_rejected(
    promotion_repo,
):
    material = qualification_material()
    await promotion_repo.register_qualification(
        material,
        actor="release.operator",
        command_id="register-receipt-original",
    )
    body = material.model_dump(mode="json")
    body["receipts"][0]["receipt_id"] = str(uuid4())
    changed = QualificationMaterial.model_validate(body)

    with pytest.raises(ImmutablePromotionConflict, match="receipt"):
        await promotion_repo.register_qualification(
            changed,
            actor="release.operator",
            command_id="register-receipt-collision",
        )


@pytest.mark.parametrize("status", ["failed", "unknown"])
async def test_failed_or_unknown_receipt_never_qualifies(
    promotion_repo,
    status,
):
    value = qualification_material().model_dump(mode="json")
    value["receipts"][2]["status"] = status
    material = QualificationMaterial.model_validate(value)

    with pytest.raises(QualificationRejected, match=status):
        await promotion_repo.register_qualification(
            material,
            actor="release.operator",
            command_id=f"register-{status}",
        )
    assert (await _counts(promotion_repo))["deployments"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("policy_hash", "a" * 64),
        ("protocol_hash", "e" * 64),
        ("runtime_hash", "d" * 64),
        ("source_revision", "other-revision"),
        ("model_identity", ""),
        ("data_role", "development"),
        ("cost", Decimal("-1")),
    ],
)
async def test_receipts_require_complete_immutable_binding(
    promotion_repo,
    field,
    value,
):
    body = qualification_material().model_dump(mode="json")
    body["receipts"][0][field] = value
    if field in {"model_identity", "cost"}:
        with pytest.raises(ValueError):
            QualificationMaterial.model_validate(body)
        return

    material = QualificationMaterial.model_validate(body)
    with pytest.raises(QualificationRejected, match=field):
        await promotion_repo.register_qualification(
            material,
            actor="release.operator",
            command_id=f"binding-{field}",
        )


async def test_receipts_require_current_judge_digest_and_one_model_identity(
    promotion_repo,
):
    for mutate, message in (
        (
            lambda body: body["receipts"][0]["details"].update(
                judge_protocol_hash="f" * 64
            ),
            "protocol hash",
        ),
        (
            lambda body: body["receipts"][0].update(
                model_identity='{"model":"other","provider":"test"}'
            ),
            "model_identity",
        ),
    ):
        body = qualification_material().model_dump(mode="json")
        mutate(body)
        material = QualificationMaterial.model_validate(body)
        with pytest.raises(QualificationRejected, match=message):
            await promotion_repo.register_qualification(
                material,
                actor="release.operator",
                command_id=f"reject-{message}",
            )


@pytest.mark.parametrize("status", ["failed", "unknown"])
async def test_newer_failed_or_unknown_receipt_overrides_older_pass(
    promotion_repo,
    status,
):
    material = qualification_material()
    await promotion_repo.register_qualification(
        material,
        actor="release.operator",
        command_id="first-pass",
    )
    failed = material.receipts[2].model_copy(
        update={
            "receipt_id": uuid4(),
            "status": status,
            "evidence_hash": "9" * 64,
            "issued_at": NOW + timedelta(hours=1),
        }
    )
    async with promotion_repo.session_factory() as session, session.begin():
        failed_values = failed.model_dump(mode="python")
        failed_values["receipt_id"] = str(failed.receipt_id)
        session.add(
            PolicyGateReceiptRecord(
                **failed_values,
                created_at=NOW + timedelta(hours=1),
            )
        )

    with pytest.raises(QualificationRejected, match=f"latest.*{status}"):
        await promotion_repo.register_qualification(
            material,
            actor="release.operator",
            command_id="retry-after-unknown",
        )


@pytest.mark.parametrize("malformed", [False, True])
async def test_latest_pass_must_exactly_match_material_receipt(
    promotion_repo,
    malformed,
):
    material = qualification_material()
    await promotion_repo.register_qualification(
        material,
        actor="release.operator",
        command_id="first-exact-pass",
    )
    latest = material.receipts[2].model_copy(
        update={
            "receipt_id": uuid4(),
            "evidence_hash": "8" * 64,
            "issued_at": NOW + timedelta(hours=1),
        }
    )
    values = latest.model_dump(mode="python")
    values["receipt_id"] = str(latest.receipt_id)
    if malformed:
        values["model_identity"] = ""
    async with promotion_repo.session_factory() as session, session.begin():
        session.add(
            PolicyGateReceiptRecord(
                **values,
                created_at=NOW + timedelta(hours=1),
            )
        )

    with pytest.raises(QualificationRejected, match="latest.*does not match"):
        await promotion_repo.register_qualification(
            material,
            actor="release.operator",
            command_id=f"retry-latest-{malformed}",
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda body: body.update(schema_version="1"),
        lambda body: body["budget"].update(max_requests="1200"),
        lambda body: body["budget"].update(unexpected=1),
        lambda body: body["budget"].update(estimated_peak_cny=-0.01),
        lambda body: body["budget"]["roles"].update(judge=-1),
    ],
)
def test_qualification_material_is_strict_and_budget_is_bounded(mutate):
    body = qualification_material().model_dump(mode="json")
    mutate(body)
    with pytest.raises(ValidationError):
        QualificationMaterial.model_validate(body)


async def test_changed_material_and_non_v3_or_development_artifact_are_rejected(
    promotion_repo,
):
    original = qualification_material()
    for mutate, message in (
        (
            lambda body: body["artifact"].update(
                components={"retrieval_rules": "changed evidence"}
            ),
            "hash",
        ),
        (
            lambda body: body["artifact"].update(data_role="development"),
            "holdout_validated",
        ),
        (
            lambda body: body["receipts"][0]["details"].update(
                judge_protocol_version=2
            ),
            "Judge v3",
        ),
    ):
        body = copy.deepcopy(original.model_dump(mode="json"))
        mutate(body)
        material = QualificationMaterial.model_validate(body)
        with pytest.raises(QualificationRejected, match=message):
            await promotion_repo.register_qualification(
                material,
                actor="release.operator",
                command_id=f"reject-{message.replace(' ', '-')}",
            )


async def test_file_registry_eligibility_does_not_create_postgres_qualification(
    promotion_repo,
    tmp_path,
):
    from core.policy_store import PolicyRegistry, artifact, atomic_json

    registry = PolicyRegistry(
        tmp_path / "registry",
        runtime_hash="runtime",
        source_revision="revision",
    )
    value = artifact(
        {"retrieval_rules": "local only"},
        parent=STABLE_HASH,
        protocol="protocol",
        runtime="runtime",
        source="revision",
        proposer="proposer",
        evidence={},
    )
    atomic_json(
        registry.root / "artifacts" / f"{value['policy_hash']}.json",
        value,
    )
    atomic_json(
        registry.root / "eligibility" / f"{value['policy_hash']}.json",
        {"campaign": "/tmp/legacy", "binding": "legacy"},
    )

    async with promotion_repo.session_factory() as session:
        assert await session.get(
            PolicyArtifactRecord,
            value["policy_hash"],
        ) is None
        assert (
            await session.scalar(
                select(func.count())
                .select_from(PolicyGateReceiptRecord)
                .where(
                    PolicyGateReceiptRecord.policy_hash
                    == value["policy_hash"]
                )
            )
            == 0
        )

# Task 4: CAS-protected promotion commands.
from core.distributed.models import DistributedOutbox
from core.distributed.promotion_contracts import (
    DeploymentState,
    PromotionCommand,
)
from core.distributed.promotion_repository import (
    PromotionCommandRejected,
    PromotionVersionConflict,
)
from core.distributed.promotion_service import PromotionCommandService


async def _registered(repository, *, command_id="register-for-transition"):
    return await repository.register_qualification(
        qualification_material(),
        actor="release.operator",
        command_id=command_id,
    )


async def _add_gate(repository, gate_type, *, overrides=None):
    material = qualification_material()
    artifact = material.artifact
    values = {
        "receipt_id": str(uuid4()),
        "policy_hash": artifact.policy_hash,
        "gate_type": gate_type,
        "status": "passed",
        "evidence_hash": canonical_hash(
            {"gate": gate_type, "marker": str(uuid4())}
        ),
        "protocol_hash": artifact.protocol_hash,
        "runtime_hash": artifact.runtime_hash,
        "source_revision": artifact.source_revision,
        "model_identity": "deterministic-health-v1",
        "data_role": artifact.data_role,
        "sample_count": 40,
        "cost": Decimal("0"),
        "details": {"window_id": f"{gate_type}-window"},
        "issued_at": NOW + timedelta(hours=4),
        "issuer": "health.evaluator",
        "created_at": NOW + timedelta(hours=4),
    }
    if gate_type in {"shadow_health", "canary_health"} and not (
        overrides and "details" in overrides
    ):
        deployment = await repository.get_head("rehearsal")
        values["details"] = {
            "window_id": f"{gate_type}-window",
            "deployment_id": str(deployment.deployment_id),
            "deployment_version": deployment.version,
            "thresholds_hash": deployment.thresholds_hash,
        }
    values.update(overrides or {})
    async with repository.session_factory() as session, session.begin():
        session.add(PolicyGateReceiptRecord(**values))
    return values


def _command(
    snapshot,
    target,
    *,
    command_id,
    traffic=0,
    actor="release.operator",
    reason="explicit promotion command",
):
    return PromotionCommand(
        command_id=command_id,
        environment=snapshot.environment,
        expected_version=snapshot.version,
        current_state=snapshot.state,
        target_state=target,
        traffic_basis_points=traffic,
        actor=actor,
        reason=reason,
    )


async def _advance_to(repository, target):
    service = PromotionCommandService(
        repository,
        authenticated_principal="release.operator",
    )
    snapshot = await _registered(
        repository,
        command_id=f"register-until-{target}",
    )
    if target == DeploymentState.REGISTERED:
        return service, snapshot
    snapshot = await service.transition(
        _command(snapshot, "shadow", command_id=f"shadow-until-{target}")
    )
    if target == DeploymentState.SHADOW:
        return service, snapshot
    await _add_gate(repository, "shadow_health")
    snapshot = await service.transition(
        _command(
            snapshot,
            "canary",
            command_id=f"canary-until-{target}",
            traffic=500,
        )
    )
    if target == DeploymentState.CANARY:
        return service, snapshot
    await _add_gate(repository, "canary_health")
    snapshot = await service.transition(
        _command(
            snapshot,
            "active",
            command_id=f"active-until-{target}",
            traffic=10000,
        )
    )
    return service, snapshot


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (DeploymentState.REGISTERED, DeploymentState.SHADOW),
        (DeploymentState.SHADOW, DeploymentState.CANARY),
        (DeploymentState.CANARY, DeploymentState.ACTIVE),
        (DeploymentState.REGISTERED, DeploymentState.FROZEN),
        (DeploymentState.SHADOW, DeploymentState.FROZEN),
        (DeploymentState.CANARY, DeploymentState.FROZEN),
        (DeploymentState.ACTIVE, DeploymentState.FROZEN),
        (DeploymentState.CANARY, DeploymentState.ROLLED_BACK),
        (DeploymentState.ACTIVE, DeploymentState.ROLLED_BACK),
    ],
)
async def test_transition_all_allowed_edges(promotion_repo, source, target):
    service, current = await _advance_to(promotion_repo, source)
    if target == DeploymentState.CANARY:
        await _add_gate(promotion_repo, "shadow_health")
    if target == DeploymentState.ACTIVE:
        await _add_gate(promotion_repo, "canary_health")
    traffic = (
        500
        if target == DeploymentState.CANARY
        else 10000
        if target == DeploymentState.ACTIVE
        else 0
    )
    result = await service.transition(
        _command(
            current,
            target,
            command_id=f"allowed-{source}-{target}",
            traffic=traffic,
            reason=f"allow {source} to {target}",
        )
    )

    assert result.version == current.version + 1
    assert result.state == target
    assert result.traffic_basis_points == traffic


def test_transition_all_forbidden_edges_are_rejected_by_contract():
    allowed = {
        (DeploymentState.REGISTERED, DeploymentState.SHADOW),
        (DeploymentState.SHADOW, DeploymentState.CANARY),
        (DeploymentState.CANARY, DeploymentState.ACTIVE),
        (DeploymentState.REGISTERED, DeploymentState.FROZEN),
        (DeploymentState.SHADOW, DeploymentState.FROZEN),
        (DeploymentState.CANARY, DeploymentState.FROZEN),
        (DeploymentState.ACTIVE, DeploymentState.FROZEN),
        (DeploymentState.CANARY, DeploymentState.ROLLED_BACK),
        (DeploymentState.ACTIVE, DeploymentState.ROLLED_BACK),
    }
    for source in DeploymentState:
        for target in DeploymentState:
            if (source, target) in allowed:
                continue
            with pytest.raises(ValidationError, match="invalid deployment"):
                PromotionCommand(
                    command_id=f"forbid-{source}-{target}",
                    environment="rehearsal",
                    expected_version=2,
                    current_state=source,
                    target_state=target,
                    traffic_basis_points=(
                        10000 if target == DeploymentState.ACTIVE else 0
                    ),
                    actor="release.operator",
                    reason="must fail",
                )


@pytest.mark.parametrize(
    ("target", "traffic"),
    [
        (DeploymentState.SHADOW, 1),
        (DeploymentState.CANARY, 0),
        (DeploymentState.CANARY, 10000),
        (DeploymentState.ACTIVE, 9999),
        (DeploymentState.FROZEN, 1),
        (DeploymentState.ROLLED_BACK, 1),
    ],
)
def test_transition_traffic_constraints_are_fail_closed(target, traffic):
    source = {
        DeploymentState.SHADOW: DeploymentState.REGISTERED,
        DeploymentState.CANARY: DeploymentState.SHADOW,
        DeploymentState.ACTIVE: DeploymentState.CANARY,
        DeploymentState.FROZEN: DeploymentState.REGISTERED,
        DeploymentState.ROLLED_BACK: DeploymentState.CANARY,
    }[target]
    with pytest.raises(ValidationError, match="traffic"):
        PromotionCommand(
            command_id=f"bad-traffic-{target}-{traffic}",
            environment="rehearsal",
            expected_version=2,
            current_state=source,
            target_state=target,
            traffic_basis_points=traffic,
            actor="release.operator",
            reason="invalid traffic",
        )


async def test_concurrent_transition_same_expected_version_has_one_winner(
    promotion_repo,
):
    service, registered = await _advance_to(
        promotion_repo,
        DeploymentState.REGISTERED,
    )
    commands = [
        _command(registered, "shadow", command_id=f"concurrent-transition-{i}")
        for i in range(2)
    ]
    results = await asyncio.gather(
        *(service.transition(command) for command in commands),
        return_exceptions=True,
    )

    assert sum(not isinstance(value, Exception) for value in results) == 1
    loser = next(value for value in results if isinstance(value, Exception))
    assert isinstance(loser, PromotionVersionConflict)
    async with promotion_repo.session_factory() as session:
        head = await session.get(PolicyEnvironmentHeadRecord, "rehearsal")
        transitions = await session.scalar(
            select(func.count())
            .select_from(PolicyDeploymentRecord)
            .where(PolicyDeploymentRecord.state == "shadow")
        )
    assert head.current_version == registered.version + 1
    assert transitions == 1


async def test_transition_command_replay_returns_original_and_conflicts_on_change(
    promotion_repo,
):
    service, registered = await _advance_to(
        promotion_repo,
        DeploymentState.REGISTERED,
    )
    command = _command(
        registered,
        "shadow",
        command_id="idempotent-transition",
    )
    first = await service.transition(command)
    replay = await service.transition(command)

    assert replay == first
    changed = command.model_copy(update={"reason": "different payload"})
    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await service.transition(changed)


async def test_missing_gate_keeps_head_and_commits_immutable_rejected_audit(
    promotion_repo,
):
    service, registered = await _advance_to(
        promotion_repo,
        DeploymentState.REGISTERED,
    )
    async with promotion_repo.session_factory() as session, session.begin():
        receipt = await session.scalar(
            select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.policy_hash
                == registered.candidate_policy_hash,
                PolicyGateReceiptRecord.gate_type == "formal_holdout",
            )
        )
        await session.delete(receipt)

    command = _command(
        registered,
        "shadow",
        command_id="reject-missing-gate",
    )
    with pytest.raises(PromotionCommandRejected, match="formal_holdout"):
        await service.transition(command)

    async with promotion_repo.session_factory() as session:
        head = await session.get(PolicyEnvironmentHeadRecord, "rehearsal")
        audit = await session.scalar(
            select(PolicyAuditEventRecord).where(
                PolicyAuditEventRecord.command_id == command.command_id
            )
        )
        snapshot = await session.scalar(
            select(PolicyDeploymentRecord).where(
                PolicyDeploymentRecord.command_id == command.command_id
            )
        )
    assert head.current_version == registered.version
    assert snapshot is None
    assert audit.event_type == "promotion_rejected"
    assert audit.deployment_id == str(registered.deployment_id)
    assert audit.details["missing_gates"] == ["formal_holdout"]


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("policy_hash", "a" * 64),
        ("protocol_hash", "e" * 64),
        ("runtime_hash", "d" * 64),
        ("source_revision", "wrong-source"),
    ],
)
async def test_transition_gate_binding_is_exact(
    promotion_repo,
    field,
    wrong,
):
    service, shadow = await _advance_to(
        promotion_repo,
        DeploymentState.SHADOW,
    )
    await _add_gate(
        promotion_repo,
        "shadow_health",
        overrides={field: wrong},
    )

    with pytest.raises(PromotionCommandRejected, match="shadow_health"):
        await service.transition(
            _command(
                shadow,
                "canary",
                command_id=f"wrong-binding-{field}",
                traffic=500,
            )
        )


async def test_transition_commits_snapshot_cas_audit_and_outbox_together(
    promotion_repo,
):
    service, registered = await _advance_to(
        promotion_repo,
        DeploymentState.REGISTERED,
    )
    result = await service.transition(
        _command(registered, "shadow", command_id="transactional-transition")
    )

    async with promotion_repo.session_factory() as session:
        head = await session.get(PolicyEnvironmentHeadRecord, "rehearsal")
        audit = await session.scalar(
            select(PolicyAuditEventRecord).where(
                PolicyAuditEventRecord.command_id == "transactional-transition"
            )
        )
        outbox = await session.scalar(
            select(DistributedOutbox).where(
                DistributedOutbox.event_key
                == f"deployment:{result.deployment_id}:changed"
            )
        )
    assert head.current_deployment_id == str(result.deployment_id)
    assert head.current_version == result.version
    assert audit.deployment_id == str(result.deployment_id)
    assert outbox.topic == "policy.deployment.changed"
    assert outbox.payload == {
        "deployment_id": str(result.deployment_id),
        "environment": "rehearsal",
        "version": result.version,
        "state": "shadow",
    }


async def test_activate_creates_approval_bound_to_current_canary_health(
    promotion_repo,
):
    service, canary = await _advance_to(
        promotion_repo,
        DeploymentState.CANARY,
    )
    canary_health = await _add_gate(promotion_repo, "canary_health")
    service = PromotionCommandService(
        promotion_repo,
        authenticated_principal="release.approver",
    )
    command = _command(
        canary,
        "active",
        command_id="activate-with-approval",
        traffic=10000,
        actor="release.approver",
        reason="canary health reviewed and approved",
    )
    active = await service.transition(command)

    async with promotion_repo.session_factory() as session:
        approval = await session.scalar(
            select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.policy_hash
                == active.candidate_policy_hash,
                PolicyGateReceiptRecord.gate_type == "promotion_approval",
            )
        )
    assert approval.issuer == command.actor
    assert approval.details["actor"] == command.actor
    assert approval.details["reason"] == command.reason
    assert approval.details["command_id"] == command.command_id
    assert approval.details["canary_health_receipt_id"] == canary_health[
        "receipt_id"
    ]
    assert approval.details["canary_health_evidence_hash"] == canary_health[
        "evidence_hash"
    ]
    assert approval.details["canary_deployment_id"] == str(
        canary.deployment_id
    )
    assert approval.details["canary_deployment_version"] == canary.version
    assert approval.details["canary_thresholds_hash"] == canary.thresholds_hash
    assert approval.policy_hash == active.candidate_policy_hash
    assert approval.protocol_hash == qualification_material().artifact.protocol_hash
    assert approval.runtime_hash == qualification_material().artifact.runtime_hash
    assert approval.source_revision == qualification_material().artifact.source_revision
    assert set(active.required_receipts) == {
        *REQUIRED_GATES,
        "shadow_health",
        "canary_health",
        "promotion_approval",
    }


async def test_show_head_and_issue_token_bind_current_deployment_without_storage(
    promotion_repo,
):
    from core.distributed.promotion_service import RehearsalTokenIssuer

    service, canary = await _advance_to(
        promotion_repo,
        DeploymentState.CANARY,
    )
    issuer = RehearsalTokenIssuer(
        promotion_repo,
        signing_secret="r" * 32,
        assignment_secret="a" * 32,
        clock=lambda: NOW,
    )
    result = await issuer.issue(
        rehearsal_id="rehearsal-1",
        namespace="rehearsal-rehearsal-1",
        learner_id="learner-1",
        request_id="request-1",
        operation="learning_task",
        fault_profile="none",
        ttl_seconds=60,
    )

    assert (await promotion_repo.get_head("rehearsal")) == canary
    assert set(result) == {"token", "expected_cohort"}
    assert result["expected_cohort"] in {"stable", "candidate"}
    assert "r" * 32 not in result["token"]
    assert "a" * 32 not in result["token"]
    async with promotion_repo.session_factory() as session:
        nonce_count = await session.scalar(
            select(func.count()).select_from(RehearsalTokenNonceRecord)
        )
    assert nonce_count == 0


def test_promotion_cli_help_lists_only_write_plane_commands(capsys):
    from core.distributed.promotion_cli import parser

    with pytest.raises(SystemExit) as error:
        parser().parse_args(["--help"])
    assert error.value.code == 0
    help_text = capsys.readouterr().out
    for command in (
        "register-campaign",
        "start-shadow",
        "start-canary",
        "activate",
        "freeze",
        "rollback",
        "issue-token",
        "show-head",
    ):
        assert command in help_text
    for forbidden in ("http", "worker", "ops"):
        assert forbidden not in help_text.lower()


async def test_shadow_health_latest_is_scoped_to_exact_deployment_binding(
    promotion_repo,
):
    service, shadow = await _advance_to(
        promotion_repo,
        DeploymentState.SHADOW,
    )
    exact = {
        "window_id": "shadow-current-window",
        "deployment_id": str(shadow.deployment_id),
        "deployment_version": shadow.version,
        "thresholds_hash": shadow.thresholds_hash,
    }
    await _add_gate(
        promotion_repo,
        "shadow_health",
        overrides={"details": exact},
    )
    await _add_gate(
        promotion_repo,
        "shadow_health",
        overrides={
            "status": "failed",
            "issued_at": NOW + timedelta(hours=5),
            "created_at": NOW + timedelta(hours=5),
            "details": {
                **exact,
                "window_id": "other-shadow-window",
                "deployment_id": str(uuid4()),
            },
        },
    )

    canary = await service.transition(
        _command(
            shadow,
            "canary",
            command_id="exact-shadow-health-latest",
            traffic=500,
        )
    )

    assert canary.state == DeploymentState.CANARY


async def test_shadow_health_from_old_deployment_is_rejected(promotion_repo):
    service, shadow = await _advance_to(
        promotion_repo,
        DeploymentState.SHADOW,
    )
    await _add_gate(
        promotion_repo,
        "shadow_health",
        overrides={
            "details": {
                "window_id": "old-shadow-window",
                "deployment_id": str(uuid4()),
                "deployment_version": shadow.version - 1,
                "thresholds_hash": shadow.thresholds_hash,
            }
        },
    )

    with pytest.raises(PromotionCommandRejected, match="shadow_health"):
        await service.transition(
            _command(
                shadow,
                "canary",
                command_id="reject-old-shadow-health",
                traffic=500,
            )
        )


async def _reject_transition_with_command_id(repository, command_id):
    service, registered = await _advance_to(
        repository,
        DeploymentState.REGISTERED,
    )
    async with repository.session_factory() as session, session.begin():
        receipt = await session.scalar(
            select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.policy_hash
                == registered.candidate_policy_hash,
                PolicyGateReceiptRecord.gate_type == "formal_holdout",
            )
        )
        await session.delete(receipt)
    command = _command(registered, "shadow", command_id=command_id)
    with pytest.raises(PromotionCommandRejected) as error:
        await service.transition(command)
    return service, command, str(error.value)


async def test_rejected_command_id_cannot_be_reused_for_registration(
    promotion_repo,
):
    command_id = "global-rejected-then-register"
    await _reject_transition_with_command_id(promotion_repo, command_id)

    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await promotion_repo.register_qualification(
            qualification_material(),
            actor="release.operator",
            command_id=command_id,
        )


async def test_registered_command_id_cannot_be_reused_for_transition(
    promotion_repo,
):
    registered = await _registered(
        promotion_repo,
        command_id="global-register-then-transition",
    )
    service = PromotionCommandService(
        promotion_repo,
        authenticated_principal="release.operator",
    )

    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await service.transition(
            _command(
                registered,
                "shadow",
                command_id="global-register-then-transition",
            )
        )


async def test_identical_rejected_command_replays_original_without_new_audit(
    promotion_repo,
):
    service, command, original_error = await _reject_transition_with_command_id(
        promotion_repo,
        "idempotent-rejected-transition",
    )

    with pytest.raises(PromotionCommandRejected) as replay_error:
        await service.transition(command)

    assert str(replay_error.value) == original_error
    async with promotion_repo.session_factory() as session:
        audit_count = await session.scalar(
            select(func.count())
            .select_from(PolicyAuditEventRecord)
            .where(
                PolicyAuditEventRecord.command_id
                == "idempotent-rejected-transition"
            )
        )
    assert audit_count == 1


async def test_rejected_command_id_conflicts_on_different_payload(
    promotion_repo,
):
    service, command, _ = await _reject_transition_with_command_id(
        promotion_repo,
        "rejected-payload-conflict",
    )

    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await service.transition(
            command.model_copy(update={"reason": "different rejection payload"})
        )


async def test_latest_gate_is_selected_after_full_artifact_binding_filter(
    promotion_repo,
):
    service, registered = await _advance_to(
        promotion_repo,
        DeploymentState.REGISTERED,
    )
    material = qualification_material()
    original = next(
        receipt
        for receipt in material.receipts
        if receipt.gate_type == "formal_holdout"
    )
    values = original.model_dump(mode="python")
    values.update(
        receipt_id=str(uuid4()),
        status="failed",
        evidence_hash="7" * 64,
        runtime_hash="6" * 64,
        issued_at=NOW + timedelta(hours=8),
        created_at=NOW + timedelta(hours=8),
    )
    async with promotion_repo.session_factory() as session, session.begin():
        session.add(PolicyGateReceiptRecord(**values))

    shadow = await service.transition(
        _command(
            registered,
            "shadow",
            command_id="artifact-bound-latest",
        )
    )

    assert shadow.state == DeploymentState.SHADOW


async def _deployment_at_version(repository, version):
    async with repository.session_factory() as session:
        return await session.scalar(
            select(PolicyDeploymentRecord).where(
                PolicyDeploymentRecord.environment == "rehearsal",
                PolicyDeploymentRecord.version == version,
            )
        )


async def test_active_revalidates_latest_qualification_evidence(promotion_repo):
    service, canary = await _advance_to(
        promotion_repo,
        DeploymentState.CANARY,
    )
    await _add_gate(
        promotion_repo,
        "canary_health",
        overrides={
            "details": {
                "window_id": "current-canary-window",
                "deployment_id": str(canary.deployment_id),
                "deployment_version": canary.version,
                "thresholds_hash": canary.thresholds_hash,
            }
        },
    )
    material = qualification_material()
    original = next(
        receipt
        for receipt in material.receipts
        if receipt.gate_type == "formal_holdout"
    )
    values = original.model_dump(mode="python")
    values.update(
        receipt_id=str(uuid4()),
        status="failed",
        evidence_hash="5" * 64,
        issued_at=NOW + timedelta(hours=9),
        created_at=NOW + timedelta(hours=9),
    )
    async with promotion_repo.session_factory() as session, session.begin():
        session.add(PolicyGateReceiptRecord(**values))

    with pytest.raises(PromotionCommandRejected, match="formal_holdout"):
        await service.transition(
            _command(
                canary,
                "active",
                command_id="active-rechecks-qualification",
                traffic=10000,
            )
        )


async def test_active_revalidates_shadow_health_from_current_chain(
    promotion_repo,
):
    service, canary = await _advance_to(
        promotion_repo,
        DeploymentState.CANARY,
    )
    shadow = await _deployment_at_version(promotion_repo, canary.version - 1)
    shadow_binding = {
        "window_id": "chain-shadow-pass",
        "deployment_id": shadow.deployment_id,
        "deployment_version": shadow.version,
        "thresholds_hash": shadow.thresholds_hash,
    }
    await _add_gate(
        promotion_repo,
        "shadow_health",
        overrides={
            "details": shadow_binding,
            "issued_at": NOW + timedelta(hours=6),
            "created_at": NOW + timedelta(hours=6),
        },
    )
    await _add_gate(
        promotion_repo,
        "shadow_health",
        overrides={
            "status": "failed",
            "details": {**shadow_binding, "window_id": "chain-shadow-fail"},
            "issued_at": NOW + timedelta(hours=7),
            "created_at": NOW + timedelta(hours=7),
        },
    )
    await _add_gate(
        promotion_repo,
        "canary_health",
        overrides={
            "details": {
                "window_id": "chain-canary-pass",
                "deployment_id": str(canary.deployment_id),
                "deployment_version": canary.version,
                "thresholds_hash": canary.thresholds_hash,
            }
        },
    )

    with pytest.raises(PromotionCommandRejected, match="shadow_health"):
        await service.transition(
            _command(
                canary,
                "active",
                command_id="active-rechecks-shadow-health",
                traffic=10000,
            )
        )


async def test_active_rejects_canary_health_from_old_deployment(
    promotion_repo,
):
    service, canary = await _advance_to(
        promotion_repo,
        DeploymentState.CANARY,
    )
    await _add_gate(
        promotion_repo,
        "canary_health",
        overrides={
            "details": {
                "window_id": "old-canary-window",
                "deployment_id": str(uuid4()),
                "deployment_version": canary.version - 1,
                "thresholds_hash": canary.thresholds_hash,
            }
        },
    )

    with pytest.raises(PromotionCommandRejected, match="canary_health"):
        await service.transition(
            _command(
                canary,
                "active",
                command_id="active-rejects-old-canary-health",
                traffic=10000,
            )
        )


async def test_forged_transition_actor_is_rejected_before_any_write(
    promotion_repo,
):
    service, canary = await _advance_to(
        promotion_repo,
        DeploymentState.CANARY,
    )
    await _add_gate(
        promotion_repo,
        "canary_health",
        overrides={
            "details": {
                "window_id": "principal-canary-window",
                "deployment_id": str(canary.deployment_id),
                "deployment_version": canary.version,
                "thresholds_hash": canary.thresholds_hash,
            }
        },
    )
    authenticated = PromotionCommandService(
        promotion_repo,
        authenticated_principal="release.approver",
    )
    command = _command(
        canary,
        "active",
        command_id="forged-transition-actor",
        traffic=10000,
        actor="forged.approver",
    )
    before = await _counts(promotion_repo)
    before_head = await promotion_repo.get_head("rehearsal")

    with pytest.raises(PermissionError, match="authenticated principal"):
        await authenticated.transition(command)

    assert await _counts(promotion_repo) == before
    assert await promotion_repo.get_head("rehearsal") == before_head
    async with promotion_repo.session_factory() as session:
        approval_count = await session.scalar(
            select(func.count())
            .select_from(PolicyGateReceiptRecord)
            .where(PolicyGateReceiptRecord.gate_type == "promotion_approval")
        )
        audit_count = await session.scalar(
            select(func.count())
            .select_from(PolicyAuditEventRecord)
            .where(
                PolicyAuditEventRecord.command_id == command.command_id
            )
        )
    assert approval_count == 0
    assert audit_count == 0


async def test_forged_registration_actor_is_rejected_before_any_write(
    promotion_repo,
):
    from core.distributed.promotion_service import PromotionService

    class CampaignMaterial:
        @staticmethod
        def qualification_material():
            return qualification_material().model_dump(mode="json")

    service = PromotionService(
        promotion_repo,
        authenticated_principal="release.operator",
    )
    before = await _counts(promotion_repo)
    before_head = await promotion_repo.get_head("rehearsal")

    with pytest.raises(PermissionError, match="authenticated principal"):
        await service.register_campaign(
            CampaignMaterial(),
            actor="forged.operator",
            command_id="forged-registration-actor",
        )

    assert await _counts(promotion_repo) == before
    assert await promotion_repo.get_head("rehearsal") == before_head

@pytest.mark.parametrize(
    "namespace",
    [
        "production",
        "../rehearsal-demo",
        "rehearsal-other",
        "rehearsal-demo/../../production",
    ],
)
async def test_issue_token_rejects_noncanonical_rehearsal_namespace(
    promotion_repo,
    namespace,
):
    from core.distributed.promotion_service import RehearsalTokenIssuer

    issuer = RehearsalTokenIssuer(
        promotion_repo,
        signing_secret="r" * 32,
        assignment_secret="a" * 32,
        clock=lambda: NOW,
    )

    with pytest.raises(ValueError, match="namespace"):
        await issuer.issue(
            rehearsal_id="demo",
            namespace=namespace,
            learner_id="learner-1",
            request_id="request-1",
            operation="learning_task",
            fault_profile="none",
            ttl_seconds=60,
        )


async def test_issue_token_payload_uses_canonical_task5_fields(promotion_repo):
    import base64
    import json

    from core.distributed.promotion_service import RehearsalTokenIssuer

    issuer = RehearsalTokenIssuer(
        promotion_repo,
        signing_secret="r" * 32,
        assignment_secret="a" * 32,
        clock=lambda: NOW,
    )
    result = await issuer.issue(
        rehearsal_id="demo",
        namespace="rehearsal-demo",
        learner_id="learner-1",
        request_id="request-1",
        operation="learning_task",
        fault_profile="none",
        ttl_seconds=60,
    )
    encoded_body = result["token"].split(".", 1)[0]
    encoded_body += "=" * (-len(encoded_body) % 4)
    payload = json.loads(base64.urlsafe_b64decode(encoded_body))

    assert payload["rehearsal_id"] == "demo"
    assert payload["namespace"] == "rehearsal-demo"
    assert payload["operations"] == ["learning_task"]
    assert "state_namespace" not in payload
    assert "operation" not in payload
    assert "allowed_operations" not in payload


async def test_command_id_is_rechecked_after_head_lock_race(promotion_repo):
    service, registered = await _advance_to(
        promotion_repo,
        DeploymentState.REGISTERED,
    )
    async with promotion_repo.session_factory() as session, session.begin():
        receipt = await session.scalar(
            select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.policy_hash
                == registered.candidate_policy_hash,
                PolicyGateReceiptRecord.gate_type == "formal_holdout",
            )
        )
        await session.delete(receipt)

    command_id = "command-id-head-lock-race"
    first_check = asyncio.Event()
    release_registration = asyncio.Event()
    original_find = promotion_repo._find_registration_replay
    find_calls = 0

    async def pause_registration_after_first_check(session, **kwargs):
        nonlocal find_calls
        find_calls += 1
        result = await original_find(session, **kwargs)
        if find_calls == 1:
            first_check.set()
            await release_registration.wait()
        return result

    promotion_repo._find_registration_replay = pause_registration_after_first_check
    registration = asyncio.create_task(
        promotion_repo.register_qualification(
            qualification_material(),
            actor="release.operator",
            command_id=command_id,
        )
    )
    await asyncio.wait_for(first_check.wait(), timeout=5)
    with pytest.raises(PromotionCommandRejected):
        await service.transition(
            _command(registered, "shadow", command_id=command_id)
        )
    release_registration.set()

    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await asyncio.wait_for(registration, timeout=5)
    assert find_calls == 2
    async with promotion_repo.session_factory() as session:
        audits = await session.scalar(
            select(func.count())
            .select_from(PolicyAuditEventRecord)
            .where(PolicyAuditEventRecord.command_id == command_id)
        )
        deployments = await session.scalar(
            select(func.count())
            .select_from(PolicyDeploymentRecord)
            .where(PolicyDeploymentRecord.command_id == command_id)
        )
    assert audits == 1
    assert deployments == 0


@pytest.mark.parametrize(
    ("source", "cli_command", "extra"),
    [
        ("registered", "start-shadow", []),
        ("shadow", "start-canary", ["--basis-points", "500"]),
        ("canary", "activate", ["--reason", "approved"]),
        ("registered", "freeze", ["--reason", "stop"]),
        ("canary", "rollback", ["--reason", "rollback"]),
    ],
)
async def test_cli_run_replays_expected_version_after_head_advances(
    promotion_repo, monkeypatch, source, cli_command, extra,
):
    from core.distributed import promotion_cli

    service, snapshot = await _advance_to(promotion_repo, DeploymentState(source))
    if cli_command == "start-canary":
        await _add_gate(promotion_repo, "shadow_health")
    if cli_command == "activate":
        await _add_gate(promotion_repo, "canary_health")
    runtime = SimpleNamespace(service=service, start=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr(promotion_cli, "build_promotion_command_runtime", lambda _: runtime)
    argv = [
        cli_command, "--environment", "rehearsal",
        "--expected-version", str(snapshot.version),
        "--actor", "release.operator", "--command-id", "cli-replay",
        *extra,
    ]
    args = promotion_cli.parser().parse_args(argv)
    first = await promotion_cli.run(args)
    assert await promotion_cli.run(args) == first
    later = await _registered(promotion_repo, command_id="cli-later-registration")
    counts = await _counts(promotion_repo)
    assert await promotion_cli.run(args) == first
    assert await service.show_head("rehearsal") == later
    assert await _counts(promotion_repo) == counts
    changed = copy.copy(args)
    changed.reason = "different CLI payload"
    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await promotion_cli.run(changed)
    if cli_command == "start-canary":
        changed = copy.copy(args)
        changed.basis_points = 600
        with pytest.raises(ImmutablePromotionConflict, match="command_id"):
            await promotion_cli.run(changed)
    assert runtime.close.await_count == runtime.start.await_count


async def _audit_body(repository, command_id):
    async with repository.session_factory() as session:
        audit = await session.scalar(select(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.command_id == command_id
        ))
        return {
            column.name: copy.deepcopy(getattr(audit, column.name))
            for column in PolicyAuditEventRecord.__table__.columns
        }


async def _legacy_registration(repository, command_id):
    snapshot = await _registered(repository, command_id=command_id)
    async with repository.session_factory() as session, session.begin():
        audit = await session.scalar(select(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.command_id == command_id
        ))
        details = dict(audit.details)
        details.pop("command_hash")  # Exact 1fc25ab registration format.
        audit.details = details
    return snapshot


async def test_legacy_registration_upgrade_replays_twice_without_audit_mutation(
    promotion_repo,
):
    command_id = "legacy-registration"
    first = await _legacy_registration(promotion_repo, command_id)
    original = await _audit_body(promotion_repo, command_id)
    counts = await _counts(promotion_repo)
    for _ in range(2):
        upgraded = PromotionRepository(promotion_repo.session_factory, clock=lambda: NOW)
        assert await _registered(upgraded, command_id=command_id) == first
    assert await _audit_body(promotion_repo, command_id) == original
    assert await _counts(promotion_repo) == counts


@pytest.mark.parametrize("tamper", [
    "actor", "material", "event_type", "command_id", "material_hash",
    "candidate_policy_hash", "campaign_id", "campaign_binding", "receipt_ids",
    "budget", "stable_policy_hash", "command_hash", "deployment_id",
])
async def test_legacy_registration_payload_tampering_fails_closed(promotion_repo, tamper):
    command_id = "legacy-registration-tamper"
    await _legacy_registration(promotion_repo, command_id)
    material = qualification_material()
    actor = "release.operator"
    if tamper == "actor":
        actor = "another.operator"
    elif tamper == "material":
        material = newer_material(material, marker="changed", issued_after=timedelta(hours=1))
    else:
        async with promotion_repo.session_factory() as session, session.begin():
            audit = await session.scalar(select(PolicyAuditEventRecord).where(
                PolicyAuditEventRecord.command_id == command_id
            ))
            if tamper in {"event_type", "command_id"}:
                setattr(audit, tamper, "different-value")
            elif tamper == "deployment_id":
                audit.deployment_id = None
            else:
                audit.details = {**audit.details, tamper: "tampered"}
    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await promotion_repo.register_qualification(material, actor=actor, command_id=command_id)


@pytest.mark.parametrize("rejected", [False, True])
async def test_legacy_transition_upgrade_replays_twice_without_audit_mutation(
    promotion_repo, rejected,
):
    command_id = "legacy-transition"
    if rejected:
        service, command, error = await _reject_transition_with_command_id(promotion_repo, command_id)
    else:
        service, registered = await _advance_to(promotion_repo, DeploymentState.REGISTERED)
        command = _command(registered, "shadow", command_id=command_id)
        first = await service.transition(command)
        await service.transition(_command(first, "frozen", command_id="legacy-later-freeze"))
    async with promotion_repo.session_factory() as session, session.begin():
        audit = await session.scalar(select(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.command_id == command_id
        ))
        audit.details = {**audit.details, "command_hash": canonical_hash(command.model_dump(mode="json"))}
    original = await _audit_body(promotion_repo, command_id)
    counts = await _counts(promotion_repo)
    for _ in range(2):
        upgraded = PromotionRepository(promotion_repo.session_factory, clock=lambda: NOW)
        if rejected:
            with pytest.raises(PromotionCommandRejected, match=error):
                await upgraded.transition(command)
        else:
            assert await upgraded.transition(command) == first
    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await upgraded.transition(command.model_copy(update={"reason": "tampered payload"}))
    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await _registered(upgraded, command_id=command_id)
    assert await _audit_body(promotion_repo, command_id) == original
    assert await _counts(promotion_repo) == counts


@pytest.mark.parametrize("legacy_hash", [False, True])
@pytest.mark.parametrize("event_type", ["qualification_registered", "promotion_rejected"])
async def test_transition_replay_requires_matching_event_type(promotion_repo, legacy_hash, event_type):
    service, registered = await _advance_to(promotion_repo, DeploymentState.REGISTERED)
    command = _command(registered, "shadow", command_id="transition-event-tamper")
    await service.transition(command)
    async with promotion_repo.session_factory() as session, session.begin():
        audit = await session.scalar(select(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.command_id == command.command_id
        ))
        audit.event_type = event_type
        if legacy_hash:
            audit.details = {**audit.details, "command_hash": canonical_hash(command.model_dump(mode="json"))}
    with pytest.raises(ImmutablePromotionConflict, match="command_id"):
        await service.transition(command)


@pytest.mark.parametrize("operation", ["registration", "transition"])
async def test_read_committed_replay_query_commit_barrier(promotion_repo, operation):
    """Commit between the reader's first replay SELECT and its next statement."""
    command_id = "snapshot-barrier-replay"
    queried = asyncio.Event()
    release = asyncio.Event()
    first_table = "policy_audit_events" if operation == "registration" else "policy_deployments"

    class BarrierSession(AsyncSession):
        paused = False

        async def _barrier(self, statement):
            if not self.paused and first_table in str(statement):
                self.paused = True
                queried.set()
                await release.wait()

        async def scalar(self, statement, *args, **kwargs):
            result = await super().scalar(statement, *args, **kwargs)
            await self._barrier(statement)
            return result

        async def execute(self, statement, *args, **kwargs):
            result = await super().execute(statement, *args, **kwargs)
            await self._barrier(statement)
            return result

    reader = PromotionRepository(async_sessionmaker(
        promotion_repo.session_factory.kw["bind"],
        class_=BarrierSession, expire_on_commit=False,
    ), clock=lambda: NOW)
    if operation == "registration":
        async def invoke(repository):
            return await _registered(repository, command_id=command_id)
    else:
        _, registered = await _advance_to(promotion_repo, DeploymentState.REGISTERED)
        command = _command(registered, "shadow", command_id=command_id)

        async def invoke(repository):
            return await repository.transition(command)

    task = asyncio.create_task(invoke(reader))
    try:
        await asyncio.wait_for(queried.wait(), timeout=5)
        first = await asyncio.wait_for(invoke(promotion_repo), timeout=5)
        release.set()
        assert await asyncio.wait_for(task, timeout=5) == first
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    async with promotion_repo.session_factory() as session:
        for model in (PolicyDeploymentRecord, PolicyAuditEventRecord):
            assert await session.scalar(select(func.count()).select_from(model).where(
                model.command_id == command_id
            )) == 1
