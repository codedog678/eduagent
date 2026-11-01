"""Candidate execution in a disposable store with a durable, redacted terminal."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

from .contracts import DistributedRunRequest, RunStatus
from .expert_contracts import RunExecutionAuthority
from .executor import ShadowExecutionError
from .models import DistributedRun
from .policy_assignment import ArtifactUnavailable, PolicyAssigner
from .promotion_contracts import PolicyExecutionBinding
from .promotion_models import PolicyDeploymentRecord
from .result_identity import ProtocolIdentityError, validate_business_result
from .shadow_repository import ShadowFencingViolation, redacted_summary


class ShadowWorker:
    def __init__(
        self, worker_id, repository, executor, store_router, *,
        policy_assigner=None, lease_seconds=15, heartbeat_seconds=3,
        attempt_timeout_seconds=300,
    ):
        if not 0 < heartbeat_seconds < lease_seconds or attempt_timeout_seconds <= 0:
            raise ValueError("invalid shadow worker timing")
        self.worker_id, self.repository, self.executor = worker_id, repository, executor
        self.store_router = store_router
        self.policy_assigner = policy_assigner or PolicyAssigner()
        self.lease_seconds, self.heartbeat_seconds = lease_seconds, heartbeat_seconds
        self.attempt_timeout_seconds = attempt_timeout_seconds

    async def _frozen_input(self, job):
        async with self.repository.session_factory() as session:
            parent = await session.get(DistributedRun, job.parent_run_id)
            deployment = await session.get(PolicyDeploymentRecord, job.deployment_id)
            binding = PolicyExecutionBinding.model_validate(job.policy_binding)
            if (parent is None or parent.status != RunStatus.COMPLETED
                or deployment is None or deployment.state != "shadow"
                or deployment.version != job.deployment_version
                or deployment.candidate_policy_hash != job.policy_hash
                or parent.deployment_id != job.deployment_id
                or binding.effective_policy_hash != job.policy_hash
                or str(binding.deployment_id) != job.deployment_id
                or binding.state_namespace != f"shadow-{job.deployment_id}-{parent.id}"
                or binding.environment != deployment.environment
                or binding.rehearsal_id != parent.rehearsal_id
                or binding.policy_cohort != "shadow"
                or job.payload_reference != {"run_id": parent.id, "input_hash": job.input_hash}):
                raise ValueError("invalid frozen shadow identity")
            request = DistributedRunRequest(
                learner_id=parent.learner_id, request_id=parent.request_id,
                operation=parent.operation, payload=parent.payload,
            )
            if request.input_hash != job.input_hash or parent.input_hash != job.input_hash:
                raise ValueError("invalid frozen shadow payload")
            components = self.policy_assigner.validate_artifact(
                await self.policy_assigner.load_artifact(session, job.policy_hash),
            )
            if components != binding.components:
                raise ArtifactUnavailable()
            return request, binding

    async def _heartbeat(self, job):
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            await self.repository.renew_shadow(
                job.shadow_id, self.worker_id, job.fencing_token, self.lease_seconds,
            )

    async def _execute(self, job, lock_holder):
        started = monotonic()
        code, usage = None, {}
        try:
            request, binding = await self._frozen_input(job)
            while lock_holder[0] is None:
                lock_holder[0] = self.store_router.try_lock(binding)
                if lock_holder[0] is None:
                    await asyncio.sleep(min(self.heartbeat_seconds, 0.1))
            # Recheck PostgreSQL after acquiring the local filesystem lock.
            await self.repository.renew_shadow(
                job.shadow_id, self.worker_id, job.fencing_token, self.lease_seconds,
            )
            authority = RunExecutionAuthority(
                distributed_run_id=job.shadow_id, run_fencing_token=job.fencing_token,
                trace_id=uuid4().hex, attempt_number=job.attempt_count,
                worker_id=self.worker_id, parent_deadline_at=job.deadline_at,
                deployment_id=binding.deployment_id,
                effective_policy_hash=binding.effective_policy_hash,
                policy_cohort=binding.policy_cohort, state_namespace=binding.state_namespace,
                rehearsal_id=binding.rehearsal_id, execution_mode="shadow",
            )
            result = await self.executor.execute(request, authority, binding)
            validate_business_result(result, binding)
            usage = result.get("usage", {})
            usage = usage if isinstance(usage, dict) else {}
        except ShadowFencingViolation:
            raise
        except ArtifactUnavailable:
            code = "artifact_unavailable"
        except ProtocolIdentityError:
            code = "protocol_identity_invalid"
        except ShadowExecutionError as exc:
            code, usage = "execution_failed", exc.usage
        except ValueError:
            code = "payload_invalid"
        except Exception:
            code = "execution_failed"
        summary = redacted_summary(
            {**usage, "latency_seconds": monotonic() - started},
            status="failed" if code else "completed",
        )
        return code, summary

    async def run_once(self):
        job = await self.repository.claim_shadow(
            self.worker_id, self.lease_seconds,
            attempt_timeout_seconds=self.attempt_timeout_seconds,
        )
        if job is None:
            return False
        lock_holder = [None]
        remaining = max(0, (job.deadline_at - datetime.now(UTC)).total_seconds())
        execution = asyncio.create_task(asyncio.wait_for(
            self._execute(job, lock_holder), timeout=remaining,
        ))
        heartbeat = asyncio.create_task(self._heartbeat(job))
        try:
            done, _ = await asyncio.wait(
                [execution, heartbeat], return_when=asyncio.FIRST_COMPLETED,
            )
            if heartbeat in done:
                await heartbeat
            try:
                code, summary = await execution
            except TimeoutError:
                # Deadline is already expired: only the fenced reaper may retry it.
                return True
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat
            # Commit failures propagate; never turn them into a successful cleanup.
            if code:
                await self.repository.fail_shadow(
                    job.shadow_id, self.worker_id, job.fencing_token, code, summary,
                )
            else:
                await self.repository.complete_shadow(
                    job.shadow_id, self.worker_id, job.fencing_token, summary,
                )
            if lock_holder[0] is not None:
                lock_holder[0].cleanup()
        except ShadowFencingViolation:
            pass
        finally:
            # Cancellation must finish before releasing the lock, even on lease loss.
            for task in (execution, heartbeat):
                task.cancel()
            await asyncio.gather(execution, heartbeat, return_exceptions=True)
            if lock_holder[0] is not None:
                lock_holder[0].close()
        return True


class ShadowReaper:
    def __init__(self, repository, store_router):
        self.repository, self.store_router = repository, store_router

    async def reap_once(self):
        ids = await self.repository.reap_shadow()
        after_id = None
        while jobs := await self.repository.terminal_shadows(after_id=after_id):
            for job in jobs:
                binding = PolicyExecutionBinding.model_validate(job.policy_binding)
                lock = self.store_router.try_lock(binding)
                if lock is None:
                    continue
                try:
                    # Terminal rows are append-only; a live old worker keeps the lock.
                    lock.cleanup()
                finally:
                    lock.close()
            after_id = jobs[-1].shadow_id
        return ids
