"""Replay 1fc25ab command evidence through two real PostgreSQL upgrades."""

import copy
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.distributed import expert_models  # noqa: F401
from core.distributed.contracts import canonical_hash
from core.distributed.models import DistributedBase, DistributedOutbox
from core.distributed.promotion_contracts import PromotionCommand
from core.distributed.promotion_models import (
    PolicyArtifactRecord,
    PolicyAuditEventRecord,
    PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord,
    PolicyGateReceiptRecord,
)
from core.distributed.promotion_repository import (
    PromotionCommandRejected,
    PromotionRepository,
)
from core.distributed.promotion_service import QualificationMaterial
from core.distributed.runtime import (
    BUILTIN_FIXED_COMPONENTS_HASH,
    BUILTIN_POLICY_COMPONENTS,
    BUILTIN_POLICY_HASH,
    BUILTIN_PROPOSER_HASH,
    BUILTIN_PROTOCOL_HASH,
    BUILTIN_RUNTIME_HASH,
    DEFAULT_POLICY_THRESHOLDS,
    DEFAULT_POLICY_THRESHOLDS_HASH,
    PRODUCTION_DEPLOYMENT_ID,
    REHEARSAL_DEPLOYMENT_ID,
    upgrade_m3_schema,
)
from tests.distributed.test_promotion_repository import NOW, qualification_material

pytestmark = pytest.mark.distributed_integration

ACTOR = "release.operator"


async def _seed_bootstrap(connection):
    """Match runtime bootstrap IDs/v1 rows without installing immutability triggers."""
    await connection.execute(
        PolicyArtifactRecord.__table__.insert().values(
            policy_hash=BUILTIN_POLICY_HASH,
            parent_policy_hash=None,
            components=BUILTIN_POLICY_COMPONENTS,
            fixed_components_hash=BUILTIN_FIXED_COMPONENTS_HASH,
            runtime_hash=BUILTIN_RUNTIME_HASH,
            source_revision="builtin",
            protocol_hash=BUILTIN_PROTOCOL_HASH,
            proposer_hash=BUILTIN_PROPOSER_HASH,
            data_role="builtin",
            evidence_bindings={},
            created_at=NOW,
        )
    )
    for environment, deployment_id, event_id in (
        (
            "production", PRODUCTION_DEPLOYMENT_ID,
            "00000000-0000-0000-0000-000000000011",
        ),
        (
            "rehearsal", REHEARSAL_DEPLOYMENT_ID,
            "00000000-0000-0000-0000-000000000012",
        ),
    ):
        command_id = f"bootstrap-{environment}"
        await connection.execute(
            PolicyDeploymentRecord.__table__.insert().values(
                deployment_id=deployment_id,
                environment=environment,
                version=1,
                state="registered",
                candidate_policy_hash=None,
                stable_policy_hash=BUILTIN_POLICY_HASH,
                previous_stable_deployment_id=None,
                traffic_basis_points=0,
                assignment_salt_id="builtin",
                thresholds=DEFAULT_POLICY_THRESHOLDS,
                thresholds_hash=DEFAULT_POLICY_THRESHOLDS_HASH,
                required_receipts=[],
                command_id=command_id,
                reason="builtin bootstrap",
                actor="system",
                created_at=NOW,
            )
        )
        await connection.execute(
            PolicyEnvironmentHeadRecord.__table__.insert().values(
                environment=environment,
                current_deployment_id=deployment_id,
                current_version=1,
                updated_at=NOW,
            )
        )
        await connection.execute(
            PolicyAuditEventRecord.__table__.insert().values(
                event_id=event_id,
                environment=environment,
                deployment_id=deployment_id,
                event_type="bootstrap",
                command_id=command_id,
                actor="system",
                reason="builtin bootstrap",
                details={},
                created_at=NOW,
            )
        )


