import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from core.distributed.contracts import RunStatus
from core.distributed.models import (
    DistributedBase,
    DistributedInbox,
    DistributedLease,
    DistributedOutbox,
    DistributedRun,
    DistributedRunAttempt,
    DistributedStep,
    DistributedTraceSpan,
)
from core.distributed.expert_models import (
    DistributedExpertInbox,
    DistributedExpertJob,
    DistributedExpertLease,
    DistributedExpertOutbox,
    DistributedExpertResult,
    DistributedWorkerRegistry,
)
from core.distributed.repository import (
    DistributedRunRepository,
    FencingViolation,
    RequestConflict,
    RunClaim,
)
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


def test_distributed_metadata_contains_run_and_expert_plane_tables():
    assert set(DistributedBase.metadata.tables) == {
        "distributed_runs",
        "distributed_run_attempts",
        "distributed_steps",
        "distributed_leases",
        "distributed_outbox",
        "distributed_inbox",
        "distributed_trace_spans",
        "distributed_expert_jobs",
        "distributed_expert_leases",
        "distributed_expert_results",
        "distributed_expert_outbox",
        "distributed_expert_inbox",
        "distributed_worker_registry",
    }
    assert DistributedRun.__table__.c.payload.type.python_type is dict
    assert DistributedRunAttempt.__table__.c.fencing_token.type.python_type is int
    assert DistributedStep.__table__.c.result.nullable
    assert DistributedLease.__table__.c.run_id.primary_key
    assert DistributedOutbox.__table__.c.event_key.unique
    assert DistributedInbox.__table__.c.message_key.nullable is False
    assert DistributedTraceSpan.__table__.c.attributes.type.python_type is dict
    assert DistributedExpertJob.__table__.c.payload.type.python_type is dict
    assert DistributedExpertLease.__table__.c.job_id.primary_key
    assert DistributedExpertResult.__table__.c.disposition.nullable is False
    assert DistributedExpertOutbox.__table__.c.available_at.nullable is False
    assert DistributedExpertInbox.__table__.c.message_key.nullable is False
    assert DistributedWorkerRegistry.__table__.c.capabilities.type.python_type is dict


async def test_accept_is_idempotent_and_conflicting_payload_is_rejected(repo):
    first = await repo.accept(spec())
    replay = await repo.accept(spec())
    assert first.id == replay.id
    with pytest.raises(RequestConflict):
        await repo.accept(spec(question="不同内容"))


async def test_expired_lease_increments_fencing_and_rejects_old_owner(repo):
    run = await repo.accept(spec())
    first = await repo.claim(run.id, "worker-a", lease_seconds=1)
    await repo.force_lease_expiry(
        run.id, datetime.now(UTC) - timedelta(seconds=1)
    )
    await repo.requeue_expired(now=datetime.now(UTC))
    second = await repo.claim(run.id, "worker-b", lease_seconds=10)
    assert second.fencing_token == first.fencing_token + 1
    with pytest.raises(FencingViolation):
        await repo.complete(run.id, first.fencing_token, {"owner": "a"})
    await repo.transition_committing(run.id, second.fencing_token)
    completed = await repo.complete(
        run.id, second.fencing_token, {"owner": "b"}
    )
    assert completed.status == RunStatus.COMPLETED


