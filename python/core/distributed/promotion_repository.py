from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .contracts import canonical_hash
from .promotion_contracts import (
    DeploymentSnapshot,
    DeploymentState,
    GateReceipt,
    PromotionCommand,
    PolicyArtifact,
    PolicyThresholds,
)
from .promotion_models import (
    PolicyArtifactRecord,
    PolicyAuditEventRecord,
    PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord,
    PolicyGateReceiptRecord,
    PolicyHealthWindowRecord,
    PolicyObservationRecord,
)
from .models import DistributedOutbox
from .promotion_service import QualificationMaterial
from .shadow_repository import ShadowRepositoryMixin

REQUIRED_QUALIFICATION_GATES = (
    "campaign_eligibility",
    "judge_calibration",
    "formal_holdout",
    "harness_qualification",
)


class QualificationRejected(ValueError):
    pass


class ImmutablePromotionConflict(RuntimeError):
    pass


class PromotionVersionConflict(ImmutablePromotionConflict):
    pass


class PromotionCommandRejected(ValueError):
    pass


REQUIRED_EXTERNAL_GATES = {
    DeploymentState.SHADOW: {
        "campaign_eligibility",
        "judge_calibration",
        "formal_holdout",
        "harness_qualification",
    },
    DeploymentState.CANARY: {"shadow_health"},
    DeploymentState.ACTIVE: {
        *REQUIRED_QUALIFICATION_GATES,
        "shadow_health",
        "canary_health",
    },
}


