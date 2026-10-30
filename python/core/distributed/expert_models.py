from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .models import DistributedBase, new_id


class DistributedExpertJob(DistributedBase):
    __tablename__ = "distributed_expert_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    parent_run_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_runs.id"),
        nullable=False,
    )
    parent_fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    logical_key: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(128))
    deadline_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint(
            "parent_run_id",
            "parent_fencing_token",
            "logical_key",
            name="uq_expert_job_logical_key",
        ),
        Index("ix_expert_job_status_role", "status", "role", "updated_at"),
        Index("ix_expert_job_parent", "parent_run_id", "created_at"),
    )


class DistributedExpertLease(DistributedBase):
    __tablename__ = "distributed_expert_leases"

    job_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_expert_jobs.id"),
        primary_key=True,
    )
    owner: Mapped[str | None] = mapped_column(String(128))
    fencing_token: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class DistributedExpertResult(DistributedBase):
    __tablename__ = "distributed_expert_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_expert_jobs.id"),
        nullable=False,
    )
    expert_fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    disposition: Mapped[str] = mapped_column(String(16), nullable=False)
    rejection_code: Mapped[str | None] = mapped_column(String(128))
    draft: Mapped[dict | None] = mapped_column(JSON)
    usage: Mapped[dict] = mapped_column(JSON, nullable=False)
    diagnostics: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    __table_args__ = (
        Index("ix_expert_result_job_created", "job_id", "created_at"),
        Index(
            "uq_expert_result_accepted",
            "job_id",
            unique=True,
            postgresql_where=text("disposition = 'accepted'"),
        ),
    )


class DistributedExpertOutbox(DistributedBase):
    __tablename__ = "distributed_expert_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_expert_jobs.id"),
        nullable=False,
    )
    event_key: Mapped[str] = mapped_column(String(180), unique=True, nullable=False)
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publish_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )


class DistributedExpertInbox(DistributedBase):
    __tablename__ = "distributed_expert_inbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    consumer: Mapped[str] = mapped_column(String(128), nullable=False)
    message_key: Mapped[str] = mapped_column(String(180), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    __table_args__ = (
        UniqueConstraint(
            "consumer",
            "message_key",
            name="uq_expert_inbox",
        ),
    )


class DistributedWorkerRegistry(DistributedBase):
    __tablename__ = "distributed_worker_registry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    process_type: Mapped[str] = mapped_column(String(64), nullable=False)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    current_run_id: Mapped[str | None] = mapped_column(String(36))
    current_job_id: Mapped[str | None] = mapped_column(String(36))
    capabilities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    registry_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSON,
        default=dict,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_heartbeat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint(
            "worker_id",
            "instance_id",
            name="uq_worker_registry_instance",
        ),
        Index("ix_worker_registry_type_status", "process_type", "status"),
    )
