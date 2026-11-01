"""PostgreSQL-authoritative shadow queue. No primary commit API is exposed."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from .contracts import RunStatus
from .models import DistributedRun
from .promotion_contracts import PolicyExecutionBinding
from .promotion_models import (
    PolicyArtifactRecord, PolicyDeploymentRecord, PolicyShadowExecutionRecord as Shadow,
)


class ShadowFencingViolation(RuntimeError):
    pass


def redacted_summary(value: dict | None = None, *, status="failed") -> dict:
    """Allowlist at the durable boundary, including callers other than the worker."""
    value = value if isinstance(value, dict) else {}
    summary = {
        "terminal_status": status,
        "commit_outcome": "not_attempted",
        "permission_outcome": "isolated",
        "structured_result": "unavailable",
    }
    for name in ("latency_seconds", "cost"):
        raw = value.get(name)
        if raw is None:
            summary[name] = None
            continue
        try:
            number = Decimal(str(raw))
            summary[name] = str(number) if number.is_finite() and 0 <= number <= Decimal("1e12") else None
        except (ValueError, InvalidOperation):
            summary[name] = None
    for name in ("input_tokens", "output_tokens", "model_calls", "tool_calls"):
        raw = value.get(name)
        summary[name] = raw if type(raw) is int and 0 <= raw <= 10**12 else None
    return summary


async def enqueue_shadow_in_transaction(session, parent_run_id):
    parent = await session.get(DistributedRun, parent_run_id)
    if parent is None or parent.status != RunStatus.COMPLETED:
        return None
    deployment = await session.get(PolicyDeploymentRecord, parent.deployment_id)
    if deployment is None or deployment.state != "shadow" or not deployment.candidate_policy_hash:
        return None
    existing = await session.scalar(select(Shadow).where(
        Shadow.parent_run_id == parent.id, Shadow.deployment_id == deployment.deployment_id,
    ))
    if existing is not None:
        return existing
    artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
    binding = {**PolicyExecutionBinding.model_validate(parent.policy_binding).model_dump(mode="json"),
        "effective_policy_hash": deployment.candidate_policy_hash,
        "components": artifact.components,
        "policy_cohort": "shadow",
        "assignment_reason": "frozen_deployment_shadow",
        "state_namespace": f"shadow-{deployment.deployment_id}-{parent.id}",
        "rehearsal_fault_profile": "none",
    }
    binding = PolicyExecutionBinding.model_validate(binding)
    now = await session.scalar(select(func.clock_timestamp()))
    await session.execute(insert(Shadow).values(
        shadow_id=str(uuid4()), parent_run_id=parent.id,
        deployment_id=deployment.deployment_id, policy_hash=deployment.candidate_policy_hash,
        deployment_version=deployment.version, input_hash=parent.input_hash,
        payload_reference={"run_id": parent.id, "input_hash": parent.input_hash},
        policy_binding=binding.model_dump(mode="json"), status="queued",
        attempt_count=0, max_attempts=3, fencing_token=0, created_at=now, updated_at=now,
    ).on_conflict_do_nothing(index_elements=["parent_run_id", "deployment_id"]))
    return await session.scalar(select(Shadow).where(
        Shadow.parent_run_id == parent.id, Shadow.deployment_id == deployment.deployment_id,
    ))


class ShadowRepositoryMixin:
    async def enqueue_shadow(self, parent_run_id):
        async with self.session_factory() as session, session.begin():
            return await enqueue_shadow_in_transaction(session, parent_run_id)

    async def get_shadow(self, shadow_id):
        async with self.session_factory() as session:
            return await session.get(Shadow, shadow_id)

    async def claim_shadow(self, worker_id, lease_seconds, *, attempt_timeout_seconds=300):
        if not worker_id or len(worker_id) > 128 or lease_seconds <= 0 or attempt_timeout_seconds <= 0:
            raise ValueError("invalid shadow claim")
        async with self.session_factory() as session, session.begin():
            now = await session.scalar(select(func.clock_timestamp()))
            job = await session.scalar(select(Shadow).where(
                Shadow.attempt_count < Shadow.max_attempts,
                Shadow.input_hash.is_not(None), Shadow.policy_binding.is_not(None),
                Shadow.payload_reference.is_not(None), Shadow.deployment_version.is_not(None),
                or_(Shadow.status == "queued", and_(
                    Shadow.status == "running", or_(
                        Shadow.lease_expires_at <= now, Shadow.deadline_at <= now,
                    ),
                )),
            ).order_by(Shadow.created_at, Shadow.shadow_id).with_for_update(skip_locked=True))
            if job is None:
                return None
            now = await session.scalar(select(func.clock_timestamp()))
            job.status, job.owner = "running", worker_id
            job.fencing_token += 1
            job.attempt_count += 1
            job.started_at = now
            job.deadline_at = now + timedelta(seconds=attempt_timeout_seconds)
            job.lease_expires_at = min(now + timedelta(seconds=lease_seconds), job.deadline_at)
            job.updated_at = now
            return job

    async def _locked_live_shadow(self, session, shadow_id, worker_id, token):
        # WHERE 中的时间可能在等锁前求值，必须锁定后重新取数据库时间。
        job = await session.scalar(select(Shadow).where(
            Shadow.shadow_id == shadow_id,
        ).with_for_update())
        now = await session.scalar(select(func.clock_timestamp()))
        if (job is None or job.status != "running"
            or job.owner != worker_id or job.fencing_token != token
            or job.lease_expires_at is None or job.lease_expires_at <= now
            or job.deadline_at is None or job.deadline_at <= now):
            raise ShadowFencingViolation("shadow lease lost")
        return job, now

    async def renew_shadow(self, shadow_id, worker_id, token, lease_seconds):
        if lease_seconds <= 0:
            raise ValueError("invalid shadow lease")
        async with self.session_factory() as session, session.begin():
            job, now = await self._locked_live_shadow(session, shadow_id, worker_id, token)
            job.lease_expires_at = min(now + timedelta(seconds=lease_seconds), job.deadline_at)
            job.updated_at = now

    async def _finish_shadow(self, shadow_id, worker_id, token, status, summary, code):
        async with self.session_factory() as session, session.begin():
            job, now = await self._locked_live_shadow(session, shadow_id, worker_id, token)
            job.status, job.result = status, redacted_summary(summary, status=status)
            job.error_code, job.owner, job.lease_expires_at = code, None, None
            job.finished_at = job.updated_at = now

    async def complete_shadow(self, shadow_id, worker_id, token, summary):
        await self._finish_shadow(shadow_id, worker_id, token, "completed", summary, None)

    async def fail_shadow(self, shadow_id, worker_id, token, error_code, summary=None):
        code = error_code if error_code in {
            "execution_failed", "protocol_identity_invalid", "artifact_unavailable",
            "deadline_expired", "cancelled", "payload_invalid",
        } else "execution_failed"
        await self._finish_shadow(shadow_id, worker_id, token, "failed", summary, code)

    async def reap_shadow(self, now=None):
        # Caller clocks never extend a lease or authorize early reclamation.
        async with self.session_factory() as session, session.begin():
            db_now = await session.scalar(select(func.clock_timestamp()))
            jobs = (await session.scalars(select(Shadow).where(
                or_(Shadow.status == "queued", and_(
                    Shadow.status.in_(["leased", "running"]), or_(
                        Shadow.lease_expires_at <= db_now, Shadow.lease_expires_at.is_(None),
                        Shadow.deadline_at <= db_now, Shadow.deadline_at.is_(None),
                    ),
                )),
            ).with_for_update(skip_locked=True))).all()
            db_now = await session.scalar(select(func.clock_timestamp()))
            ids = []
            for job in jobs:
                if job.input_hash is None or job.policy_binding is None or job.payload_reference is None or job.deployment_version is None:
                    code = "legacy_identity_missing"
                elif job.attempt_count >= job.max_attempts:
                    code = "attempts_exhausted"
                elif job.status == "queued":
                    continue
                else:
                    code = None
                job.fencing_token += 1
                job.owner, job.lease_expires_at = None, None
                job.updated_at = db_now
                if code:
                    job.status, job.error_code = "exhausted", code
                    job.result = redacted_summary(status="exhausted")
                    job.finished_at = db_now
                else:
                    job.status = "queued"
                ids.append(job.shadow_id)
            return ids

    async def terminal_shadows(self, limit=100, *, after_id=None):
        async with self.session_factory() as session:
            query = select(Shadow).where(
                Shadow.status.in_(["completed", "failed", "exhausted"]),
                Shadow.result.is_not(None), Shadow.finished_at.is_not(None),
                Shadow.policy_binding.is_not(None),
            )
            if after_id is not None:
                query = query.where(Shadow.shadow_id > after_id)
            return (await session.scalars(query.order_by(Shadow.shadow_id).limit(limit))).all()
