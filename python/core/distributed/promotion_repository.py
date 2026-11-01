from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid4

from sqlalchemy import or_, select, update
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
)
from .models import DistributedOutbox
from .promotion_service import QualificationMaterial

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


class PromotionRepository:
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
            if receipt is None or receipt.status != "passed":
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
