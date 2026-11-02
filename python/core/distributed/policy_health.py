"""Frozen PostgreSQL observations and deterministic, fail-closed health windows."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from uuid import uuid4

from sqlalchemy import func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert

from .contracts import RunStatus, canonical_hash
from .health_evidence_identity import observation_key, same_distribution
from .models import DistributedRun, DistributedRunAttempt, DistributedStep
from .promotion_contracts import PolicyObservation, PolicyThresholds
from .promotion_models import (
    PolicyArtifactRecord, PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord, PolicyGateReceiptRecord, PolicyHealthWindowRecord,
    PolicyObservationRecord, PolicyShadowExecutionRecord,
)


class RehearsalInjectedCommitFailure(RuntimeError):
    pass


class ConfirmedPermissionViolation(PermissionError):
    """Only server-side authorization invariant checks may raise this diagnostic."""


def server_diagnostic_code(exc):
    current = exc
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, (ConfirmedPermissionViolation, RehearsalInjectedCommitFailure)):
            return type(current).__name__
        current = current.__cause__
    return type(exc).__name__


def nearest_rank(values, percentile):
    if not values or not Decimal(0) < percentile <= Decimal(1):
        raise ValueError("invalid percentile sample")
    rank = max(1, int((len(values) * percentile).to_integral_value(rounding=ROUND_CEILING)))
    return sorted(values)[rank - 1]


def _stats(rows):
    count = len(rows)
    decisions_known = all(
        row.structured_decision_count is not None and row.unknown_decision_count is not None
        for row in rows
    )
    decisions = sum(row.structured_decision_count or 0 for row in rows)
    unknown = sum(row.unknown_decision_count or 0 for row in rows)
    mean_cost = (
        sum((row.cost for row in rows), Decimal(0)) / count
        if count and all(row.cost is not None for row in rows) else None
    )
    return {
        "run_count": count,
        "commit_failure_rate": str(Decimal(sum(row.commit_outcome == "failed" for row in rows)) / count)
        if count else None,
        "terminal_failure_rate": str(Decimal(sum(row.terminal_status != "completed" for row in rows)) / count)
        if count else None,
        "p95_latency": str(nearest_rank([row.latency_seconds for row in rows], Decimal(".95")))
        if count else None,
        "mean_cost": str(mean_cost) if mean_cost is not None else None,
        "structured_decision_count": decisions if decisions_known else None,
        "unknown_decision_count": unknown if decisions_known else None,
        "unknown_rate": str(Decimal(unknown) / decisions) if decisions_known and decisions else None,
        "fault_injected_count": sum(row.fault_injected for row in rows),
        "injected_commit_failure_count": sum(
            row.fault_injected and row.server_error_code == "RehearsalInjectedCommitFailure" for row in rows),
        "natural_failure_count": sum(
            row.terminal_status != "completed" and not (
                row.fault_injected and row.server_error_code == "RehearsalInjectedCommitFailure"
            ) for row in rows),
    }


@dataclass(frozen=True)
class WindowEvaluation:
    decision: str
    reasons: list[str]
    candidate_stats: dict
    stable_stats: dict


def evaluate_window(candidate, stable, thresholds):
    candidate_stats, stable_stats = _stats(candidate), _stats(stable)
    unavailable, failed = [], []
    if any(row.permission_outcome == "confirmed_violation"
           and row.terminal_status == "confirmed_permission_violation"
           and row.server_error_code == "ConfirmedPermissionViolation" for row in candidate):
        failed.append("confirmed_permission_violation")
    enough = (len(candidate) >= thresholds.candidate_min_runs
              and len(stable) >= thresholds.stable_min_runs)
    if not enough:
        unavailable.append("baseline_shortage")
    if candidate_stats["mean_cost"] is None or stable_stats["mean_cost"] is None:
        unavailable.append("cost_unavailable")
    if candidate_stats["unknown_rate"] is None:
        unavailable.append("structured_decisions_unavailable")
    if enough:
        for metric in ("commit_failure_rate", "terminal_failure_rate", "unknown_rate"):
            value = candidate_stats[metric]
            if value is not None and Decimal(value) >= getattr(thresholds, metric):
                failed.append(metric)
        for metric, field in (("latency_increase_rate", "p95_latency"),
                              ("mean_cost_increase_rate", "mean_cost")):
            c, s = candidate_stats[field], stable_stats[field]
            if c is not None and s is not None:
                relative = (Decimal(c) - Decimal(s)) / max(Decimal(s), thresholds.relative_epsilon)
                candidate_stats[metric] = str(relative)
                if relative >= getattr(thresholds, metric):
                    failed.append(metric)
    return WindowEvaluation(
        "fail" if failed else "hold" if unavailable else "pass",
        failed + unavailable, candidate_stats, stable_stats,
    )


def _observation(row):
    return PolicyObservation.model_validate({
        name: getattr(row, name) for name in PolicyObservation.model_fields
    })


def evaluate_matched_window(candidate, stable, thresholds, *, matched):
    result = evaluate_window(candidate, stable, thresholds)
    if matched:
        return result
    unqualified = evaluate_window(candidate, [], thresholds)
    return WindowEvaluation(
        unqualified.decision, unqualified.reasons + ["matched_window_incomplete"],
        result.candidate_stats, result.stable_stats,
    )


def proportional_baseline(candidate, pool, thresholds):
    """Largest bounded exact-ratio baseline; newest rows win within each bucket."""
    if not candidate or any(row.rehearsal_id is None for row in candidate):
        return [], False
    needed = Counter((row.rehearsal_id, row.operation) for row in candidate)
    buckets = {bucket: [] for bucket in needed}
    for row in sorted(pool, key=lambda row: (row.observed_at, row.observation_key), reverse=True):
        bucket = (row.rehearsal_id, row.operation)
        if bucket in buckets:
            buckets[bucket].append(row)
    for total in range(min(len(pool), thresholds.window_max_runs), thresholds.stable_min_runs - 1, -1):
        if any(count * total % len(candidate) for count in needed.values()):
            continue
        sizes = {bucket: count * total // len(candidate) for bucket, count in needed.items()}
        if all(len(buckets[bucket]) >= size for bucket, size in sizes.items()):
            selected = [row for bucket, size in sizes.items() for row in buckets[bucket][:size]]
            return sorted(selected, key=lambda row: (row.observed_at, row.observation_key)), True
    # Preserve bounded diagnostic samples, but do not evaluate normal failures on them.
    return sorted(pool, key=lambda row: (row.observed_at, row.observation_key)), False


class PolicyObservationRecorder:
    def __init__(self, session_factory, *, metrics=None):
        self.session_factory, self.metrics = session_factory, metrics

    async def _insert(self, session, observation):
        deployment = await session.get(PolicyDeploymentRecord, str(observation.deployment_id))
        if deployment is None:
            raise ValueError("observation deployment is missing")
        # 与晋级/回滚共用 head 锁；此路径不持有终态写锁，也不反向取得 health advisory。
        head = await session.scalar(select(PolicyEnvironmentHeadRecord).where(
            PolicyEnvironmentHeadRecord.environment == deployment.environment,
        ).with_for_update())
        if head is None:
            raise ValueError("observation environment head is missing")
        values = observation.model_dump(mode="python")
        for field in ("run_id", "deployment_id"):
            values[field] = str(values[field])
        values["created_at"] = await session.scalar(select(func.clock_timestamp()))
        inserted = await session.scalar(insert(PolicyObservationRecord).values(**values)
            .on_conflict_do_nothing().returning(PolicyObservationRecord.observation_key))
        return observation, inserted is not None

    def _observe(self, observation, inserted):
        if inserted and observation is not None and self.metrics is not None:
            self.metrics.policy_observation_latency.labels(cohort=observation.cohort).observe(
                float(observation.latency_seconds))
            if observation.cost is not None:
                self.metrics.policy_observation_cost.labels(cohort=observation.cohort).observe(
                    float(observation.cost))
        return observation

    async def record_run(self, run_id):
        return self._observe(*(await self._record_run(run_id)))

    async def _record_run(self, run_id):
        async with self.session_factory() as session, session.begin():
            run = await session.get(DistributedRun, str(run_id))
            if run is None or run.status not in {
                RunStatus.COMPLETED, RunStatus.TERMINAL_FAILED, RunStatus.EXHAUSTED,
            } or run.policy_binding is None:
                return None, False
            key = observation_key(run.id, run.deployment_id, run.policy_cohort, 1)
            existing = await session.get(PolicyObservationRecord, key)
            if existing is not None:
                return _observation(existing), False
            attempts = list((await session.scalars(select(DistributedRunAttempt).where(
                DistributedRunAttempt.run_id == run.id).order_by(DistributedRunAttempt.number))).all())
            summaries = [attempt.usage_summary for attempt in attempts]
            # 没有服务端完整账本时，不把仅专家费用伪装成全链路费用。
            from .shadow_usage import combine_usage
            usage = combine_usage(summaries)
            injected = any(attempt.fault_injected for attempt in attempts)
            permission = (run.error_code == "ConfirmedPermissionViolation" and bool(attempts)
                          and attempts[-1].reason == run.error_code
                          and attempts[-1].status == run.status)
            step = await session.scalar(select(DistributedStep).where(
                DistributedStep.run_id == run.id, DistributedStep.step_id == "business-execution"))
            commit_failed = run.status != RunStatus.COMPLETED and (
                run.error_code == "RehearsalInjectedCommitFailure"
                or (step is not None and step.status == RunStatus.COMPLETED)
            )
            status = ("completed" if run.status == RunStatus.COMPLETED else
                      "confirmed_permission_violation" if permission else
                      "commit_failed" if commit_failed else
                      "exhausted" if run.status == RunStatus.EXHAUSTED else "terminal_failed")
            observation = PolicyObservation(
                observation_key=key, run_id=run.id, deployment_id=run.deployment_id,
                policy_hash=run.effective_policy_hash, cohort=run.policy_cohort,
                state_namespace=run.state_namespace, terminal_status=status,
                latency_seconds=max(Decimal(0), Decimal(str((run.updated_at - run.created_at).total_seconds()))),
                input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"], cost=usage["cost"],
                commit_outcome="succeeded" if status == "completed" else "failed" if commit_failed else "not_attempted",
                permission_outcome="confirmed_violation" if permission else "not_applicable",
                structured_result=usage["structured_result"],
                structured_decision_count=usage["structured_decision_count"],
                unknown_decision_count=usage["unknown_decision_count"],
                injected=injected, fault_injected=injected, observed_at=run.updated_at,
                source_trace_id=run.trace_id[:32], rehearsal_id=run.rehearsal_id,
                operation=run.operation, server_error_code=run.error_code,
            )
            return await self._insert(session, observation)

    async def record_shadow(self, shadow_id):
        return self._observe(*(await self._record_shadow(shadow_id)))

    async def _record_shadow(self, shadow_id):
        async with self.session_factory() as session, session.begin():
            shadow = await session.get(PolicyShadowExecutionRecord, str(shadow_id))
            if shadow is None or shadow.status not in {"completed", "failed", "exhausted"}:
                return None, False
            run = await session.get(DistributedRun, shadow.parent_run_id)
            if run is None or shadow.policy_binding is None:
                return None, False
            key = observation_key(run.id, shadow.deployment_id, "shadow", 1)
            existing = await session.get(PolicyObservationRecord, key)
            if existing is not None:
                return _observation(existing), False
            usage = shadow.result or {}
            permission = shadow.error_code == "ConfirmedPermissionViolation"
            observation = PolicyObservation(
                observation_key=key, run_id=run.id, deployment_id=shadow.deployment_id,
                policy_hash=shadow.policy_hash, cohort="shadow",
                state_namespace=shadow.policy_binding["state_namespace"],
                terminal_status="confirmed_permission_violation" if permission else
                "completed" if shadow.status == "completed" else
                "exhausted" if shadow.status == "exhausted" else "terminal_failed",
                latency_seconds=max(Decimal(0), Decimal(str(
                    ((shadow.finished_at or shadow.updated_at)
                     - (shadow.started_at or shadow.created_at)).total_seconds()))),
                input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
                cost=usage.get("cost"), commit_outcome="not_attempted",
                permission_outcome="confirmed_violation" if permission else "isolated",
                structured_result=usage.get("structured_result", "unavailable"),
                structured_decision_count=usage.get("structured_decision_count"),
                unknown_decision_count=usage.get("unknown_decision_count"),
                observed_at=shadow.finished_at or shadow.updated_at, source_trace_id=run.trace_id[:32],
                rehearsal_id=run.rehearsal_id, operation=run.operation, server_error_code=shadow.error_code,
            )
            return await self._insert(session, observation)

    async def recover(self, *, limit=200):
        # 轮询补齐 worker 提交后崩溃遗漏的终态通知，不依赖 Redis 投递。
        async with self.session_factory() as session:
            runs = (await session.scalars(select(DistributedRun.id).where(
                DistributedRun.status.in_(["completed", "terminal_failed", "exhausted"]),
                func.json_typeof(DistributedRun.policy_binding) == "object",
                ~select(PolicyObservationRecord.observation_key).where(
                    PolicyObservationRecord.run_id == DistributedRun.id,
                    PolicyObservationRecord.cohort == DistributedRun.policy_cohort,
                    PolicyObservationRecord.deployment_id == DistributedRun.deployment_id,
                    PolicyObservationRecord.metric_contract_version == 1,
                ).exists(),
            ).order_by(DistributedRun.updated_at, DistributedRun.id).limit(limit))).all()
            shadows = (await session.scalars(select(PolicyShadowExecutionRecord.shadow_id).where(
                PolicyShadowExecutionRecord.status.in_(["completed", "failed", "exhausted"]),
                func.json_typeof(PolicyShadowExecutionRecord.policy_binding) == "object",
                select(DistributedRun.id).where(
                    DistributedRun.id == PolicyShadowExecutionRecord.parent_run_id,
                ).exists(),
                ~select(PolicyObservationRecord.observation_key).where(
                    PolicyObservationRecord.run_id == PolicyShadowExecutionRecord.parent_run_id,
                    PolicyObservationRecord.deployment_id == PolicyShadowExecutionRecord.deployment_id,
                    PolicyObservationRecord.cohort == "shadow",
                    PolicyObservationRecord.metric_contract_version == 1,
                ).exists(),
            ).order_by(PolicyShadowExecutionRecord.updated_at,
                       PolicyShadowExecutionRecord.shadow_id).limit(limit))).all()
        for run_id in runs:
            await self.record_run(run_id)
        for shadow_id in shadows:
            await self.record_shadow(shadow_id)
        return len(runs) + len(shadows)


class PolicyHealthEvaluator:
    def __init__(self, repository, *, metrics=None):
        self.repository, self.metrics = repository, metrics
        self.session_factory = repository.session_factory

    async def evaluate(self, deployment_id):
        window, events = await self._evaluate(deployment_id)
        if self.metrics is not None:
            for name, labels in events:
                getattr(self.metrics, name).labels(**labels).inc()
        return window

    async def _evaluate(self, deployment_id):
        events = []
        async with self.session_factory() as session, session.begin():
            deployment = await session.get(PolicyDeploymentRecord, str(deployment_id))
            if deployment is None or deployment.state not in {"shadow", "canary", "active"}:
                return None, events
            await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                                  {"key": "policy-health:" + deployment.environment})
            head = await session.scalar(select(PolicyEnvironmentHeadRecord).where(
                PolicyEnvironmentHeadRecord.environment == deployment.environment
            ).with_for_update().execution_options(populate_existing=True))
            cohort = "shadow" if deployment.state == "shadow" else "candidate"
            thresholds = PolicyThresholds.model_validate(deployment.thresholds)
            if thresholds.digest != deployment.thresholds_hash:
                raise ValueError("frozen threshold identity mismatch")
            query = select(PolicyObservationRecord).where(
                PolicyObservationRecord.deployment_id == deployment.deployment_id,
                PolicyObservationRecord.metric_contract_version == 1,
            )
            ordering = (PolicyObservationRecord.observed_at.desc(), PolicyObservationRecord.observation_key.desc())
            candidate_query = query.where(
                PolicyObservationRecord.cohort == cohort,
                PolicyObservationRecord.policy_hash == deployment.candidate_policy_hash,
            )
            if deployment.state == "active":
                candidate_query = candidate_query.where(
                    PolicyObservationRecord.observed_at >= deployment.created_at,
                )
            candidate = [_observation(row) for row in (await session.scalars(
                candidate_query.order_by(*ordering).limit(thresholds.window_max_runs))).all()][::-1]
            # 硬违规不受滚动窗口淘汰；有界查询冻结最早的权威违规键。
            predecessors = await self.repository.health_predecessors(session, deployment)
            hard_sources = [(deployment.deployment_id, cohort)] + [
                (source.deployment_id, "shadow" if source.state == "shadow" else "candidate")
                for source in predecessors
            ]
            hard_failure = await session.scalar(select(PolicyObservationRecord).where(
                tuple_(PolicyObservationRecord.deployment_id,
                       PolicyObservationRecord.cohort).in_(hard_sources),
                PolicyObservationRecord.metric_contract_version == 1,
                PolicyObservationRecord.policy_hash == deployment.candidate_policy_hash,
                PolicyObservationRecord.permission_outcome == "confirmed_violation",
                PolicyObservationRecord.terminal_status == "confirmed_permission_violation",
                PolicyObservationRecord.server_error_code == "ConfirmedPermissionViolation",
            ).order_by(PolicyObservationRecord.observed_at, PolicyObservationRecord.observation_key).limit(1))
            baseline_query = query.where(
                PolicyObservationRecord.cohort == "stable",
                PolicyObservationRecord.policy_hash == deployment.stable_policy_hash,
            )
            if cohort == "shadow":
                parents = {row.run_id for row in candidate}
                stable = [_observation(row) for row in (await session.scalars(baseline_query.where(
                    PolicyObservationRecord.run_id.in_([str(parent) for parent in parents]),
                ).order_by(*ordering).limit(thresholds.window_max_runs))).all()][::-1]
                matched = len(stable) == len(candidate)
            else:
                needed = {(row.rehearsal_id, row.operation) for row in candidate
                          if row.rehearsal_id is not None}
                if deployment.state == "active":
                    pool = await self.repository.active_health_baseline(session, deployment)
                    pool = [_observation(row) for row in pool]
                else:
                    pool = [_observation(row) for row in (await session.scalars(
                        baseline_query.where(
                            tuple_(PolicyObservationRecord.rehearsal_id,
                                   PolicyObservationRecord.operation).in_(list(needed)),
                            PolicyObservationRecord.state_namespace != "production",
                        ).order_by(*ordering).limit(thresholds.window_max_runs)
                    )).all()][::-1]
                stable, matched = proportional_baseline(candidate, pool, thresholds)
            result = evaluate_matched_window(candidate, stable, thresholds, matched=matched)
            if hard_failure is not None and "confirmed_permission_violation" not in result.reasons:
                result = WindowEvaluation(
                    "fail", ["confirmed_permission_violation", *result.reasons],
                    result.candidate_stats, result.stable_stats,
                )
            keys = {"candidate": [row.observation_key for row in candidate],
                    "stable": [row.observation_key for row in stable]}
            if hard_failure is not None and hard_failure.observation_key not in keys["candidate"]:
                keys["hard_failures"] = [hard_failure.observation_key]
            identity = {"deployment_id": deployment.deployment_id, "deployment_version": deployment.version,
                        "metric_contract_version": 1, "thresholds_hash": thresholds.digest,
                        "observation_keys": keys}
            window_id = canonical_hash(identity)
            existing = await session.get(PolicyHealthWindowRecord, window_id)
            if existing is not None:
                return existing, events
            now = await session.scalar(select(func.clock_timestamp()))
            flat = keys["candidate"] + keys["stable"]
            window = PolicyHealthWindowRecord(
                window_id=window_id, deployment_id=deployment.deployment_id,
                deployment_version=deployment.version, thresholds_hash=thresholds.digest,
                metric_contract_version=1, observation_keys=keys,
                observation_start_key=flat[0] if flat else canonical_hash([]),
                observation_end_key=flat[-1] if flat else canonical_hash([]),
                candidate_stats=result.candidate_stats, stable_stats=result.stable_stats,
                decision=result.decision, triggered_thresholds=result.reasons,
                evaluated_at=now, created_at=now,
            )
            session.add(window)
            await session.flush()
            current = (head is not None and head.current_deployment_id == deployment.deployment_id
                       and head.current_version == deployment.version)
            if result.decision == "fail" and current and deployment.state in {"canary", "active"}:
                rolled_back = await self.repository.rollback_if_current(session, deployment, window)
                if rolled_back:
                    events.append(("policy_rollbacks", {"environment": deployment.environment,
                                                       "trigger": "health_threshold"}))
            elif result.decision == "pass":
                artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
                gate = "shadow_health" if cohort == "shadow" else "canary_health"
                details = {**identity, "window_id": window_id,
                           "gate_cohort": cohort,
                           "candidate_stats": result.candidate_stats, "stable_stats": result.stable_stats}
                if artifact.evidence_bindings.get("evidence_role") == "test_fixture":
                    details.update(evidence_role="test_fixture", release_eligible=False)
                session.add(PolicyGateReceiptRecord(
                    receipt_id=str(uuid4()), policy_hash=artifact.policy_hash, gate_type=gate,
                    status="passed", evidence_hash=canonical_hash(details),
                    protocol_hash=artifact.protocol_hash, runtime_hash=artifact.runtime_hash,
                    source_revision=artifact.source_revision, model_identity="server-policy-health-v1",
                    data_role=artifact.data_role, sample_count=len(candidate),
                    cost=sum((row.cost for row in candidate + stable), Decimal(0)),
                    details=details, issued_at=now, issuer="policy-health", created_at=now,
                ))
                events.append(("policy_gate_decisions", {"gate": gate, "status": "passed"}))
            events.append(("policy_health_decisions", {
                "environment": deployment.environment, "decision": result.decision,
            }))
            return window, events


class PolicyHealthProcess:
    def __init__(self, repository, *, metrics=None, enabled=False):
        self.repository, self.enabled = repository, enabled
        self.recorder = PolicyObservationRecorder(repository.session_factory, metrics=metrics)
        self.evaluator = PolicyHealthEvaluator(repository, metrics=metrics)

    async def poll_once(self):
        if not self.enabled:
            return []
        await self.recorder.recover()
        async with self.repository.session_factory() as session:
            ids = (await session.scalars(select(PolicyEnvironmentHeadRecord.current_deployment_id))).all()
        return [await self.evaluator.evaluate(deployment_id) for deployment_id in ids]
