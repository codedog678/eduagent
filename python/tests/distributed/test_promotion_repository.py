import copy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from core.distributed.contracts import canonical_hash
from core.distributed.promotion_models import (
    PolicyArtifactRecord,
    PolicyAuditEventRecord,
    PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord,
    PolicyGateReceiptRecord,
)
from core.distributed.promotion_repository import (
    ImmutablePromotionConflict,
    PromotionRepository,
    QualificationRejected,
)
from core.distributed.promotion_service import (
    QualificationMaterial,
)

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
    budget = {
        "requests": 80,
        "estimated_peak_cny": 1.25,
        "billing_status": "estimate_only",
    }
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
                    "judge_protocol_hash": "c" * 64,
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


@pytest.fixture
async def promotion_repo(repo):
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
        ("policy_hash", "f" * 64),
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