async def test_claim_persists_database_derived_parent_deadline(repo):
    run = await repo.accept(spec(request_id="persisted-deadline"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)

    async with repo.session_factory() as session:
        attempt = await session.get(DistributedRunAttempt, claim.attempt_id)

    assert attempt is not None
    assert attempt.deadline_at == claim.deadline_at
    assert claim.deadline_at > attempt.started_at


async def test_m1_attempt_schema_is_backfilled_during_upgrade(repo):
    from core.distributed.runtime import upgrade_m1_schema

    run = await repo.accept(spec(request_id="m1-schema-upgrade"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    async with repo.session_factory() as session, session.begin():
        connection = await session.connection()
        await connection.execute(
            text(
                "ALTER TABLE distributed_run_attempts "
                "DROP COLUMN deadline_at"
            )
        )
        await upgrade_m1_schema(connection, parent_timeout_seconds=75)
        row = (
            await connection.execute(
                text(
                    "SELECT started_at, deadline_at "
                    "FROM distributed_run_attempts WHERE id = :attempt_id"
                ),
                {"attempt_id": claim.attempt_id},
            )
        ).one()

    assert row.deadline_at == row.started_at + timedelta(seconds=75)


async def test_waiting_expert_parent_can_renew_lease(repo):
    run = await repo.accept(spec(request_id="waiting-expert-renew"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    async with repo.session_factory() as session, session.begin():
        stored = await session.get(DistributedRun, run.id, with_for_update=True)
        assert stored is not None
        stored.status = RunStatus.WAITING_EXPERT

    renewed = await repo.renew(
        run.id,
        "worker-a",
        claim.fencing_token,
        lease_seconds=20,
    )

    assert renewed.owner == "worker-a"
    assert renewed.fencing_token == claim.fencing_token


async def test_step_result_is_reused_only_for_same_input_hash(repo):
    run = await repo.accept(spec())
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    await repo.start_step(
        run.id,
        "business-execution",
        "hash-a",
        claim.fencing_token,
    )
    first = await repo.complete_step(
        run.id,
        "business-execution",
        "hash-a",
        claim.fencing_token,
        {"ok": True},
    )
    replay = await repo.complete_step(
        run.id,
        "business-execution",
        "hash-a",
        claim.fencing_token,
        {"ok": True},
    )
    assert replay.id == first.id
    with pytest.raises(RequestConflict):
        await repo.start_step(
            run.id,
            "business-execution",
            "hash-b",
            claim.fencing_token,
        )


async def test_renew_fail_outbox_and_inbox_are_transactional(repo):
    run = await repo.accept(spec(request_id="lifecycle"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    renewed = await repo.renew(
        run.id,
        "worker-a",
        claim.fencing_token,
        lease_seconds=20,
    )
    assert renewed.owner == "worker-a"

    failed = await repo.fail(
        run.id,
        claim.fencing_token,
        "business_store_busy",
        retryable=True,
    )
    assert failed.status == RunStatus.RETRYABLE_FAILED
    assert failed.error_code == "business_store_busy"

    rows = await repo.pending_outbox(10)
    assert [row.topic for row in rows] == ["run.accepted", "run.retry"]
    with pytest.raises(RequestConflict):
        await repo.mark_outbox_published(rows[0].id, "wrong-key")
    await repo.mark_outbox_published(rows[0].id, rows[0].event_key)

    event_key = f"run:{run.id}:retry:{claim.fencing_token}"
    assert await repo.record_inbox("worker-a", event_key)
    assert not await repo.record_inbox("worker-a", event_key)


async def test_cancel_is_idempotent_and_releases_active_lease(repo):
    run = await repo.accept(spec(request_id="cancel"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    cancelled = await repo.cancel(run.id)
    replay = await repo.cancel(run.id)
    lease = await repo.lease(run.id)

    assert cancelled.status == RunStatus.CANCELLED
    assert replay.id == cancelled.id
    assert lease.owner is None
    with pytest.raises(FencingViolation):
        await repo.complete(run.id, claim.fencing_token, {"too": "late"})


async def test_requeue_marks_run_queued_and_trace_lifecycle_is_durable(repo):
    run = await repo.accept(spec(request_id="trace"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await repo.requeue_expired(datetime.now(UTC)) == [run.id]
    queued = await repo.get(run.id)
    assert queued is not None
    assert queued.status == RunStatus.QUEUED

    span = await repo.start_span(
        run.id,
        run.trace_id,
        "span-1",
        None,
        "run_attempt",
        {"worker.id": "worker-a"},
    )
    finished = await repo.finish_span(
        span.span_id,
        "ok",
        {"attempt": claim.attempt_count},
    )
    trace = await repo.trace(run.id)
    assert finished.status == "ok"
    assert finished.attributes["attempt"] == 1
    assert [item.span_id for item in trace] == ["span-1"]


async def test_expired_unreaped_lease_cannot_be_renewed_or_mutated(repo):
    run = await repo.accept(spec(request_id="expired"))
    claim = await repo.claim(run.id, "worker-a", lease_seconds=10)
    await repo.start_step(
        run.id,
        "business-execution",
        "hash-a",
        claim.fencing_token,
    )
    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )

    with pytest.raises(FencingViolation, match="expired"):
        await repo.renew(
            run.id,
            "worker-a",
            claim.fencing_token,
            lease_seconds=10,
        )
    with pytest.raises(FencingViolation, match="expired"):
        await repo.start_step(
            run.id,
            "another-step",
            "hash-b",
            claim.fencing_token,
        )
    with pytest.raises(FencingViolation, match="expired"):
        await repo.complete_step(
            run.id,
            "business-execution",
            "hash-a",
            claim.fencing_token,
            {"ok": True},
        )
    with pytest.raises(FencingViolation, match="expired"):
        await repo.transition_committing(run.id, claim.fencing_token)

    committing = await repo.accept(spec(request_id="expired-complete"))
    committing_claim = await repo.claim(
        committing.id,
        "worker-a",
        lease_seconds=10,
    )
    await repo.transition_committing(
        committing.id,
        committing_claim.fencing_token,
    )
    await repo.force_lease_expiry(
        committing.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(FencingViolation, match="expired"):
        await repo.complete(
            committing.id,
            committing_claim.fencing_token,
            {"ok": True},
        )


async def test_complete_requires_step_intent_and_takeover_updates_token(repo):
    run = await repo.accept(spec(request_id="step-intent"))
    first = await repo.claim(run.id, "worker-a", lease_seconds=10)
    with pytest.raises(RequestConflict, match="not been started"):
        await repo.complete_step(
            run.id,
            "business-execution",
            "hash-a",
            first.fencing_token,
            {"ok": True},
        )
    started = await repo.start_step(
        run.id,
        "business-execution",
        "hash-a",
        first.fencing_token,
    )
    assert started.fencing_token == first.fencing_token

    await repo.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    await repo.requeue_expired(datetime.now(UTC))
    second = await repo.claim(run.id, "worker-b", lease_seconds=10)
    taken_over = await repo.start_step(
        run.id,
        "business-execution",
        "hash-a",
        second.fencing_token,
    )
    assert taken_over.id == started.id
    assert taken_over.fencing_token == second.fencing_token


async def test_concurrent_claim_has_exactly_one_winner(repo):
    run = await repo.accept(spec(request_id="concurrent-claim"))
    outcomes = await asyncio.gather(
        repo.claim(run.id, "worker-a", lease_seconds=10),
        repo.claim(run.id, "worker-b", lease_seconds=10),
        return_exceptions=True,
    )
    assert sum(isinstance(item, RunClaim) for item in outcomes) == 1
    assert sum(isinstance(item, FencingViolation) for item in outcomes) == 1


async def test_reaper_exhausts_run_at_max_attempts(repo):
    limited = DistributedRunRepository(
        repo.session_factory,
        max_attempts=1,
    )
    run = await limited.accept(spec(request_id="exhausted"))
    await limited.claim(run.id, "worker-a", lease_seconds=10)
    await limited.force_lease_expiry(
        run.id,
        datetime.now(UTC) - timedelta(seconds=1),
    )
    assert await limited.requeue_expired(datetime.now(UTC)) == []
    exhausted = await limited.get(run.id)
    assert exhausted is not None
    assert exhausted.status == RunStatus.EXHAUSTED
