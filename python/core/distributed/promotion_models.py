from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import DistributedBase, new_id


class PolicyArtifactRecord(DistributedBase):
    __tablename__ = "policy_artifacts"

    policy_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    parent_policy_hash: Mapped[str | None] = mapped_column(
        ForeignKey("policy_artifacts.policy_hash")
    )
    components: Mapped[dict] = mapped_column(JSON, nullable=False)
    fixed_components_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    protocol_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    proposer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    data_role: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_bindings: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class PolicyGateReceiptRecord(DistributedBase):
    __tablename__ = "policy_gate_receipts"

    receipt_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_id
    )
    policy_hash: Mapped[str] = mapped_column(
        ForeignKey("policy_artifacts.policy_hash"), nullable=False
    )
    gate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    protocol_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    model_identity: Mapped[str] = mapped_column(String(256), nullable=False)
    data_role: Mapped[str] = mapped_column(String(64), nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cost: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    issuer: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "policy_hash",
            "gate_type",
            "evidence_hash",
            name="uq_policy_gate_evidence",
        ),
    )


class PolicyDeploymentRecord(DistributedBase):
    __tablename__ = "policy_deployments"

    deployment_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_id
    )
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    candidate_policy_hash: Mapped[str | None] = mapped_column(
        ForeignKey("policy_artifacts.policy_hash")
    )
    stable_policy_hash: Mapped[str] = mapped_column(
        ForeignKey("policy_artifacts.policy_hash"), nullable=False
    )
    previous_stable_deployment_id: Mapped[str | None] = mapped_column(
        ForeignKey("policy_deployments.deployment_id")
    )
    traffic_basis_points: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_salt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    thresholds: Mapped[dict] = mapped_column(JSON, nullable=False)
    thresholds_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    required_receipts: Mapped[list] = mapped_column(JSON, nullable=False)
    command_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False
    )
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "environment",
            "version",
            name="uq_policy_deployment_environment_version",
        ),
    )


class PolicyEnvironmentHeadRecord(DistributedBase):
    __tablename__ = "policy_environment_heads"

    environment: Mapped[str] = mapped_column(String(32), primary_key=True)
    current_deployment_id: Mapped[str] = mapped_column(
        ForeignKey("policy_deployments.deployment_id"), nullable=False
    )
    current_version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class RehearsalTokenNonceRecord(DistributedBase):
    __tablename__ = "rehearsal_token_nonces"

    nonce_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    rehearsal_id: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class PolicyObservationRecord(DistributedBase):
    __tablename__ = "policy_observations"

    observation_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_runs.id"), nullable=False
    )
    deployment_id: Mapped[str] = mapped_column(
        ForeignKey("policy_deployments.deployment_id"), nullable=False
    )
    policy_hash: Mapped[str] = mapped_column(
        ForeignKey("policy_artifacts.policy_hash"), nullable=False
    )
    cohort: Mapped[str] = mapped_column(String(16), nullable=False)
    state_namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    metric_contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    terminal_status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_seconds: Mapped[Decimal] = mapped_column(
        Numeric(20, 6), nullable=False
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 8))
    commit_outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    permission_outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    structured_result: Mapped[str] = mapped_column(String(32), nullable=False)
    injected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_trace_id: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        Index(
            "ix_policy_observation_deployment_cohort",
            "deployment_id",
            "cohort",
            "observed_at",
        ),
    )


class PolicyHealthWindowRecord(DistributedBase):
    __tablename__ = "policy_health_windows"

    window_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    deployment_id: Mapped[str] = mapped_column(
        ForeignKey("policy_deployments.deployment_id"), nullable=False
    )
    metric_contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    observation_start_key: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_end_key: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_stats: Mapped[dict] = mapped_column(JSON, nullable=False)
    stable_stats: Mapped[dict] = mapped_column(JSON, nullable=False)
    decision: Mapped[str] = mapped_column(String(16), nullable=False)
    triggered_thresholds: Mapped[list] = mapped_column(JSON, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class PolicyAuditEventRecord(DistributedBase):
    __tablename__ = "policy_audit_events"

    event_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_id
    )
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    deployment_id: Mapped[str | None] = mapped_column(
        ForeignKey("policy_deployments.deployment_id")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    command_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "command_id",
            name="uq_policy_audit_command_deployment_event_type",
        ),
    )


class PolicyShadowExecutionRecord(DistributedBase):
    __tablename__ = "policy_shadow_executions"

    shadow_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_id
    )
    parent_run_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_runs.id"), nullable=False
    )
    deployment_id: Mapped[str] = mapped_column(
        ForeignKey("policy_deployments.deployment_id"), nullable=False
    )
    policy_hash: Mapped[str] = mapped_column(
        ForeignKey("policy_artifacts.policy_hash"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    fencing_token: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    __table_args__ = (
        UniqueConstraint(
            "parent_run_id",
            "deployment_id",
            name="uq_policy_shadow_parent_deployment",
        ),
        Index(
            "ix_policy_shadow_status_lease",
            "status",
            "lease_expires_at",
        ),
        Index(
            "ix_policy_shadow_active_parent",
            "parent_run_id",
            unique=True,
            postgresql_where=text(
                "status IN ('queued', 'leased', 'running')"
            ),
        ),
    )