@pytest_asyncio.fixture
async def legacy_promotion_schema():
    url = os.getenv("DISTRIBUTED_TEST_DATABASE_URL")
    if not url:
        pytest.skip("DISTRIBUTED_TEST_DATABASE_URL is not configured")
    schema = f"legacy_promotion_upgrade_{uuid4().hex}"
    admin_engine = create_async_engine(url)
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": schema}}
    )
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as connection:
            assert await connection.scalar(text("SELECT current_schema()")) == schema
            await connection.run_sync(DistributedBase.metadata.create_all)
            await _seed_bootstrap(connection)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        yield engine, PromotionRepository(factory, clock=lambda: NOW), schema
    finally:
        await engine.dispose()
        try:
            async with admin_engine.begin() as connection:
                await connection.execute(
                    text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
                )
        finally:
            await admin_engine.dispose()


def _material():
    """Bind the existing qualified evidence factory to the real bootstrap parent."""
    material = qualification_material()
    body = material.model_dump(mode="json")
    artifact = body["artifact"]
    artifact["parent_policy_hash"] = BUILTIN_POLICY_HASH
    hash_body = {
        key: value
        for key, value in artifact.items()
        if key not in {"policy_hash", "evidence_bindings"}
    }
    hash_body.update(
        schema_version=1,
        evidence_paths=artifact["evidence_bindings"],
        # Artifact hashing uses isoformat (+00:00), not JSON datetime encoding (Z).
        created_at=material.artifact.created_at.isoformat(),
    )
    artifact["policy_hash"] = canonical_hash(hash_body)
    for receipt in body["receipts"]:
        receipt["policy_hash"] = artifact["policy_hash"]
    return QualificationMaterial.model_validate(body)


def _command(snapshot, target, command_id):
    return PromotionCommand(
        command_id=command_id,
        environment=snapshot.environment,
        expected_version=snapshot.version,
        current_state=snapshot.state,
        target_state=target,
        traffic_basis_points=0,
        actor=ACTOR,
        reason="explicit legacy promotion command",
    )


async def _legacy_audit(repository, command_id, *, command=None):
    # This runs before upgrades install append-only triggers, in this schema only.
    async with repository.session_factory() as session, session.begin():
        audit = (
            await session.scalars(
                select(PolicyAuditEventRecord).where(
                    PolicyAuditEventRecord.command_id == command_id
                )
            )
        ).one()
        details = dict(audit.details)
        if command is None:
            details.pop("command_hash")  # 1fc25ab registration had no command hash.
        else:
            # 1fc25ab transitions hashed the command without a command_type wrapper.
            details["command_hash"] = canonical_hash(command.model_dump(mode="json"))
        audit.details = details


async def _evidence(repository):
    """Compare every row, not just counts, including mutable heads and outbox."""
    async with repository.session_factory() as session:
        evidence = {}
        for model in (
            PolicyArtifactRecord,
            PolicyGateReceiptRecord,
            PolicyDeploymentRecord,
            PolicyAuditEventRecord,
            PolicyEnvironmentHeadRecord,
            DistributedOutbox,
        ):
            table = model.__table__
            rows = await session.execute(
                select(table).order_by(*table.primary_key.columns)
            )
            evidence[table.name] = copy.deepcopy([dict(row) for row in rows.mappings()])
        return evidence


async def _upgrade(engine, schema):
    # Each invocation commits real DDL on the same schema used by repository sessions.
    async with engine.begin() as connection:
        assert await connection.scalar(text("SELECT current_schema()")) == schema
        await upgrade_m3_schema(connection)
        assert await connection.scalar(
            text(
                "SELECT count(*) FROM pg_trigger "
                "WHERE tgrelid = 'policy_audit_events'::regclass "
                "AND tgname = 'trg_policy_audit_events_append_only' "
                "AND tgenabled = 'O'"
            )
        ) == 1


