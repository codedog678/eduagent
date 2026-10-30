import asyncio
import copy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
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
