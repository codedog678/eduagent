from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class DistributedBase(DeclarativeBase):
    pass


def new_id() -> str:
    return str(uuid4())


class DistributedRun(DistributedBase):
    __tablename__ = "distributed_runs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    learner_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    error_code: Mapped[str | None] = mapped_column(String(128))
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
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
    __table_args__ = (
        UniqueConstraint(
            "learner_id",
            "request_id",
            name="uq_distributed_request",
        ),
        Index("ix_distributed_run_status_updated", "status", "updated_at"),
    )

    def public_dict(self) -> dict:
        return {
            "run_id": self.id,
            "learner_id": self.learner_id,
            "request_id": self.request_id,
            "operation": self.operation,
            "status": self.status,
            "attempt_count": self.attempt_count,
            "result": self.result,
            "error_code": self.error_code,
            "trace_id": self.trace_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class DistributedRunAttempt(DistributedBase):
    __tablename__ = "distributed_run_attempts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_runs.id"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "number",
            name="uq_distributed_attempt_number",
        ),
    )


class DistributedStep(DistributedBase):
    __tablename__ = "distributed_steps"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_runs.id"),
        nullable=False,
    )
    step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    result: Mapped[dict | None] = mapped_column(JSON)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "step_id",
            name="uq_distributed_step",
        ),
    )


class DistributedLease(DistributedBase):
    __tablename__ = "distributed_leases"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_runs.id"),
        primary_key=True,
    )
    owner: Mapped[str | None] = mapped_column(String(128))
    fencing_token: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )


class DistributedOutbox(DistributedBase):
    __tablename__ = "distributed_outbox"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
    event_key: Mapped[str] = mapped_column(
        String(180),
        unique=True,
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    publish_attempts: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )


class DistributedInbox(DistributedBase):
    __tablename__ = "distributed_inbox"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_id,
    )
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
            name="uq_distributed_inbox",
        ),
    )


class DistributedTraceSpan(DistributedBase):
    __tablename__ = "distributed_trace_spans"

    span_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(String(32))
    run_id: Mapped[str] = mapped_column(
        ForeignKey("distributed_runs.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    attributes: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    __table_args__ = (
        Index("ix_distributed_trace", "trace_id", "started_at"),
    )

    def public_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "status": self.status,
            "attributes": self.attributes,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
        }