async def test_legacy_registration_replays_through_two_real_schema_upgrades(
    legacy_promotion_schema,
):
    engine, repository, schema = legacy_promotion_schema
    material = _material()
    command_id = "legacy-registration-schema-upgrade"
    first = await repository.register_qualification(
        material, actor=ACTOR, command_id=command_id
    )
    assert first.version == 2
    assert first.stable_policy_hash == BUILTIN_POLICY_HASH
    await _legacy_audit(repository, command_id)
    later = await repository.transition(_command(first, "frozen", "later-freeze"))
    original = await _evidence(repository)
    audits = [
        row for row in original["policy_audit_events"]
        if row["command_id"] == command_id
    ]
    deployments = [
        row for row in original["policy_deployments"]
        if row["command_id"] == command_id
    ]
    assert len(audits) == len(deployments) == 1
    assert audits[0]["event_type"] == "qualification_registered"
    assert "command_hash" not in audits[0]["details"]

    for _ in range(2):
        await _upgrade(engine, schema)
        assert await _evidence(repository) == original
        upgraded = PromotionRepository(repository.session_factory, clock=lambda: NOW)
        replay = await upgraded.register_qualification(
            material, actor=ACTOR, command_id=command_id
        )
        assert replay == first
        assert await upgraded.get_head("rehearsal") == later
        assert await _evidence(upgraded) == original


@pytest.mark.parametrize("rejected", [False, True], ids=["successful", "rejected"])
async def test_legacy_transition_replays_through_two_real_schema_upgrades(
    legacy_promotion_schema, rejected,
):
    engine, repository, schema = legacy_promotion_schema
    material = _material()
    registered = await repository.register_qualification(
        material, actor=ACTOR, command_id="setup-registration"
    )
    command = _command(registered, "shadow", "legacy-transition-schema-upgrade")
    if rejected:
        receipt = next(
            receipt for receipt in material.receipts
            if receipt.gate_type == "formal_holdout"
        )
        async with repository.session_factory() as session, session.begin():
            await session.execute(
                delete(PolicyGateReceiptRecord).where(
                    PolicyGateReceiptRecord.receipt_id == str(receipt.receipt_id)
                )
            )
        with pytest.raises(PromotionCommandRejected) as error:
            await repository.transition(command)
        original_error = str(error.value)
        assert "formal_holdout" in original_error
        # Heal the rejection cause before upgrade/replay; the persisted error must win.
        values = receipt.model_dump(mode="python")
        values.update(receipt_id=str(receipt.receipt_id), created_at=NOW)
        async with repository.session_factory() as session, session.begin():
            session.add(PolicyGateReceiptRecord(**values))
        later = await repository.transition(
            _command(registered, "shadow", "later-shadow")
        )
    else:
        first = await repository.transition(command)
        later = await repository.transition(_command(first, "frozen", "later-freeze"))
    await _legacy_audit(repository, command.command_id, command=command)
    original = await _evidence(repository)
    audits = [
        row for row in original["policy_audit_events"]
        if row["command_id"] == command.command_id
    ]
    deployments = [
        row for row in original["policy_deployments"]
        if row["command_id"] == command.command_id
    ]
    assert len(audits) == 1
    assert len(deployments) == (0 if rejected else 1)
    assert audits[0]["event_type"] == (
        "promotion_rejected" if rejected else "promotion_transitioned"
    )
    assert audits[0]["details"]["command_hash"] == canonical_hash(
        command.model_dump(mode="json")
    )

    for _ in range(2):
        await _upgrade(engine, schema)
        assert await _evidence(repository) == original
        upgraded = PromotionRepository(repository.session_factory, clock=lambda: NOW)
        if rejected:
            with pytest.raises(PromotionCommandRejected) as replay_error:
                await upgraded.transition(command)
            assert str(replay_error.value) == original_error
        else:
            assert await upgraded.transition(command) == first
        assert await upgraded.get_head("rehearsal") == later
        assert await _evidence(upgraded) == original