class PromotionRepository(ShadowRepositoryMixin):
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] | None = None,
        judge_protocol_digest: Callable[[], str] | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.clock = clock or (lambda: datetime.now(UTC))
        self.judge_protocol_digest = (
            judge_protocol_digest or self._current_judge_protocol_digest
        )

    @staticmethod
    def _current_judge_protocol_digest() -> str:
        from evals.optimization.scoring import judge_protocol_digest

        return judge_protocol_digest()

    async def freeze_if_current(
        self, session: AsyncSession, deployment_id: str, version: int,
    ) -> bool:
        """Freeze a failed admission snapshot in the caller's surviving transaction."""
        current = await session.get(PolicyDeploymentRecord, deployment_id)
        if current is None:
            return False
        head = await session.scalar(select(PolicyEnvironmentHeadRecord).where(
            PolicyEnvironmentHeadRecord.environment == current.environment
        ).with_for_update().execution_options(populate_existing=True))
        if (head is None or head.current_deployment_id != deployment_id
            or head.current_version != version or current.state == "frozen"):
            return False
        now = self.clock()
        command_id = f"admission-freeze-{deployment_id}-{version}"
        frozen = PolicyDeploymentRecord(
            deployment_id=str(uuid4()), environment=current.environment, version=version + 1,
            state="frozen", candidate_policy_hash=current.candidate_policy_hash,
            stable_policy_hash=current.stable_policy_hash,
            previous_stable_deployment_id=current.previous_stable_deployment_id,
            traffic_basis_points=0, assignment_salt_id=current.assignment_salt_id,
            thresholds=current.thresholds, thresholds_hash=current.thresholds_hash,
            required_receipts=current.required_receipts, command_id=command_id,
            actor="run-admission", reason="selected artifact unavailable or incompatible", created_at=now,
        )
        session.add(frozen)
        await session.flush()
        head.current_deployment_id, head.current_version = frozen.deployment_id, frozen.version
        head.updated_at = now
        session.add(PolicyAuditEventRecord(
            event_id=str(uuid4()), environment=current.environment,
            deployment_id=frozen.deployment_id, event_type="admission_artifact_rejected",
            command_id=command_id, actor="run-admission", reason=frozen.reason,
            details={"failed_deployment_id": deployment_id, "failed_version": version}, created_at=now,
        ))
        session.add(DistributedOutbox(
            event_key=f"policy:{frozen.deployment_id}:changed", topic="policy.deployment.changed",
            payload={"environment": current.environment, "deployment_id": frozen.deployment_id,
                     "version": frozen.version}, created_at=now, publish_attempts=0,
        ))
        await session.flush()
        return True

    async def register_qualification(
        self,
        material: QualificationMaterial,
        *,
        actor: str,
        command_id: str,
    ) -> DeploymentSnapshot:
        material = QualificationMaterial.model_validate(material)
        material_hash = canonical_hash(material.model_dump(mode="json"))
        command_hash = canonical_hash(
            {
                "command_type": "register_qualification",
                "material_hash": material_hash,
                "actor": actor,
            }
        )

        async with self.session_factory() as session, session.begin():
            self._validate_material(material)
            replay = await self._find_registration_replay(
                session,
                command_id=command_id,
                command_hash=command_hash,
                material=material,
                material_hash=material_hash,
                actor=actor,
            )
            if replay is not None:
                return self._deployment(replay)

            now = self.clock()
            await self._insert_or_compare_artifact(session, material.artifact)
            for receipt in material.receipts:
                await self._insert_or_compare_receipt(session, receipt, now)

            await self._verify_latest_receipts(session, material)
            head = await session.scalar(
                select(PolicyEnvironmentHeadRecord)
                .where(
                    PolicyEnvironmentHeadRecord.environment == "rehearsal"
                )
                .with_for_update()
            )
            replay = await self._find_registration_replay(
                session,
                command_id=command_id,
                command_hash=command_hash,
                material=material,
                material_hash=material_hash,
                actor=actor,
            )
            if replay is not None:
                return self._deployment(replay)
            if head is None:
                raise QualificationRejected(
                    "rehearsal deployment head is not initialized"
                )
            await self._verify_latest_receipts(session, material)
            current = await session.get(
                PolicyDeploymentRecord,
                head.current_deployment_id,
            )
            if current is None:
                raise ImmutablePromotionConflict(
                    "rehearsal head references a missing deployment"
                )

            thresholds = PolicyThresholds()
            deployment_id = str(uuid4())
            version = head.current_version + 1
            stable_policy_hash = (
                current.candidate_policy_hash
                if current.state == "active"
                and current.candidate_policy_hash is not None
                else current.stable_policy_hash
            )
            row = PolicyDeploymentRecord(
                deployment_id=deployment_id,
                environment="rehearsal",
                version=version,
                state="registered",
                candidate_policy_hash=material.artifact.policy_hash,
                stable_policy_hash=stable_policy_hash,
                previous_stable_deployment_id=current.deployment_id,
                traffic_basis_points=0,
                assignment_salt_id=(
                    f"registration-{material.artifact.policy_hash[:16]}"
                ),
                thresholds=thresholds.model_dump(mode="json"),
                thresholds_hash=thresholds.digest,
                required_receipts=list(REQUIRED_QUALIFICATION_GATES),
                command_id=command_id,
                reason=(
                    f"qualification registered for campaign "
                    f"{material.campaign_id}"
                ),
                actor=actor,
                created_at=now,
            )
            session.add(row)
            await session.flush()
            head.current_deployment_id = deployment_id
            head.current_version = version
            head.updated_at = now
            session.add(
                PolicyAuditEventRecord(
                    event_id=str(uuid4()),
                    environment="rehearsal",
                    deployment_id=deployment_id,
                    event_type="qualification_registered",
                    command_id=command_id,
                    actor=actor,
                    reason="immutable qualification evidence registered",
                    details={
                        **self._registration_details(
                            material, material_hash, stable_policy_hash
                        ),
                        "command_hash": command_hash,
                    },
                    created_at=now,
                )
            )
            return self._deployment(row)

    async def get_head(self, environment: str) -> DeploymentSnapshot:
        async with self.session_factory() as session:
            head = await session.get(PolicyEnvironmentHeadRecord, environment)
            if head is None:
                raise LookupError(f"{environment} deployment head is not initialized")
            row = await session.get(
                PolicyDeploymentRecord,
                head.current_deployment_id,
            )
            if row is None:
                raise ImmutablePromotionConflict(
                    f"{environment} head references a missing deployment"
                )
            return self._deployment(row)

    async def rollback_if_current(self, session, deployment, window) -> bool:
        """Called inside the frozen-window transaction; never rewrites accepted Runs."""
        from .promotion_models import PolicyHealthWindowRecord

        await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                              {"key": "policy-health:" + deployment.environment})
        head = await session.scalar(select(PolicyEnvironmentHeadRecord).where(
            PolicyEnvironmentHeadRecord.environment == deployment.environment
        ).with_for_update().execution_options(populate_existing=True))
        frozen = await session.get(PolicyHealthWindowRecord, window.window_id)
        expected_window_id = canonical_hash({
            "deployment_id": deployment.deployment_id, "deployment_version": deployment.version,
            "metric_contract_version": 1, "thresholds_hash": deployment.thresholds_hash,
            "observation_keys": frozen.observation_keys if frozen is not None else None,
        })
        if (head is None or head.current_deployment_id != deployment.deployment_id
            or head.current_version != deployment.version
            or deployment.state not in {"canary", "active"} or frozen is None
            or frozen.decision != "fail" or frozen.deployment_id != deployment.deployment_id
            or frozen.deployment_version != deployment.version
            or frozen.thresholds_hash != deployment.thresholds_hash
            or frozen.metric_contract_version != 1 or frozen.window_id != expected_window_id):
            return False
        now = await session.scalar(select(func.clock_timestamp()))
        command_id = "health-rollback-" + window.window_id
        row = PolicyDeploymentRecord(
            deployment_id=str(uuid4()), environment=deployment.environment,
            version=deployment.version + 1, state="rolled_back",
            candidate_policy_hash=deployment.candidate_policy_hash,
            stable_policy_hash=deployment.stable_policy_hash,
            previous_stable_deployment_id=deployment.previous_stable_deployment_id,
            traffic_basis_points=0, assignment_salt_id=deployment.assignment_salt_id,
            thresholds=deployment.thresholds, thresholds_hash=deployment.thresholds_hash,
            required_receipts=deployment.required_receipts, command_id=command_id,
            actor="policy-health", reason="health thresholds failed", created_at=now,
        )
        session.add(row)
        await session.flush()
        cas = await session.execute(update(PolicyEnvironmentHeadRecord).where(
            PolicyEnvironmentHeadRecord.environment == deployment.environment,
            PolicyEnvironmentHeadRecord.current_deployment_id == deployment.deployment_id,
            PolicyEnvironmentHeadRecord.current_version == deployment.version,
        ).values(current_deployment_id=row.deployment_id, current_version=row.version, updated_at=now))
        if cas.rowcount != 1:
            raise PromotionVersionConflict("health rollback CAS failed")
        session.add(PolicyAuditEventRecord(
            event_id=str(uuid4()), environment=deployment.environment, deployment_id=row.deployment_id,
            event_type="health_rollback", command_id=command_id, actor="policy-health",
            reason=row.reason, details={"window_id": window.window_id,
                "failed_deployment_id": deployment.deployment_id,
                "failed_version": deployment.version, "thresholds_hash": deployment.thresholds_hash,
                "triggered_thresholds": window.triggered_thresholds}, created_at=now,
        ))
        session.add(DistributedOutbox(
            event_key=f"deployment:{row.deployment_id}:changed", topic="policy.deployment.changed",
            payload={"deployment_id": row.deployment_id, "environment": row.environment,
                     "version": row.version, "state": row.state}, created_at=now, publish_attempts=0,
        ))
        return True

    async def get_snapshot(
        self, environment: str, version: int
    ) -> DeploymentSnapshot:
        """Read the immutable source of a command, never the mutable head."""
        async with self.session_factory() as session:
            row = await session.scalar(
                select(PolicyDeploymentRecord).where(
                    PolicyDeploymentRecord.environment == environment,
                    PolicyDeploymentRecord.version == version,
                )
            )
            if row is None:
                raise LookupError(
                    f"{environment} deployment version {version} does not exist"
                )
            return self._deployment(row)

    async def transition(
        self,
        command: PromotionCommand,
    ) -> DeploymentSnapshot:
        command = PromotionCommand.model_validate(command)
        command_hash = canonical_hash(
            {
                "command_type": "transition",
                "command": command.model_dump(mode="json"),
            }
        )
        rejected: str | None = None
        result: DeploymentSnapshot | None = None

        async with self.session_factory() as session, session.begin():
            replay = await self._find_transition_replay(
                session,
                command=command,
                command_hash=command_hash,
            )
            if replay is not None:
                return self._deployment(replay)

            head = await session.scalar(
                select(PolicyEnvironmentHeadRecord)
                .where(
                    PolicyEnvironmentHeadRecord.environment
                    == command.environment
                )
                .with_for_update()
            )
            replay = await self._find_transition_replay(
                session,
                command=command,
                command_hash=command_hash,
            )
            if replay is not None:
                return self._deployment(replay)
            if head is None:
                raise PromotionVersionConflict(
                    f"{command.environment} deployment head is not initialized"
                )
            current = await session.get(
                PolicyDeploymentRecord,
                head.current_deployment_id,
            )
            if current is None:
                raise ImmutablePromotionConflict(
                    f"{command.environment} head references a missing deployment"
                )

            if command.environment != "rehearsal":
                rejected = "candidate transitions are restricted to rehearsal"
            elif (
                head.current_version != command.expected_version
                or current.version != command.expected_version
            ):
                rejected = (
                    "expected_version conflict: expected "
                    f"{command.expected_version}, current {head.current_version}"
                )
            elif current.state != command.current_state.value:
                rejected = (
                    "current_state conflict: expected "
                    f"{command.current_state.value}, current {current.state}"
                )

            missing_gates: list[str] = []
            gate_rows: dict[str, PolicyGateReceiptRecord] = {}
            artifact: PolicyArtifactRecord | None = None
            if rejected is None:
                if current.candidate_policy_hash is None:
                    rejected = "current deployment has no candidate policy"
                else:
                    artifact = await session.get(
                        PolicyArtifactRecord,
                        current.candidate_policy_hash,
                    )
                    if artifact is None:
                        rejected = "candidate policy artifact is missing"
            if rejected is None and artifact is not None:
                required = REQUIRED_EXTERNAL_GATES.get(
                    command.target_state,
                    set(),
                )
                health_bindings: dict[str, PolicyDeploymentRecord] = {}
                if command.target_state == DeploymentState.CANARY:
                    health_bindings["shadow_health"] = current
                elif command.target_state == DeploymentState.ACTIVE:
                    health_bindings["canary_health"] = current
                    shadow = await session.scalar(
                        select(PolicyDeploymentRecord).where(
                            PolicyDeploymentRecord.environment
                            == current.environment,
                            PolicyDeploymentRecord.version
                            == current.version - 1,
                            PolicyDeploymentRecord.state == "shadow",
                            PolicyDeploymentRecord.candidate_policy_hash
                            == current.candidate_policy_hash,
                        )
                    )
                    if shadow is None:
                        missing_gates.append("shadow_health")
                    else:
                        health_bindings["shadow_health"] = shadow
                bound_missing, gate_rows = await self._bound_gate_receipts(
                    session,
                    artifact=artifact,
                    required=required - set(missing_gates),
                    health_bindings=health_bindings,
                )
                missing_gates.extend(bound_missing)
                missing_gates.sort()
                if missing_gates:
                    rejected = "required gates are missing or invalid: " + ", ".join(
                        missing_gates
                    )

            if rejected is not None:
                await self._append_rejected_audit(
                    session,
                    command=command,
                    current=current,
                    command_hash=command_hash,
                    error=rejected,
                    missing_gates=missing_gates,
                )
            else:
                assert artifact is not None
                now = self.clock()
                required_receipts = sorted(
                    REQUIRED_EXTERNAL_GATES.get(command.target_state, set())
                )
                if command.target_state == DeploymentState.ACTIVE:
                    await self._create_promotion_approval(
                        session,
                        command=command,
                        artifact=artifact,
                        canary_health=gate_rows["canary_health"],
                        command_hash=command_hash,
                        now=now,
                    )
                    required_receipts.append("promotion_approval")

                deployment_id = str(uuid4())
                row = PolicyDeploymentRecord(
                    deployment_id=deployment_id,
                    environment=current.environment,
                    version=current.version + 1,
                    state=command.target_state.value,
                    candidate_policy_hash=current.candidate_policy_hash,
                    stable_policy_hash=current.stable_policy_hash,
                    previous_stable_deployment_id=(
                        current.previous_stable_deployment_id
                    ),
                    traffic_basis_points=command.traffic_basis_points,
                    assignment_salt_id=current.assignment_salt_id,
                    thresholds=current.thresholds,
                    thresholds_hash=current.thresholds_hash,
                    required_receipts=required_receipts,
                    command_id=command.command_id,
                    reason=command.reason,
                    actor=command.actor,
                    created_at=now,
                )
                session.add(row)
                await session.flush()
                cas = await session.execute(
                    update(PolicyEnvironmentHeadRecord)
                    .where(
                        PolicyEnvironmentHeadRecord.environment
                        == command.environment,
                        PolicyEnvironmentHeadRecord.current_version
                        == command.expected_version,
                        PolicyEnvironmentHeadRecord.current_deployment_id
                        == current.deployment_id,
                    )
                    .values(
                        current_deployment_id=deployment_id,
                        current_version=row.version,
                        updated_at=now,
                    )
                )
                if cas.rowcount != 1:
                    raise PromotionVersionConflict(
                        "deployment head changed during CAS transition"
                    )
                session.add(
                    PolicyAuditEventRecord(
                        event_id=str(uuid4()),
                        environment=command.environment,
                        deployment_id=deployment_id,
                        event_type="promotion_transitioned",
                        command_id=command.command_id,
                        actor=command.actor,
                        reason=command.reason,
                        details={
                            "command_hash": command_hash,
                            "from_state": current.state,
                            "to_state": command.target_state.value,
                            "from_version": current.version,
                            "to_version": row.version,
                            "required_receipts": required_receipts,
                        },
                        created_at=now,
                    )
                )
                session.add(
                    DistributedOutbox(
                        event_key=f"deployment:{deployment_id}:changed",
                        topic="policy.deployment.changed",
                        payload={
                            "deployment_id": deployment_id,
                            "environment": command.environment,
                            "version": row.version,
                            "state": command.target_state.value,
                        },
                        created_at=now,
                        publish_attempts=0,
                    )
                )
                result = self._deployment(row)

        if rejected is not None:
            if rejected.startswith("expected_version"):
                raise PromotionVersionConflict(rejected)
            raise PromotionCommandRejected(rejected)
        assert result is not None
        return result

    @staticmethod
    async def _command_evidence(
        session: AsyncSession, command_id: str,
    ) -> tuple[PolicyDeploymentRecord | None, PolicyAuditEventRecord | None]:
        # One READ COMMITTED statement snapshot, including orphaned evidence.
        # Joining on command_id (not deployment_id) keeps rejections row-less.
        evidence = (await session.execute(
            select(PolicyDeploymentRecord, PolicyAuditEventRecord)
            .outerjoin(
                PolicyAuditEventRecord,
                PolicyDeploymentRecord.command_id == PolicyAuditEventRecord.command_id,
                full=True,
            )
            .where(or_(
                PolicyDeploymentRecord.command_id == command_id,
                PolicyAuditEventRecord.command_id == command_id,
            ))
        )).one_or_none()
        return (None, None) if evidence is None else (evidence[0], evidence[1])

    @staticmethod
    async def _find_transition_replay(
        session: AsyncSession,
        *,
        command: PromotionCommand,
        command_hash: str,
    ) -> PolicyDeploymentRecord | None:
        row, audit = await PromotionRepository._command_evidence(
            session, command.command_id
        )
        if row is None and audit is None:
            return None
        expected_event = "promotion_rejected" if row is None else "promotion_transitioned"
        legacy_hash = canonical_hash(command.model_dump(mode="json"))
        if (
            audit is None
            or audit.event_type != expected_event
            or audit.details.get("command_hash") not in {command_hash, legacy_hash}
            or audit.environment != command.environment
            or audit.actor != command.actor
            or audit.reason != command.reason
        ):
            raise ImmutablePromotionConflict(
                "command_id is bound to another promotion payload"
            )
        if row is None:
            raise PromotionCommandRejected(
                audit.details.get("error", "promotion command was rejected")
            )
        if (
            row.deployment_id != audit.deployment_id
            or row.environment != command.environment
            or row.version != command.expected_version + 1
            or row.state != command.target_state.value
            or row.traffic_basis_points != command.traffic_basis_points
            or row.actor != command.actor
            or row.reason != command.reason
            or audit.details.get("from_state") != command.current_state.value
            or audit.details.get("from_version") != command.expected_version
            or audit.details.get("to_state") != row.state
            or audit.details.get("to_version") != row.version
        ):
            raise ImmutablePromotionConflict(
                "command_id is bound to another promotion payload"
            )
        return row

    @staticmethod
    async def _validated_health_window(
        session, *, artifact, deployment, gate_type, receipt,
    ):
        """Validate frozen evidence, not just the receipt's claimed status."""
        from .health_evidence_identity import frozen_leaf_identity_matches
        from .policy_health import _observation, evaluate_window

        cohort = "shadow" if gate_type == "shadow_health" else "candidate"
        if (
            receipt is None or receipt.status != "passed"
            or deployment.state != ("shadow" if cohort == "shadow" else "canary")
            or receipt.gate_type != gate_type or receipt.policy_hash != artifact.policy_hash
            or artifact.policy_hash != deployment.candidate_policy_hash
            or receipt.protocol_hash != artifact.protocol_hash
            or receipt.runtime_hash != artifact.runtime_hash
            or receipt.source_revision != artifact.source_revision
            or receipt.data_role != artifact.data_role
            or receipt.issuer != "policy-health"
            or receipt.model_identity != "server-policy-health-v1"
            or not isinstance(receipt.details, dict)
        ):
            return None
        try:
            thresholds = PolicyThresholds.model_validate(deployment.thresholds)
            details = receipt.details
            window_id = details.get("window_id")
            if not isinstance(window_id, str) or len(window_id) != 64:
                return None
            window = await session.get(PolicyHealthWindowRecord, window_id)
            if window is None or window.decision != "pass" or window.triggered_thresholds:
                return None
            keys = window.observation_keys
            if not isinstance(keys, dict) or set(keys) != {"candidate", "stable"}:
                return None
            for label, minimum in (("candidate", thresholds.candidate_min_runs),
                                   ("stable", thresholds.stable_min_runs)):
                if (not isinstance(keys[label], list)
                    or not minimum <= len(keys[label]) <= thresholds.window_max_runs
                    or any(not isinstance(key, str) or len(key) != 64 for key in keys[label])
                    or len(set(keys[label])) != len(keys[label])):
                    return None
            flat = keys["candidate"] + keys["stable"]
            identity = {
                "deployment_id": deployment.deployment_id,
                "deployment_version": deployment.version,
                "metric_contract_version": 1, "thresholds_hash": thresholds.digest,
                "observation_keys": keys,
            }
            if (
                thresholds.digest != deployment.thresholds_hash
                or canonical_hash({key: details.get(key) for key in identity}) != canonical_hash(identity)
                or details.get("gate_cohort") != cohort
                or window.window_id != canonical_hash(identity)
                or window.deployment_id != deployment.deployment_id
                or window.deployment_version != deployment.version
                or window.metric_contract_version != 1
                or window.thresholds_hash != thresholds.digest
                or details.get("candidate_stats") != window.candidate_stats
                or details.get("stable_stats") != window.stable_stats
                or receipt.evidence_hash != canonical_hash(details)
                or receipt.sample_count != len(keys["candidate"])
                or receipt.issued_at < window.evaluated_at
            ):
                return None
            records = (await session.scalars(select(PolicyObservationRecord).where(
                PolicyObservationRecord.observation_key.in_(flat)
            ).limit(2 * thresholds.window_max_runs))).all()
            by_key = {row.observation_key: row for row in records}
            if len(by_key) != len(flat):
                return None
            candidate = [_observation(by_key[key]) for key in keys["candidate"]]
            stable = [_observation(by_key[key]) for key in keys["stable"]]
            if not frozen_leaf_identity_matches(
                candidate, stable, window, cohort=cohort, passed=True,
                max_runs=thresholds.window_max_runs,
            ):
                return None
            for rows, expected_cohort, policy_hash in (
                (candidate, cohort, deployment.candidate_policy_hash),
                (stable, "stable", deployment.stable_policy_hash),
            ):
                if rows != sorted(rows, key=lambda row: (row.observed_at, row.observation_key)):
                    return None
                if any(
                    str(row.deployment_id) != deployment.deployment_id
                    or row.cohort != expected_cohort or row.policy_hash != policy_hash
                    or row.metric_contract_version != 1
                    or row.observed_at > window.evaluated_at
                    or by_key[row.observation_key].created_at > window.evaluated_at
                    for row in rows
                ):
                    return None
            result = evaluate_window(candidate, stable, thresholds)
            if (
                result.decision != "pass"
                or result.candidate_stats != window.candidate_stats
                or result.stable_stats != window.stable_stats
                or any(row.cost is None for row in candidate + stable)
                or receipt.cost != sum((row.cost for row in candidate + stable), Decimal(0))
            ):
                return None
            return window
        except (ValueError, TypeError, KeyError, InvalidOperation):
            return None

    async def _active_health_source(self, session, deployment):
        """Validate the exact Canary/window actually consumed by this activation."""
        if deployment.environment != "rehearsal":
            return None
        canary = await session.scalar(select(PolicyDeploymentRecord).where(
            PolicyDeploymentRecord.environment == deployment.environment,
            PolicyDeploymentRecord.version == deployment.version - 1,
            PolicyDeploymentRecord.state == "canary",
            PolicyDeploymentRecord.candidate_policy_hash == deployment.candidate_policy_hash,
            PolicyDeploymentRecord.stable_policy_hash == deployment.stable_policy_hash,
            PolicyDeploymentRecord.thresholds_hash == deployment.thresholds_hash,
        ))
        if canary is None or canary.created_at > deployment.created_at:
            return None
        audit = await session.scalar(select(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.command_id == deployment.command_id,
            PolicyAuditEventRecord.deployment_id == deployment.deployment_id,
            PolicyAuditEventRecord.event_type == "promotion_transitioned",
        ))
        approval = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.policy_hash == deployment.candidate_policy_hash,
            PolicyGateReceiptRecord.gate_type == "promotion_approval",
            PolicyGateReceiptRecord.details["command_id"].as_string() == deployment.command_id,
        ).limit(1))
        if audit is None or approval is None or not isinstance(approval.details, dict):
            return None
        details = approval.details
        if (
            approval.status != "passed" or approval.evidence_hash != canonical_hash(details)
            or approval.issued_at != deployment.created_at
            or details.get("command_hash") != audit.details.get("command_hash")
            or audit.details.get("from_state") != "canary"
            or audit.details.get("from_version") != canary.version
            or audit.details.get("to_state") != "active"
            or audit.details.get("to_version") != deployment.version
            or details.get("canary_deployment_id") != canary.deployment_id
            or details.get("canary_deployment_version") != canary.version
            or details.get("canary_thresholds_hash") != canary.thresholds_hash
            or details.get("actor") != deployment.actor or details.get("reason") != deployment.reason
        ):
            return None
        receipt_id = details.get("canary_health_receipt_id")
        if not isinstance(receipt_id, str):
            return None
        receipt = await session.get(PolicyGateReceiptRecord, receipt_id)
        artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
        if (
            receipt is None or artifact is None or receipt.issued_at > deployment.created_at
            or receipt.evidence_hash != details.get("canary_health_evidence_hash")
            or approval.protocol_hash != artifact.protocol_hash
            or approval.runtime_hash != artifact.runtime_hash
            or approval.source_revision != artifact.source_revision
        ):
            return None
        window = await self._validated_health_window(
            session, artifact=artifact, deployment=canary, gate_type="canary_health", receipt=receipt)
        if window is None:
            return None
        return canary, window

    async def active_health_baseline(self, session, deployment):
        """Use only stable keys in the validated consumed Canary window."""
        source = await self._active_health_source(session, deployment)
        if source is None:
            return []
        canary, window = source
        return list((await session.scalars(select(PolicyObservationRecord).where(
            PolicyObservationRecord.observation_key.in_(window.observation_keys["stable"]),
            PolicyObservationRecord.observed_at >= canary.created_at,
            PolicyObservationRecord.observed_at <= deployment.created_at,
            PolicyObservationRecord.created_at <= deployment.created_at,
        ).limit(PolicyThresholds.model_validate(deployment.thresholds).window_max_runs))).all())

    async def health_predecessors(self, session, deployment):
        """Bound hard-event inheritance to this audited promotion chain, never policy history."""
        sources = []
        canary = deployment
        if deployment.state == "active":
            source = await self._active_health_source(session, deployment)
            if source is None:
                return sources
            canary, _ = source
            sources.append(canary)
        if canary.state != "canary" or canary.environment != "rehearsal":
            return sources
        shadow = await session.scalar(select(PolicyDeploymentRecord).where(
            PolicyDeploymentRecord.environment == canary.environment,
            PolicyDeploymentRecord.version == canary.version - 1,
            PolicyDeploymentRecord.state == "shadow",
            PolicyDeploymentRecord.candidate_policy_hash == canary.candidate_policy_hash,
            PolicyDeploymentRecord.stable_policy_hash == canary.stable_policy_hash,
            PolicyDeploymentRecord.thresholds_hash == canary.thresholds_hash,
            PolicyDeploymentRecord.assignment_salt_id == canary.assignment_salt_id,
            PolicyDeploymentRecord.previous_stable_deployment_id == canary.previous_stable_deployment_id,
        ))
        if shadow is None or shadow.created_at > canary.created_at:
            return sources
        audit = await session.scalar(select(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.command_id == canary.command_id,
            PolicyAuditEventRecord.deployment_id == canary.deployment_id,
            PolicyAuditEventRecord.environment == canary.environment,
            PolicyAuditEventRecord.event_type == "promotion_transitioned",
        ))
        if (
            audit is not None and isinstance(audit.details, dict)
            and audit.created_at == canary.created_at
            and audit.details.get("from_state") == "shadow"
            and audit.details.get("from_version") == shadow.version
            and audit.details.get("to_state") == "canary"
            and audit.details.get("to_version") == canary.version
            and "shadow_health" in audit.details.get("required_receipts", [])
        ):
            sources.append(shadow)
        return sources

    @staticmethod
    async def _bound_gate_receipts(
        session: AsyncSession,
        *,
        artifact: PolicyArtifactRecord,
        required: set[str],
        health_bindings: dict[str, PolicyDeploymentRecord],
    ) -> tuple[list[str], dict[str, PolicyGateReceiptRecord]]:
        missing: list[str] = []
        rows: dict[str, PolicyGateReceiptRecord] = {}
        for gate_type in sorted(required):
            query = select(PolicyGateReceiptRecord).where(
                PolicyGateReceiptRecord.policy_hash == artifact.policy_hash,
                PolicyGateReceiptRecord.gate_type == gate_type,
                PolicyGateReceiptRecord.protocol_hash
                == artifact.protocol_hash,
                PolicyGateReceiptRecord.runtime_hash == artifact.runtime_hash,
                PolicyGateReceiptRecord.source_revision
                == artifact.source_revision,
            )
            if gate_type in {"shadow_health", "canary_health"}:
                deployment = health_bindings.get(gate_type)
                if deployment is None:
                    missing.append(gate_type)
                    continue
                hard_failure = await session.scalar(select(PolicyObservationRecord.observation_key).where(
                    PolicyObservationRecord.deployment_id == deployment.deployment_id,
                    PolicyObservationRecord.metric_contract_version == 1,
                    PolicyObservationRecord.cohort == ("shadow" if gate_type == "shadow_health" else "candidate"),
                    PolicyObservationRecord.policy_hash == artifact.policy_hash,
                    PolicyObservationRecord.permission_outcome == "confirmed_violation",
                    PolicyObservationRecord.terminal_status == "confirmed_permission_violation",
                    PolicyObservationRecord.server_error_code == "ConfirmedPermissionViolation",
                ).limit(1))
                latest_window = await session.scalar(select(PolicyHealthWindowRecord).where(
                    PolicyHealthWindowRecord.deployment_id == deployment.deployment_id,
                    PolicyHealthWindowRecord.deployment_version == deployment.version,
                    PolicyHealthWindowRecord.thresholds_hash == deployment.thresholds_hash,
                    PolicyHealthWindowRecord.metric_contract_version == 1,
                ).order_by(PolicyHealthWindowRecord.evaluated_at.desc(),
                           PolicyHealthWindowRecord.window_id.desc()).limit(1))
                if hard_failure is not None or latest_window is None or latest_window.decision != "pass":
                    missing.append(gate_type)
                    continue
                query = query.where(
                    PolicyGateReceiptRecord.details[
                        "deployment_id"
                    ].as_string()
                    == deployment.deployment_id,
                    PolicyGateReceiptRecord.details[
                        "deployment_version"
                    ].as_integer()
                    == deployment.version,
                    PolicyGateReceiptRecord.details[
                        "thresholds_hash"
                    ].as_string()
                    == deployment.thresholds_hash,
                )
            receipt = await session.scalar(
                query.order_by(
                    PolicyGateReceiptRecord.issued_at.desc(),
                    PolicyGateReceiptRecord.created_at.desc(),
                    PolicyGateReceiptRecord.receipt_id.desc(),
                ).limit(1)
            )
            valid_health = True
            if gate_type in {"shadow_health", "canary_health"} and receipt is not None:
                frozen = await PromotionRepository._validated_health_window(
                    session, artifact=artifact, deployment=deployment, gate_type=gate_type, receipt=receipt)
                valid_health = frozen is not None and frozen.window_id == latest_window.window_id
            if receipt is None or receipt.status != "passed" or not valid_health:
                missing.append(gate_type)
            else:
                rows[gate_type] = receipt
        return missing, rows

    async def _append_rejected_audit(
        self,
        session: AsyncSession,
        *,
        command: PromotionCommand,
        current: PolicyDeploymentRecord,
        command_hash: str,
        error: str,
        missing_gates: list[str],
    ) -> None:
        now = self.clock()
        await session.execute(
            pg_insert(PolicyAuditEventRecord)
            .values(
                event_id=str(uuid4()),
                environment=command.environment,
                deployment_id=current.deployment_id,
                event_type="promotion_rejected",
                command_id=command.command_id,
                actor=command.actor,
                reason=command.reason,
                details={
                    "command_hash": command_hash,
                    "error": error,
                    "expected_version": command.expected_version,
                    "current_version": current.version,
                    "current_state": current.state,
                    "target_state": command.target_state.value,
                    "missing_gates": missing_gates,
                },
                created_at=now,
            )
            .on_conflict_do_nothing(
                constraint="uq_policy_audit_command_deployment_event_type"
            )
        )

    @staticmethod
    async def _create_promotion_approval(
        session: AsyncSession,
        *,
        command: PromotionCommand,
        artifact: PolicyArtifactRecord,
        canary_health: PolicyGateReceiptRecord,
        command_hash: str,
        now: datetime,
    ) -> None:
        receipt_id = str(uuid4())
        details = {
            "actor": command.actor,
            "reason": command.reason,
            "command_id": command.command_id,
            "command_hash": command_hash,
            "canary_health_receipt_id": canary_health.receipt_id,
            "canary_health_evidence_hash": canary_health.evidence_hash,
            "canary_deployment_id": canary_health.details["deployment_id"],
            "canary_deployment_version": canary_health.details[
                "deployment_version"
            ],
            "canary_thresholds_hash": canary_health.details[
                "thresholds_hash"
            ],
        }
        session.add(
            PolicyGateReceiptRecord(
                receipt_id=receipt_id,
                policy_hash=artifact.policy_hash,
                gate_type="promotion_approval",
                status="passed",
                evidence_hash=canonical_hash(details),
                protocol_hash=artifact.protocol_hash,
                runtime_hash=artifact.runtime_hash,
                source_revision=artifact.source_revision,
                model_identity="authenticated-promotion-command",
                data_role=artifact.data_role,
                sample_count=canary_health.sample_count,
                cost=Decimal("0"),
                details=details,
                issued_at=now,
                issuer=command.actor,
                created_at=now,
            )
        )

    @staticmethod
    def _artifact_hash(artifact: PolicyArtifact) -> str:
        body = {
            "schema_version": 1,
            "parent_policy_hash": artifact.parent_policy_hash,
            "components": artifact.components.model_dump(mode="json"),
            "fixed_components_hash": artifact.fixed_components_hash,
            "proposer_hash": artifact.proposer_hash,
            "protocol_hash": artifact.protocol_hash,
            "runtime_hash": artifact.runtime_hash,
            "source_revision": artifact.source_revision,
            "data_role": artifact.data_role,
            "evidence_paths": artifact.evidence_bindings,
            "created_at": artifact.created_at.isoformat(),
        }
        return canonical_hash(body)

    def _validate_material(self, material: QualificationMaterial) -> None:
        artifact = material.artifact
        if artifact.data_role != "holdout_validated":
            raise QualificationRejected(
                "candidate artifact must use data_role=holdout_validated"
            )
        if self._artifact_hash(artifact) != artifact.policy_hash:
            raise QualificationRejected("artifact canonical hash mismatch")
        if set(receipt.gate_type for receipt in material.receipts) != set(
            REQUIRED_QUALIFICATION_GATES
        ):
            raise QualificationRejected(
                "qualification requires exactly four release receipts"
            )

        try:
            expected_cost = Decimal(str(material.budget.estimated_peak_cny))
        except (InvalidOperation, ValueError):
            raise QualificationRejected("shared budget cost is invalid") from None
        expected_budget = material.budget.model_dump(mode="json")
        expected_judge_protocol_hash = self.judge_protocol_digest()
        model_identities: set[str] = set()
        for receipt in material.receipts:
            if receipt.status != "passed":
                raise QualificationRejected(
                    f"{receipt.gate_type} receipt status is {receipt.status}"
                )
            bindings = {
                "policy_hash": artifact.policy_hash,
                "protocol_hash": artifact.protocol_hash,
                "runtime_hash": artifact.runtime_hash,
                "source_revision": artifact.source_revision,
                "data_role": "holdout_validated",
            }
            for field, expected in bindings.items():
                if getattr(receipt, field) != expected:
                    raise QualificationRejected(
                        f"receipt {field} does not match candidate"
                    )
            if not receipt.model_identity.strip():
                raise QualificationRejected(
                    "receipt model_identity is required"
                )
            model_identities.add(receipt.model_identity)
            details = receipt.details
            if details.get("campaign_id") != material.campaign_id:
                raise QualificationRejected(
                    "receipt campaign_id does not match material"
                )
            if (
                details.get("campaign_binding")
                != material.campaign_binding
            ):
                raise QualificationRejected(
                    "receipt campaign_binding does not match material"
                )
            if details.get("judge_protocol_version") != 3:
                raise QualificationRejected(
                    "candidate registration requires Judge v3"
                )
            judge_protocol_hash = details.get("judge_protocol_hash")
            if judge_protocol_hash != expected_judge_protocol_hash:
                raise QualificationRejected(
                    "Judge v3 protocol hash does not match current Judge v3"
                )
            if details.get("budget") != expected_budget:
                raise QualificationRejected(
                    "receipt budget does not match shared budget"
                )
            if receipt.cost != expected_cost:
                raise QualificationRejected(
                    "receipt cost does not match shared budget"
                )
        if len(model_identities) != 1:
            raise QualificationRejected(
                "receipts use inconsistent model_identity"
            )

    @staticmethod
    def _registration_details(
        material: QualificationMaterial,
        material_hash: str,
        stable_policy_hash: str,
    ) -> dict:
        return {
            "campaign_id": material.campaign_id,
            "campaign_binding": material.campaign_binding,
            "candidate_policy_hash": material.artifact.policy_hash,
            "stable_policy_hash": stable_policy_hash,
            "receipt_ids": [str(receipt.receipt_id) for receipt in material.receipts],
            "budget": material.budget.model_dump(mode="json"),
            "material_hash": material_hash,
        }

    @staticmethod
    async def _find_registration_replay(
        session: AsyncSession,
        *,
        command_id: str,
        command_hash: str,
        material: QualificationMaterial,
        material_hash: str,
        actor: str,
    ) -> PolicyDeploymentRecord | None:
        replay, audit = await PromotionRepository._command_evidence(
            session, command_id
        )
        if audit is None and replay is None:
            return None
        if (
            audit is None
            or audit.event_type != "qualification_registered"
            or audit.environment != "rehearsal"
            or audit.actor != actor
            or replay is None
            or replay.deployment_id != audit.deployment_id
            or replay.environment != "rehearsal"
            or replay.state != "registered"
            or replay.actor != actor
            or replay.candidate_policy_hash != material.artifact.policy_hash
        ):
            raise ImmutablePromotionConflict(
                "command_id is bound to another promotion command"
            )
        expected_details = PromotionRepository._registration_details(
            material, material_hash, replay.stable_policy_hash
        )
        # Only the exact 1fc25ab body may omit command_hash. A present but
        # incorrect hash must never fall back to legacy evidence.
        if "command_hash" in audit.details:
            expected_details["command_hash"] = command_hash
        if audit.details != expected_details:
            raise ImmutablePromotionConflict(
                "command_id is bound to another promotion command"
            )
        return replay

    @staticmethod
    async def _insert_or_compare_artifact(
        session: AsyncSession,
        artifact: PolicyArtifact,
    ) -> None:
        values = {
            "policy_hash": artifact.policy_hash,
            "parent_policy_hash": artifact.parent_policy_hash,
            "components": artifact.components.model_dump(mode="json"),
            "fixed_components_hash": artifact.fixed_components_hash,
            "runtime_hash": artifact.runtime_hash,
            "source_revision": artifact.source_revision,
            "protocol_hash": artifact.protocol_hash,
            "proposer_hash": artifact.proposer_hash,
            "data_role": artifact.data_role,
            "evidence_bindings": artifact.evidence_bindings,
            "created_at": artifact.created_at,
        }
        inserted = await session.scalar(
            pg_insert(PolicyArtifactRecord)
            .values(**values)
            .on_conflict_do_nothing()
            .returning(PolicyArtifactRecord.policy_hash)
        )
        if inserted is not None:
            return
        existing = await session.get(
            PolicyArtifactRecord,
            artifact.policy_hash,
        )
        if existing is None or PolicyArtifact.model_validate(
            {
                key: getattr(existing, key)
                for key in values
            }
        ) != artifact:
            raise ImmutablePromotionConflict(
                "immutable artifact hash collision"
            )

    @staticmethod
    async def _insert_or_compare_receipt(
        session: AsyncSession,
        receipt: GateReceipt,
        now: datetime,
    ) -> None:
        values = receipt.model_dump(mode="python")
        values["receipt_id"] = str(receipt.receipt_id)
        values["created_at"] = now
        inserted = await session.scalar(
            pg_insert(PolicyGateReceiptRecord)
            .values(**values)
            .on_conflict_do_nothing()
            .returning(PolicyGateReceiptRecord.receipt_id)
        )
        if inserted is not None:
            return
        existing = await session.get(
            PolicyGateReceiptRecord,
            str(receipt.receipt_id),
        )
        if existing is None:
            existing = await session.scalar(
                select(PolicyGateReceiptRecord).where(
                    PolicyGateReceiptRecord.policy_hash
                    == receipt.policy_hash,
                    PolicyGateReceiptRecord.gate_type
                    == receipt.gate_type,
                    PolicyGateReceiptRecord.evidence_hash
                    == receipt.evidence_hash,
                )
            )
        if existing is None or PromotionRepository._receipt(existing) != receipt:
            raise ImmutablePromotionConflict(
                "immutable qualification receipt collision"
            )

    @staticmethod
    async def _verify_latest_receipts(
        session: AsyncSession,
        material: QualificationMaterial,
    ) -> None:
        expected_by_gate = {
            receipt.gate_type: receipt for receipt in material.receipts
        }
        for gate_type in REQUIRED_QUALIFICATION_GATES:
            latest = await session.scalar(
                select(PolicyGateReceiptRecord)
                .where(
                    PolicyGateReceiptRecord.policy_hash
                    == material.artifact.policy_hash,
                    PolicyGateReceiptRecord.gate_type == gate_type,
                    PolicyGateReceiptRecord.protocol_hash
                    == material.artifact.protocol_hash,
                    PolicyGateReceiptRecord.runtime_hash
                    == material.artifact.runtime_hash,
                    PolicyGateReceiptRecord.source_revision
                    == material.artifact.source_revision,
                )
                .order_by(
                    PolicyGateReceiptRecord.issued_at.desc(),
                    PolicyGateReceiptRecord.created_at.desc(),
                    PolicyGateReceiptRecord.receipt_id.desc(),
                )
                .limit(1)
            )
            if latest is None or latest.status != "passed":
                status = latest.status if latest is not None else "missing"
                raise QualificationRejected(
                    f"latest {gate_type} receipt is {status}"
                )
            try:
                matches = (
                    PromotionRepository._receipt(latest)
                    == expected_by_gate[gate_type]
                )
            except ValueError:
                matches = False
            if not matches:
                raise QualificationRejected(
                    f"latest {gate_type} receipt does not match material"
                )

    @staticmethod
    def _receipt(row: PolicyGateReceiptRecord) -> GateReceipt:
        return GateReceipt.model_validate(
            {
                "receipt_id": UUID(row.receipt_id),
                "policy_hash": row.policy_hash,
                "gate_type": row.gate_type,
                "status": row.status,
                "evidence_hash": row.evidence_hash,
                "protocol_hash": row.protocol_hash,
                "runtime_hash": row.runtime_hash,
                "source_revision": row.source_revision,
                "model_identity": row.model_identity,
                "data_role": row.data_role,
                "sample_count": row.sample_count,
                "cost": row.cost,
                "details": row.details,
                "issued_at": row.issued_at,
                "issuer": row.issuer,
            }
        )

    @staticmethod
    def _deployment(row: PolicyDeploymentRecord) -> DeploymentSnapshot:
        return DeploymentSnapshot.model_validate(
            {
                "deployment_id": UUID(row.deployment_id),
                "environment": row.environment,
                "version": row.version,
                "state": row.state,
                "candidate_policy_hash": row.candidate_policy_hash,
                "stable_policy_hash": row.stable_policy_hash,
                "previous_stable_deployment_id": (
                    UUID(row.previous_stable_deployment_id)
                    if row.previous_stable_deployment_id
                    else None
                ),
                "traffic_basis_points": row.traffic_basis_points,
                "assignment_salt_id": row.assignment_salt_id,
                "thresholds": row.thresholds,
                "required_receipts": row.required_receipts,
                "command_id": row.command_id,
                "reason": row.reason,
                "actor": row.actor,
                "created_at": row.created_at,
            }
        )
