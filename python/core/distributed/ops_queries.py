"""Bounded, query-only projections for the distributed operations API."""

from __future__ import annotations

import base64
import binascii
import json
import re
from contextlib import asynccontextmanager
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, get_args
from uuid import UUID

from sqlalchemy import and_, case, func, or_, select, text
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .expert_contracts import ExpertUsage
from .expert_models import (
    DistributedExpertJob,
    DistributedExpertResult,
    DistributedWorkerRegistry,
)
from .models import (
    DistributedLease,
    DistributedRun,
    DistributedRunAttempt,
    DistributedTraceSpan,
)
from .ops_contracts import (
    OpsExpertAttempt,
    OpsExpertBudget,
    OpsExpertJobDetail,
    OpsExpertJobPage,
    OpsExpertJobSummary,
    OpsRunAttempt,
    OpsRunDetail,
    OpsRunPage,
    OpsRunSummary,
    OpsTrace,
    OpsTraceSpan,
    OpsUsage,
    OpsWorker,
    OpsWorkerPage,
    OpsAuditEvent, OpsAuditEventPage, OpsAuditType, OpsCohortCounts,
    OpsGateReceipt, OpsHealthSource, OpsHealthStats, OpsHealthWindow, OpsHealthWindowPage,
    OpsPolicyDeployment, OpsPolicyDeploymentDetail, OpsPolicyDeploymentPage,
    OpsThresholdCode,
)
from .promotion_contracts import (
    DeploymentState, GateType, PolicyThresholds, PromotionCommand, canonical_hash,
)
from .promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord, PolicyGateReceiptRecord, PolicyHealthWindowRecord,
    PolicyObservationRecord, PolicyShadowExecutionRecord,
)

_SAFE_TRACE_ATTRIBUTES = frozenset(
    {
        "duration_ms",
        "error.type",
        "expert.attempt",
        "expert.fencing_token",
        "expert.job_id",
        "expert.role",
        "job_id",
        "messaging.system",
        "process.type",
        "run.attempt",
        "run.fencing_token",
        "run.operation",
        "worker.id",
        "worker_id",
    }
)
_MAX_DETAIL_ATTEMPTS = 100
_MAX_DETAIL_JOBS = 100
_MAX_DETAIL_RESULTS = 100
_MAX_TRACE_SPANS = 500


class InvalidOpsCursor(ValueError):
    pass


def encode_cursor(created_at: datetime, row_id: str) -> str:
    raw = json.dumps(
        {"created_at": created_at.isoformat(), "id": row_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, str]:
    try:
        padded = value + "=" * (-len(value) % 4)
        body = json.loads(base64.urlsafe_b64decode(padded).decode())
        if set(body) != {"created_at", "id"}:
            raise ValueError
        created_at = datetime.fromisoformat(body["created_at"])
        row_id = body["id"]
        if created_at.tzinfo is None or not isinstance(row_id, str) or not row_id:
            raise ValueError
        return created_at.astimezone(UTC), row_id
    except (
        ValueError,
        OverflowError,
        TypeError,
        KeyError,
        UnicodeDecodeError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise InvalidOpsCursor("invalid operations cursor") from exc


def _usage(value: ExpertUsage) -> OpsUsage:
    return OpsUsage(
        model_calls=value.model_calls,
        tool_calls=value.tool_calls,
        input_tokens=value.input_tokens,
        output_tokens=value.output_tokens,
        estimated_cost_usd=value.estimated_cost_usd,
        uncertain=value.uncertain,
    )


def _zero_usage() -> ExpertUsage:
    return ExpertUsage(
        model_calls=0,
        tool_calls=0,
        input_tokens=0,
        output_tokens=0,
        estimated_cost_usd=Decimal("0"),
        provider="unknown",
        model="unknown",
        uncertain=False,
    )


def _sum_usage(values: list[ExpertUsage]) -> ExpertUsage:
    if not values:
        return _zero_usage()

    def optional_sum(name: str):
        parts = [getattr(item, name) for item in values]
        if any(item is None for item in parts):
            return None
        return sum(parts)

    return ExpertUsage(
        model_calls=sum(item.model_calls for item in values),
        tool_calls=sum(item.tool_calls for item in values),
        input_tokens=optional_sum("input_tokens"),
        output_tokens=optional_sum("output_tokens"),
        estimated_cost_usd=optional_sum("estimated_cost_usd"),
        provider=values[-1].provider,
        model=values[-1].model,
        uncertain=any(item.uncertain for item in values),
    )


def _cumulative_job_usage(
    rows: list[DistributedExpertResult],
) -> ExpertUsage:
    by_attempt: dict[int, list[DistributedExpertResult]] = defaultdict(list)
    for row in rows:
        by_attempt[row.expert_fencing_token].append(row)
    billable: list[DistributedExpertResult] = []
    for attempt_rows in by_attempt.values():
        accepted = next(
            (row for row in attempt_rows if row.disposition == "accepted"),
            None,
        )
        real = next(
            (
                row
                for row in attempt_rows
                if row.worker_id != "__expert_reaper__"
            ),
            None,
        )
        billable.append(accepted or real or attempt_rows[0])
    return _sum_usage(
        [ExpertUsage.model_validate(row.usage) for row in billable]
    )


def _source_refs(draft: dict[str, Any] | None) -> list[str]:
    if not isinstance(draft, dict):
        return []
    refs = draft.get("source_refs")
    if not isinstance(refs, list):
        return []
    return [
        value
        for value in refs
        if isinstance(value, str) and 0 < len(value) <= 256
    ][:16]


def _policy_identity(run: DistributedRun) -> dict:
    namespace = run.state_namespace
    return {
        "deployment_id": run.deployment_id,
        "effective_policy_hash": run.effective_policy_hash,
        "policy_cohort": run.policy_cohort,
        "namespace_class": (
            "production" if namespace == "production"
            else "rehearsal" if namespace else None
        ),
    }


def _policy_cursor(value: str, *, hash_id: bool = False) -> tuple[datetime, str]:
    try:
        if not 1 <= len(value) <= 512 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError
        created_at, row_id = decode_cursor(value)
        if hash_id:
            if not re.fullmatch(r"[0-9a-f]{64}", row_id):
                raise ValueError
        elif str(UUID(row_id)) != row_id:
            raise ValueError
        return created_at, row_id
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidOpsCursor("invalid policy cursor") from exc


def _health_stats(raw: dict) -> OpsHealthStats:
    # Only individually validated numbers leave the database, never freeform JSON values.
    safe = {}
    for name in OpsHealthStats.model_fields:
        value = raw.get(name) if isinstance(raw, dict) else None
        if value is None or isinstance(value, bool):
            continue
        if not isinstance(value, (str, int, float, Decimal)):
            continue
        if isinstance(value, str) and not re.fullmatch(
            r"-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value,
        ):
            continue
        try:
            safe[name] = getattr(OpsHealthStats.model_validate({name: value}), name)
        except ValidationError:
            continue
    return OpsHealthStats(**safe)


def _keyset(statement, column, id_column, cursor, *, hash_id=False):
    if cursor is not None:
        timestamp, row_id = _policy_cursor(cursor, hash_id=hash_id)
        statement = statement.where(or_(
            column < timestamp, and_(column == timestamp, id_column < row_id),
        ))
    return statement


def _next_cursor(rows, limit, id_name):
    return encode_cursor(rows[limit - 1].created_at, getattr(rows[limit - 1], id_name)) \
        if len(rows) > limit else None


class OpsQueries:
    """Read-only database access used exclusively by the Ops API."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        worker_stale_seconds: float = 15,
    ) -> None:
        if worker_stale_seconds <= 0:
            raise ValueError("worker_stale_seconds must be positive")
        self.session_factory = session_factory
        self.worker_stale_seconds = worker_stale_seconds

    @asynccontextmanager
    async def _policy_read_session(self):
        async with self.session_factory() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            yield session

    @staticmethod
    def _policy_arguments(limit, environment=None, deployment_id=None):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise InvalidOpsCursor("invalid policy limit")
        if environment is not None and environment not in {"production", "rehearsal"}:
            raise InvalidOpsCursor("invalid policy environment")
        if deployment_id is not None:
            try:
                if str(UUID(deployment_id)) != deployment_id:
                    raise ValueError
            except (ValueError, TypeError, AttributeError) as exc:
                raise InvalidOpsCursor("invalid deployment identity") from exc

    async def list_policy_deployments(
        self, *, limit, cursor=None, environment=None, state=None,
    ) -> OpsPolicyDeploymentPage:
        self._policy_arguments(limit, environment)
        if state is not None and state not in {item.value for item in DeploymentState}:
            raise InvalidOpsCursor("invalid policy state")
        async with self._policy_read_session() as session:
            statement = select(PolicyDeploymentRecord).order_by(
                PolicyDeploymentRecord.created_at.desc(), PolicyDeploymentRecord.deployment_id.desc(),
            ).limit(limit + 1)
            statement = _keyset(statement, PolicyDeploymentRecord.created_at,
                                PolicyDeploymentRecord.deployment_id, cursor)
            if environment is not None:
                statement = statement.where(PolicyDeploymentRecord.environment == environment)
            if state is not None:
                statement = statement.where(PolicyDeploymentRecord.state == state)
            rows = list(await session.scalars(statement))
            heads = {head.environment: head for head in await session.scalars(
                select(PolicyEnvironmentHeadRecord).where(
                    PolicyEnvironmentHeadRecord.environment.in_(["production", "rehearsal"]),
                ),
            )}
            counts = await self._policy_counts(session, [row.deployment_id for row in rows[:limit]])
            return OpsPolicyDeploymentPage(
                items=[self._deployment(row, heads.get(row.environment), counts[row.deployment_id])
                       for row in rows[:limit]],
                next_cursor=_next_cursor(rows, limit, "deployment_id"),
            )

    async def get_policy_deployment(self, deployment_id) -> OpsPolicyDeploymentDetail | None:
        self._policy_arguments(1, deployment_id=deployment_id)
        async with self._policy_read_session() as session:
            row = await session.get(PolicyDeploymentRecord, deployment_id)
            if row is None:
                return None
            head = await session.get(PolicyEnvironmentHeadRecord, row.environment)
            counts = await self._policy_counts(session, [deployment_id])
            summary = self._deployment(row, head, counts[deployment_id])
            # Artifact-wide qualification receipts retain the authority's three-key ordering.
            # This is evidence display, not authorization or gate re-evaluation.
            ranked = select(
                PolicyGateReceiptRecord.receipt_id,
                func.row_number().over(
                    partition_by=PolicyGateReceiptRecord.gate_type,
                    order_by=(PolicyGateReceiptRecord.issued_at.desc(),
                              PolicyGateReceiptRecord.created_at.desc(),
                              PolicyGateReceiptRecord.receipt_id.desc()),
                ).label("rank"),
            ).join(
                PolicyArtifactRecord,
                and_(PolicyArtifactRecord.policy_hash == PolicyGateReceiptRecord.policy_hash,
                     PolicyArtifactRecord.protocol_hash == PolicyGateReceiptRecord.protocol_hash,
                     PolicyArtifactRecord.runtime_hash == PolicyGateReceiptRecord.runtime_hash,
                     PolicyArtifactRecord.source_revision == PolicyGateReceiptRecord.source_revision),
            ).where(
                PolicyGateReceiptRecord.policy_hash == row.candidate_policy_hash,
                PolicyGateReceiptRecord.gate_type.in_(get_args(GateType)),
                PolicyGateReceiptRecord.gate_type.not_in(("shadow_health", "canary_health")),
                PolicyGateReceiptRecord.issued_at <= await self._db_now(session),
            ).subquery()
            receipts = list(await session.scalars(select(PolicyGateReceiptRecord).join(
                ranked, ranked.c.receipt_id == PolicyGateReceiptRecord.receipt_id,
            ).where(ranked.c.rank == 1).order_by(PolicyGateReceiptRecord.gate_type).limit(8)))
            projected = [self._gate_receipt(r) for r in receipts]
            projected.extend(await self._health_receipts(session, row))
            window = await session.scalar(select(PolicyHealthWindowRecord).where(
                PolicyHealthWindowRecord.deployment_id == deployment_id,
            ).order_by(PolicyHealthWindowRecord.created_at.desc(),
                       PolicyHealthWindowRecord.window_id.desc()).limit(1))
            audits = await session.scalars(select(PolicyAuditEventRecord).where(
                self._audit_binding(deployment_id),
            ).order_by(PolicyAuditEventRecord.created_at.desc(),
                       PolicyAuditEventRecord.event_id.desc()).limit(100))
            return OpsPolicyDeploymentDetail(
                **{**summary.model_dump(), "candidate_policy_hash": row.candidate_policy_hash,
                   "stable_policy_hash": row.stable_policy_hash},
                gate_receipts=sorted(projected, key=lambda r: r.gate_type),
                latest_health_window=self._health_window(window, row.environment) if window else None,
                audit_events=[self._audit_event(a) for a in audits],
            )

    @staticmethod
    def _gate_receipt(receipt, source=None):
        return OpsGateReceipt(
            receipt_id=receipt.receipt_id, policy_hash=receipt.policy_hash,
            gate_type=receipt.gate_type, status=receipt.status,
            evidence_hash=receipt.evidence_hash, sample_count=receipt.sample_count,
            cost=receipt.cost, issuer="redacted", issued_at=receipt.issued_at,
            health_source=source,
        )

    async def _health_receipts(self, session, deployment):
        """Project at most two explicitly related sources, without replay or authorization."""
        artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash) \
            if deployment.candidate_policy_hash else None
        if artifact is None:
            return []
        now = await self._db_now(session)
        sources = []
        if deployment.state in {"shadow", "canary", "active"}:
            gate = "shadow_health" if deployment.state == "shadow" else "canary_health"
            sources.append((deployment, gate, "local", now, None))
        canary = deployment
        if deployment.state == "active":
            consumed = await self._consumed_canary(session, deployment, artifact)
            if consumed is None:
                return await self._project_health_sources(session, artifact, sources)
            canary, receipt_id = consumed
            # A local Active receipt, including unknown/invalid evidence, never falls back.
            local = await self._latest_health_receipt(session, artifact, deployment, "canary_health", now)
            if local is None:
                sources.append((canary, "canary_health", "consumed_chain",
                                deployment.created_at, receipt_id))
        if canary.state == "canary":
            shadow = await session.scalar(select(PolicyDeploymentRecord).where(
                PolicyDeploymentRecord.environment == canary.environment,
                PolicyDeploymentRecord.version == canary.version - 1,
                PolicyDeploymentRecord.state == "shadow",
            ).limit(1))
            if shadow is not None and await self._transition_identity(session, shadow, canary):
                sources.append((shadow, "shadow_health", "consumed_chain", canary.created_at, None))
        return await self._project_health_sources(session, artifact, sources)

    @staticmethod
    async def _latest_health_receipt(session, artifact, deployment, gate, cutoff):
        return await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.policy_hash == artifact.policy_hash,
            PolicyGateReceiptRecord.protocol_hash == artifact.protocol_hash,
            PolicyGateReceiptRecord.runtime_hash == artifact.runtime_hash,
            PolicyGateReceiptRecord.source_revision == artifact.source_revision,
            PolicyGateReceiptRecord.gate_type == gate,
            or_(
                PolicyGateReceiptRecord.details["deployment_id"].as_string() == deployment.deployment_id,
                func.coalesce(func.json_typeof(PolicyGateReceiptRecord.details), "null") != "object",
                func.coalesce(func.json_typeof(
                    PolicyGateReceiptRecord.details["deployment_id"],
                ), "null") != "string",
                PolicyGateReceiptRecord.details["deployment_id"].as_string().op("!~")(
                    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
                ),
            ),
            PolicyGateReceiptRecord.issued_at >= deployment.created_at,
            PolicyGateReceiptRecord.issued_at <= cutoff,
            PolicyGateReceiptRecord.created_at <= cutoff,
        ).order_by(PolicyGateReceiptRecord.issued_at.desc(),
                   PolicyGateReceiptRecord.created_at.desc(),
                   PolicyGateReceiptRecord.receipt_id.desc()).limit(1))

    @classmethod
    async def _project_health_sources(cls, session, artifact, sources):
        result = {}
        for deployment, gate, relation, cutoff, exact_id in sources:
            # Unidentifiable latest evidence blocks display rather than reviving an old pass.
            receipt = await cls._latest_health_receipt(session, artifact, deployment, gate, cutoff)
            if receipt is None or (exact_id is not None and receipt.receipt_id != exact_id):
                continue
            details = receipt.details
            if not isinstance(details, dict):
                continue
            window_id = details.get("window_id")
            if not isinstance(window_id, str) or not re.fullmatch(r"[0-9a-f]{64}", window_id):
                continue
            window = await session.get(PolicyHealthWindowRecord, window_id)
            latest = await session.scalar(select(PolicyHealthWindowRecord).where(
                PolicyHealthWindowRecord.deployment_id == deployment.deployment_id,
            ).order_by(PolicyHealthWindowRecord.evaluated_at.desc(),
                       PolicyHealthWindowRecord.window_id.desc()).limit(1))
            consumed_latest = await session.scalar(select(PolicyHealthWindowRecord).where(
                PolicyHealthWindowRecord.deployment_id == deployment.deployment_id,
                PolicyHealthWindowRecord.evaluated_at <= cutoff,
                PolicyHealthWindowRecord.created_at <= cutoff,
            ).order_by(PolicyHealthWindowRecord.evaluated_at.desc(),
                       PolicyHealthWindowRecord.window_id.desc()).limit(1)) \
                if relation == "consumed_chain" else None
            try:
                thresholds = PolicyThresholds.model_validate(deployment.thresholds)
                identity = {
                    "deployment_id": deployment.deployment_id,
                    "deployment_version": deployment.version,
                    "metric_contract_version": 1, "thresholds_hash": thresholds.digest,
                    "observation_keys": window.observation_keys if window else None,
                }
                if (
                    window is None or thresholds.digest != deployment.thresholds_hash
                    or receipt.data_role != artifact.data_role
                    or receipt.issuer != "policy-health"
                    or receipt.model_identity != "server-policy-health-v1"
                    or type(details.get("deployment_version")) is not int
                    or type(details.get("metric_contract_version")) is not int
                    or any(details.get(key) != value for key, value in identity.items())
                    or window.deployment_id != deployment.deployment_id
                    or window.deployment_version != deployment.version
                    or window.thresholds_hash != deployment.thresholds_hash
                    or window.metric_contract_version != 1
                    or canonical_hash(identity) != window.window_id
                    or canonical_hash(details) != receipt.evidence_hash
                    or details.get("gate_cohort") != ("shadow" if gate == "shadow_health" else "candidate")
                    or details.get("candidate_stats") != window.candidate_stats
                    or details.get("stable_stats") != window.stable_stats
                    or not deployment.created_at <= window.evaluated_at <= receipt.issued_at <= cutoff
                    or window.created_at > cutoff
                    or (receipt.status == "passed" and window.decision != "pass")
                    or (relation == "consumed_chain" and (
                        receipt.status != "passed" or window.decision != "pass"
                        or consumed_latest is None or consumed_latest.window_id != window.window_id
                    ))
                    or not await cls._frozen_summary_matches(
                        session, deployment, gate, window, receipt, thresholds,
                    )
                ):
                    continue
                source = OpsHealthSource(
                    relation=relation, deployment_id=deployment.deployment_id,
                    deployment_version=deployment.version, window_id=window.window_id,
                    thresholds_hash=window.thresholds_hash, window_decision=window.decision,
                    evaluated_at=window.evaluated_at,
                    is_latest_window=bool(latest and latest.window_id == window.window_id),
                )
            except (ValidationError, ValueError, TypeError, KeyError):
                continue
            result[gate] = cls._gate_receipt(receipt, source)
        return list(result.values())

    @staticmethod
    async def _frozen_summary_matches(session, deployment, gate, window, receipt, thresholds):
        """只读冻结 key 的有限集合，不重放健康判定，也不从 rounded mean 反推费用。"""
        keys = window.observation_keys
        if not isinstance(keys, dict) or set(keys) != {"candidate", "stable"}:
            return False
        # passed（含消费来源）须满足所属部署冻结下限；本地非通过低样本仍可展示。
        for label, stats, minimum in (
            ("candidate", window.candidate_stats, thresholds.candidate_min_runs),
            ("stable", window.stable_stats, thresholds.stable_min_runs),
        ):
            values = keys[label]
            if (
                not isinstance(values, list) or not 0 <= len(values) <= thresholds.window_max_runs
                or (receipt.status == "passed" and len(values) < minimum)
                or any(not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key)
                       for key in values)
                or not isinstance(stats, dict) or type(stats.get("run_count")) is not int
                or stats["run_count"] != len(values)
            ):
                return False
        flat = keys["candidate"] + keys["stable"]
        if (
            len(set(flat)) != len(flat) or type(receipt.sample_count) is not int
            or receipt.sample_count != len(keys["candidate"])
            or not isinstance(receipt.cost, Decimal) or not receipt.cost.is_finite()
            or receipt.cost < 0
        ):
            return False
        records = list(await session.scalars(select(PolicyObservationRecord).where(
            PolicyObservationRecord.observation_key.in_(flat),
        ).limit(2 * thresholds.window_max_runs)))
        by_key = {row.observation_key: row for row in records}
        if len(by_key) != len(flat):
            return False
        # Active 的合法基线来自已消费 Canary；其余来源必须绑定本部署。
        stable_deployment = deployment
        if deployment.state == "active":
            artifact = await session.get(PolicyArtifactRecord, deployment.candidate_policy_hash)
            consumed = await OpsQueries._consumed_canary(session, deployment, artifact)
            if consumed is None:
                return False
            stable_deployment, consumed_id = consumed
            consumed_receipt = await session.get(PolicyGateReceiptRecord, consumed_id)
            consumed_details = consumed_receipt.details if consumed_receipt else None
            consumed_window = await session.get(
                PolicyHealthWindowRecord, consumed_details.get("window_id"),
            ) if isinstance(consumed_details, dict) else None
            if (
                consumed_window is None or not isinstance(consumed_window.observation_keys, dict)
                or not set(keys["stable"]).issubset(consumed_window.observation_keys.get("stable", []))
            ):
                return False
        total = Decimal(0)
        for label, source, cohort, policy in (
            ("candidate", deployment, "shadow" if gate == "shadow_health" else "candidate",
             deployment.candidate_policy_hash),
            ("stable", stable_deployment, "stable", deployment.stable_policy_hash),
        ):
            rows = [by_key[key] for key in keys[label]]
            if rows != sorted(rows, key=lambda row: (row.observed_at, row.observation_key)):
                return False
            for row in rows:
                if (
                    row.deployment_id != source.deployment_id or row.cohort != cohort
                    or row.policy_hash != policy or row.metric_contract_version != 1
                    or not source.created_at <= row.observed_at <= window.evaluated_at
                    or row.created_at > window.evaluated_at
                    or not isinstance(row.cost, Decimal) or not row.cost.is_finite() or row.cost < 0
                ):
                    return False
                total += row.cost
        return receipt.cost == total

    @staticmethod
    async def _transition_identity(session, predecessor, deployment):
        """从 immutable snapshot 重建完整命令，并验证消费审计的同一身份。"""
        audit = await session.scalar(select(PolicyAuditEventRecord).where(
            PolicyAuditEventRecord.command_id == deployment.command_id,
            PolicyAuditEventRecord.deployment_id == deployment.deployment_id,
            PolicyAuditEventRecord.environment == deployment.environment,
            PolicyAuditEventRecord.event_type == "promotion_transitioned",
        ).limit(1))
        if audit is None or not isinstance(audit.details, dict):
            return None
        details = audit.details
        required = deployment.required_receipts
        health_required = {"shadow_health"} if deployment.state == "canary" else {
            "shadow_health", "canary_health", "promotion_approval",
        }
        try:
            if (
                deployment.environment != "rehearsal"
                or predecessor.environment != deployment.environment
                or type(predecessor.version) is not int or type(deployment.version) is not int
                or predecessor.version != deployment.version - 1
                or (predecessor.state, deployment.state) not in {("shadow", "canary"), ("canary", "active")}
                or any(getattr(predecessor, key) != getattr(deployment, key) for key in (
                    "candidate_policy_hash", "stable_policy_hash", "thresholds_hash", "thresholds",
                    "assignment_salt_id", "previous_stable_deployment_id",
                ))
                or predecessor.created_at > deployment.created_at
                or audit.created_at != deployment.created_at
                or audit.actor != deployment.actor or audit.reason != deployment.reason
                or not isinstance(required, list)
                or any(not isinstance(gate, str) or gate not in get_args(GateType) for gate in required)
                or len(set(required)) != len(required) or not health_required.issubset(required)
                or details.get("required_receipts") != required
                or details.get("from_state") != predecessor.state
                or details.get("to_state") != deployment.state
                or type(details.get("from_version")) is not int
                or type(details.get("to_version")) is not int
                or details["from_version"] != predecessor.version
                or details["to_version"] != deployment.version
            ):
                return None
            command = PromotionCommand(
                command_id=deployment.command_id, environment=deployment.environment,
                expected_version=predecessor.version, current_state=predecessor.state,
                target_state=deployment.state, traffic_basis_points=deployment.traffic_basis_points,
                actor=deployment.actor, reason=deployment.reason,
            )
            command_hash = canonical_hash({"command_type": "transition", "command": command.model_dump(mode="json")})
            return command_hash if details.get("command_hash") == command_hash else None
        except (ValidationError, ValueError, TypeError, KeyError):
            return None

    @staticmethod
    async def _consumed_canary(session, deployment, artifact):
        """Read the exact approval/audit relation, never infer consumption from adjacency."""
        if artifact is None:
            return None
        # 无法识别归属的 latest approval 遮蔽旧 pass；可识别的其它命令不串用。
        approval = await session.scalar(select(PolicyGateReceiptRecord).where(
            PolicyGateReceiptRecord.policy_hash == artifact.policy_hash,
            PolicyGateReceiptRecord.protocol_hash == artifact.protocol_hash,
            PolicyGateReceiptRecord.runtime_hash == artifact.runtime_hash,
            PolicyGateReceiptRecord.source_revision == artifact.source_revision,
            PolicyGateReceiptRecord.gate_type == "promotion_approval",
            or_(
                PolicyGateReceiptRecord.details["command_id"].as_string() == deployment.command_id,
                func.coalesce(func.json_typeof(PolicyGateReceiptRecord.details), "null") != "object",
                func.coalesce(func.json_typeof(
                    PolicyGateReceiptRecord.details["command_id"],
                ), "null") != "string",
                PolicyGateReceiptRecord.details["command_id"].as_string().op("!~")(
                    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$",
                ),
            ),
            PolicyGateReceiptRecord.issued_at >= deployment.created_at,
            PolicyGateReceiptRecord.issued_at <= await OpsQueries._db_now(session),
        ).order_by(PolicyGateReceiptRecord.issued_at.desc(),
                   PolicyGateReceiptRecord.created_at.desc(),
                   PolicyGateReceiptRecord.receipt_id.desc()).limit(1))
        if approval is None or not isinstance(approval.details, dict):
            return None
        details = approval.details
        canary_id = details.get("canary_deployment_id")
        receipt_id = details.get("canary_health_receipt_id")
        if not isinstance(canary_id, str) or not isinstance(receipt_id, str):
            return None
        canary = await session.get(PolicyDeploymentRecord, canary_id)
        receipt = await session.get(PolicyGateReceiptRecord, receipt_id)
        try:
            command_hash = await OpsQueries._transition_identity(session, canary, deployment) \
                if canary is not None else None
            if (
                command_hash is None or canary is None or receipt is None or deployment.environment != "rehearsal"
                or canary.environment != deployment.environment or canary.state != "canary"
                or canary.version != deployment.version - 1
                or canary.candidate_policy_hash != deployment.candidate_policy_hash
                or canary.stable_policy_hash != deployment.stable_policy_hash
                or canary.thresholds_hash != deployment.thresholds_hash
                or canary.thresholds != deployment.thresholds
                or canary.assignment_salt_id != deployment.assignment_salt_id
                or canary.previous_stable_deployment_id != deployment.previous_stable_deployment_id
                or canary.created_at > deployment.created_at
                or approval.issued_at != deployment.created_at
                or approval.status != "passed"
                or approval.protocol_hash != artifact.protocol_hash
                or approval.runtime_hash != artifact.runtime_hash
                or approval.source_revision != artifact.source_revision
                or approval.issuer != deployment.actor
                or approval.model_identity != "authenticated-promotion-command"
                or approval.data_role != artifact.data_role
                or approval.cost != Decimal(0)
                or type(approval.sample_count) is not int
                or approval.sample_count != receipt.sample_count
                or approval.evidence_hash != canonical_hash(details)
                or details.get("command_id") != deployment.command_id
                or details.get("command_hash") != command_hash
                or details.get("canary_deployment_version") != canary.version
                or type(details.get("canary_deployment_version")) is not int
                or details.get("canary_thresholds_hash") != canary.thresholds_hash
                or details.get("canary_health_evidence_hash") != receipt.evidence_hash
                or details.get("actor") != deployment.actor or details.get("reason") != deployment.reason
            ):
                return None
        except (ValueError, TypeError):
            return None
        # 精确引用的 Canary 自身必须通过叶证据校验，否则整条依赖消费链断开。
        # Canary 叶校验不回溯 Active；复用有界只读校验，不重放 evaluator 或授权。
        if not await OpsQueries._project_health_sources(
            session, artifact,
            [(canary, "canary_health", "consumed_chain", deployment.created_at, receipt_id)],
        ):
            return None
        return canary, receipt_id

    async def list_policy_health_windows(
        self, *, limit, cursor=None, environment=None, deployment_id=None, decision=None,
    ) -> OpsHealthWindowPage:
        self._policy_arguments(limit, environment, deployment_id)
        if decision is not None and decision not in {"pass", "hold", "fail"}:
            raise InvalidOpsCursor("invalid health decision")
        async with self._policy_read_session() as session:
            statement = select(PolicyHealthWindowRecord, PolicyDeploymentRecord.environment).join(
                PolicyDeploymentRecord,
                PolicyDeploymentRecord.deployment_id == PolicyHealthWindowRecord.deployment_id,
            ).order_by(PolicyHealthWindowRecord.created_at.desc(),
                       PolicyHealthWindowRecord.window_id.desc()).limit(limit + 1)
            statement = _keyset(statement, PolicyHealthWindowRecord.created_at,
                                PolicyHealthWindowRecord.window_id, cursor, hash_id=True)
            if environment is not None:
                statement = statement.where(PolicyDeploymentRecord.environment == environment)
            if deployment_id is not None:
                statement = statement.where(PolicyHealthWindowRecord.deployment_id == deployment_id)
            if decision is not None:
                statement = statement.where(PolicyHealthWindowRecord.decision == decision)
            rows = list(await session.execute(statement))
            return OpsHealthWindowPage(
                items=[self._health_window(row, env) for row, env in rows[:limit]],
                next_cursor=_next_cursor([row for row, _ in rows], limit, "window_id"),
            )

    async def list_policy_audit(
        self, *, limit, cursor=None, environment=None, deployment_id=None, event_type=None,
    ) -> OpsAuditEventPage:
        self._policy_arguments(limit, environment, deployment_id)
        if event_type is not None and event_type not in set(get_args(OpsAuditType)) - {"redacted"}:
            raise InvalidOpsCursor("invalid audit event type")
        async with self._policy_read_session() as session:
            statement = select(PolicyAuditEventRecord).order_by(
                PolicyAuditEventRecord.created_at.desc(), PolicyAuditEventRecord.event_id.desc(),
            ).limit(limit + 1)
            statement = _keyset(statement, PolicyAuditEventRecord.created_at,
                                PolicyAuditEventRecord.event_id, cursor)
            if environment is not None:
                statement = statement.where(PolicyAuditEventRecord.environment == environment)
            if deployment_id is not None:
                statement = statement.where(self._audit_binding(deployment_id))
            if event_type is not None:
                statement = statement.where(PolicyAuditEventRecord.event_type == event_type)
            rows = list(await session.scalars(statement))
            return OpsAuditEventPage(
                items=[self._audit_event(row) for row in rows[:limit]],
                next_cursor=_next_cursor(rows, limit, "event_id"),
            )

    @staticmethod
    async def _policy_counts(session, deployment_ids):
        counts = {value: {"stable": 0, "candidate": 0, "shadow": 0} for value in deployment_ids}
        if deployment_ids:
            rows = await session.execute(select(
                DistributedRun.deployment_id, DistributedRun.policy_cohort, func.count(),
            ).where(DistributedRun.deployment_id.in_(deployment_ids)).group_by(
                DistributedRun.deployment_id, DistributedRun.policy_cohort,
            ))
            for deployment_id, cohort, count in rows:
                if cohort in counts[deployment_id]:
                    counts[deployment_id][cohort] = int(count)
            shadows = await session.execute(select(
                PolicyShadowExecutionRecord.deployment_id, func.count(),
            ).where(PolicyShadowExecutionRecord.deployment_id.in_(deployment_ids)).group_by(
                PolicyShadowExecutionRecord.deployment_id,
            ))
            for deployment_id, count in shadows:
                counts[deployment_id]["shadow"] += int(count)
        return counts

    @staticmethod
    def _deployment(row, head, counts):
        return OpsPolicyDeployment(
            deployment_id=row.deployment_id, environment=row.environment, version=row.version,
            state=row.state, candidate_policy_hash=row.candidate_policy_hash[:12]
            if row.candidate_policy_hash else None, stable_policy_hash=row.stable_policy_hash[:12],
            is_current=bool(head and head.current_deployment_id == row.deployment_id),
            current_deployment_id=head.current_deployment_id if head else None,
            current_version=head.current_version if head else None,
            traffic_basis_points=row.traffic_basis_points, cohort_counts=OpsCohortCounts(**counts),
            thresholds=row.thresholds, thresholds_hash=row.thresholds_hash,
            required_receipts=[value for value in row.required_receipts if value in get_args(GateType)],
            actor="redacted", reason="redacted", created_at=row.created_at,
        )

    @staticmethod
    def _health_window(row, environment):
        return OpsHealthWindow(
            window_id=row.window_id, deployment_id=row.deployment_id,
            deployment_version=row.deployment_version, environment=environment,
            metric_contract_version=row.metric_contract_version, thresholds_hash=row.thresholds_hash,
            candidate_stats=_health_stats(row.candidate_stats), stable_stats=_health_stats(row.stable_stats),
            decision=row.decision,
            triggered_thresholds=[value if value in get_args(OpsThresholdCode) else "redacted"
                                  for value in row.triggered_thresholds[:16]],
            evaluated_at=row.evaluated_at, created_at=row.created_at,
        )

    @staticmethod
    def _audit_binding(deployment_id):
        return or_(
            PolicyAuditEventRecord.deployment_id == deployment_id,
            and_(
                PolicyAuditEventRecord.event_type == "health_rollback",
                PolicyAuditEventRecord.details["failed_deployment_id"].as_string() == deployment_id,
            ),
        )

    @staticmethod
    def _audit_event(row):
        details = row.details if isinstance(row.details, dict) else {}
        failed_id = details.get("failed_deployment_id") if row.event_type == "health_rollback" else None
        try:
            if not isinstance(failed_id, str) or str(UUID(failed_id)) != failed_id:
                failed_id = None
        except (ValueError, TypeError, AttributeError):
            failed_id = None
        window_id = details.get("window_id") if row.event_type == "health_rollback" else None
        if not isinstance(window_id, str) or not re.fullmatch(r"[0-9a-f]{64}", window_id):
            window_id = None
        states = {item.value for item in DeploymentState}
        transitions = {
            name: details.get(name) if row.event_type == "promotion_transitioned"
            and isinstance(details.get(name), str) and details[name] in states else None
            for name in ("from_state", "to_state")
        }
        return OpsAuditEvent(
            event_id=row.event_id, environment=row.environment, deployment_id=row.deployment_id,
            failed_deployment_id=failed_id, health_window_id=window_id, **transitions,
            event_type=row.event_type if row.event_type in get_args(OpsAuditType) else "redacted",
            actor="redacted", reason="redacted", created_at=row.created_at,
        )

    async def list_runs(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        status: str | None = None,
        operation: str | None = None,
    ) -> OpsRunPage:
        async with self.session_factory() as session:
            now = await self._db_now(session)
            statement = (
                select(DistributedRun, DistributedLease)
                .join(
                    DistributedLease,
                    DistributedLease.run_id == DistributedRun.id,
                )
                .order_by(
                    DistributedRun.created_at.desc(),
                    DistributedRun.id.desc(),
                )
                .limit(limit + 1)
            )
            if cursor:
                created_at, row_id = decode_cursor(cursor)
                statement = statement.where(
                    or_(
                        DistributedRun.created_at < created_at,
                        and_(
                            DistributedRun.created_at == created_at,
                            DistributedRun.id < row_id,
                        ),
                    )
                )
            if status:
                statement = statement.where(DistributedRun.status == status)
            if operation:
                statement = statement.where(
                    DistributedRun.operation == operation
                )
            rows = list(await session.execute(statement))
            visible = rows[:limit]
            run_ids = [run.id for run, _ in visible]
            job_counts = await self._job_counts(session, run_ids)
            run_usage = await self._run_usage(session, run_ids)
            items = [
                self._run_summary(
                    run,
                    lease,
                    now,
                    job_counts.get(run.id, 0),
                    run_usage.get(run.id, _zero_usage()),
                )
                for run, lease in visible
            ]
            next_cursor = None
            if len(rows) > limit and visible:
                next_cursor = encode_cursor(
                    visible[-1][0].created_at,
                    visible[-1][0].id,
                )
            return OpsRunPage(items=items, next_cursor=next_cursor)

    async def get_run(self, run_id: str) -> OpsRunDetail | None:
        async with self.session_factory() as session:
            row = (
                await session.execute(
                    select(DistributedRun, DistributedLease)
                    .join(
                        DistributedLease,
                        DistributedLease.run_id == DistributedRun.id,
                    )
                    .where(DistributedRun.id == run_id)
                )
            ).one_or_none()
            if row is None:
                return None
            run, lease = row
            now = await self._db_now(session)
            attempts = list(
                await session.scalars(
                    select(DistributedRunAttempt)
                    .where(DistributedRunAttempt.run_id == run_id)
                    .order_by(DistributedRunAttempt.number)
                    .limit(_MAX_DETAIL_ATTEMPTS)
                )
            )
            jobs = list(
                await session.scalars(
                    select(DistributedExpertJob)
                    .where(DistributedExpertJob.parent_run_id == run_id)
                    .order_by(
                        DistributedExpertJob.created_at,
                        DistributedExpertJob.id,
                    )
                    .limit(_MAX_DETAIL_JOBS)
                )
            )
            usage_by_run = await self._run_usage(session, [run_id])
            summary = self._run_summary(
                run,
                lease,
                now,
                len(jobs),
                usage_by_run.get(run_id, _zero_usage()),
            )
            return OpsRunDetail(
                **summary.model_dump(),
                attempts=[
                    self._run_attempt(item, now)
                    for item in attempts
                ],
                expert_jobs=[self._job_summary(item) for item in jobs],
            )

    async def get_run_trace(self, run_id: str) -> OpsTrace | None:
        async with self.session_factory() as session:
            run = await session.get(DistributedRun, run_id)
            if run is None:
                return None
            now = await self._db_now(session)
            spans = list(
                await session.scalars(
                    select(DistributedTraceSpan)
                    .where(DistributedTraceSpan.run_id == run_id)
                    .order_by(
                        DistributedTraceSpan.started_at,
                        DistributedTraceSpan.span_id,
                    )
                    .limit(_MAX_TRACE_SPANS)
                )
            )
            return OpsTrace(
                **_policy_identity(run),
                run_id=run.id,
                trace_id=run.trace_id,
                spans=[self._trace_span(span, now) for span in spans],
            )

    async def list_expert_jobs(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        role: str | None = None,
        status: str | None = None,
        parent_run_id: str | None = None,
    ) -> OpsExpertJobPage:
        async with self.session_factory() as session:
            statement = (
                select(DistributedExpertJob)
                .order_by(
                    DistributedExpertJob.created_at.desc(),
                    DistributedExpertJob.id.desc(),
                )
                .limit(limit + 1)
            )
            if cursor:
                created_at, row_id = decode_cursor(cursor)
                statement = statement.where(
                    or_(
                        DistributedExpertJob.created_at < created_at,
                        and_(
                            DistributedExpertJob.created_at == created_at,
                            DistributedExpertJob.id < row_id,
                        ),
                    )
                )
            if role:
                statement = statement.where(
                    func.lower(DistributedExpertJob.role) == role.lower()
                )
            if status:
                statement = statement.where(
                    DistributedExpertJob.status == status
                )
            if parent_run_id:
                statement = statement.where(
                    DistributedExpertJob.parent_run_id == parent_run_id
                )
            rows = list(await session.scalars(statement))
            visible = rows[:limit]
            next_cursor = None
            if len(rows) > limit and visible:
                next_cursor = encode_cursor(
                    visible[-1].created_at,
                    visible[-1].id,
                )
            return OpsExpertJobPage(
                items=[self._job_summary(job) for job in visible],
                next_cursor=next_cursor,
            )

    async def get_expert_job(
        self,
        job_id: str,
    ) -> OpsExpertJobDetail | None:
        async with self.session_factory() as session:
            job = await session.get(DistributedExpertJob, job_id)
            if job is None:
                return None
            latest_results = list(
                await session.scalars(
                    select(DistributedExpertResult)
                    .where(DistributedExpertResult.job_id == job_id)
                    .order_by(
                        DistributedExpertResult.created_at.desc(),
                        DistributedExpertResult.id.desc(),
                    )
                    .limit(_MAX_DETAIL_RESULTS)
                )
            )
            accepted = await session.scalar(
                select(DistributedExpertResult).where(
                    DistributedExpertResult.job_id == job_id,
                    DistributedExpertResult.disposition == "accepted",
                )
            )
            by_id = {row.id: row for row in latest_results}
            if accepted is not None:
                by_id[accepted.id] = accepted
            if len(by_id) > _MAX_DETAIL_RESULTS:
                newest = sorted(
                    (
                        row
                        for row in by_id.values()
                        if accepted is None or row.id != accepted.id
                    ),
                    key=lambda row: (row.created_at, row.id),
                    reverse=True,
                )
                kept = newest[: _MAX_DETAIL_RESULTS - 1]
                if accepted is not None:
                    kept.append(accepted)
                by_id = {row.id: row for row in kept}
            results = sorted(
                by_id.values(),
                key=lambda row: (row.created_at, row.id),
            )
            verified_refs = self._verified_source_refs(job.payload)
            attempts = [
                self._expert_attempt(row, verified_refs)
                for row in results
            ]
            billable = await self._billable_job_results(session, job_id)
            refs = sorted(
                {
                    ref
                    for attempt in attempts
                    for ref in attempt.source_refs
                }
            )
            budget = job.payload.get("budget", {})
            return OpsExpertJobDetail(
                job_id=job.id,
                parent_run_id=job.parent_run_id,
                logical_key=job.logical_key,
                role=job.role.lower(),
                status=job.status,
                input_hash=job.input_hash,
                policy_hash=job.policy_hash,
                budget=OpsExpertBudget.model_validate(budget),
                usage=_usage(_cumulative_job_usage(billable)),
                source_refs=refs,
                attempts=attempts,
                error_code=job.error_code,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
            )

    async def list_workers(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        worker_id: str | None = None,
        process_type: str | None = None,
        status: str | None = None,
    ) -> OpsWorkerPage:
        async with self.session_factory() as session:
            now = await self._db_now(session)
            statement = (
                select(DistributedWorkerRegistry)
                .order_by(
                    DistributedWorkerRegistry.started_at.desc(),
                    DistributedWorkerRegistry.id.desc(),
                )
                .limit(limit + 1)
            )
            if cursor:
                created_at, row_id = decode_cursor(cursor)
                statement = statement.where(
                    or_(
                        DistributedWorkerRegistry.started_at < created_at,
                        and_(
                            DistributedWorkerRegistry.started_at == created_at,
                            DistributedWorkerRegistry.id < row_id,
                        ),
                    )
                )
            if worker_id:
                statement = statement.where(
                    DistributedWorkerRegistry.worker_id == worker_id
                )
            if process_type:
                statement = statement.where(
                    DistributedWorkerRegistry.process_type == process_type
                )
            if status:
                statement = statement.where(
                    DistributedWorkerRegistry.status == status
                )
            rows = list(await session.scalars(statement))
            visible = rows[:limit]
            next_cursor = None
            if len(rows) > limit and visible:
                next_cursor = encode_cursor(
                    visible[-1].started_at,
                    visible[-1].id,
                )
            return OpsWorkerPage(
                items=[self._worker(row, now) for row in visible],
                next_cursor=next_cursor,
            )

    async def _job_counts(
        self,
        session: AsyncSession,
        run_ids: list[str],
    ) -> dict[str, int]:
        if not run_ids:
            return {}
        rows = await session.execute(
            select(
                DistributedExpertJob.parent_run_id,
                func.count(DistributedExpertJob.id),
            )
            .where(DistributedExpertJob.parent_run_id.in_(run_ids))
            .group_by(DistributedExpertJob.parent_run_id)
        )
        return {run_id: int(count) for run_id, count in rows}

    async def _run_usage(
        self,
        session: AsyncSession,
        run_ids: list[str],
    ) -> dict[str, ExpertUsage]:
        if not run_ids:
            return {}
        priority = case(
            (DistributedExpertResult.disposition == "accepted", 0),
            (
                DistributedExpertResult.worker_id
                != "__expert_reaper__",
                1,
            ),
            else_=2,
        )
        ranked = (
            select(
                DistributedExpertJob.parent_run_id.label("run_id"),
                DistributedExpertJob.id.label("job_id"),
                DistributedExpertResult.usage.label("usage"),
                func.row_number()
                .over(
                    partition_by=(
                        DistributedExpertJob.id,
                        DistributedExpertResult.expert_fencing_token,
                    ),
                    order_by=(
                        priority,
                        DistributedExpertResult.created_at,
                        DistributedExpertResult.id,
                    ),
                )
                .label("usage_rank"),
            )
            .join(
                DistributedExpertResult,
                DistributedExpertResult.job_id
                == DistributedExpertJob.id,
            )
            .where(DistributedExpertJob.parent_run_id.in_(run_ids))
            .subquery()
        )
        rows = await session.execute(
            select(ranked.c.run_id, ranked.c.usage).where(
                ranked.c.usage_rank == 1
            )
        )
        per_run: dict[str, list[ExpertUsage]] = defaultdict(list)
        for run_id, usage in rows:
            per_run[run_id].append(ExpertUsage.model_validate(usage))
        return {
            run_id: _sum_usage(usages)
            for run_id, usages in per_run.items()
        }

    @staticmethod
    async def _billable_job_results(
        session: AsyncSession,
        job_id: str,
    ) -> list[DistributedExpertResult]:
        priority = case(
            (DistributedExpertResult.disposition == "accepted", 0),
            (
                DistributedExpertResult.worker_id
                != "__expert_reaper__",
                1,
            ),
            else_=2,
        )
        rows = await session.scalars(
            select(DistributedExpertResult)
            .where(DistributedExpertResult.job_id == job_id)
            .order_by(
                DistributedExpertResult.expert_fencing_token,
                priority,
                DistributedExpertResult.created_at,
                DistributedExpertResult.id,
            )
            .distinct(DistributedExpertResult.expert_fencing_token)
        )
        return list(rows)

    @staticmethod
    async def _db_now(session: AsyncSession) -> datetime:
        return await session.scalar(select(func.now()))

    @staticmethod
    def _run_summary(
        run: DistributedRun,
        lease: DistributedLease,
        now: datetime,
        job_count: int,
        usage: ExpertUsage,
    ) -> OpsRunSummary:
        end = (
            run.updated_at
            if run.status
            in {
                "completed",
                "terminal_failed",
                "cancelled",
                "exhausted",
            }
            else now
        )
        return OpsRunSummary(
            **_policy_identity(run),
            run_id=run.id,
            operation=run.operation,
            status=run.status,
            trace_id=run.trace_id,
            attempt_count=run.attempt_count,
            owner=lease.owner,
            fencing_token=lease.fencing_token,
            lease_expires_at=lease.expires_at,
            lease_fresh=bool(
                lease.owner
                and lease.expires_at
                and lease.expires_at > now
            ),
            expert_job_count=job_count,
            usage=_usage(usage),
            latency_ms=max(
                0,
                int((end - run.created_at).total_seconds() * 1000),
            ),
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    @staticmethod
    def _run_attempt(
        attempt: DistributedRunAttempt,
        now: datetime,
    ) -> OpsRunAttempt:
        end = attempt.finished_at or now
        return OpsRunAttempt(
            number=attempt.number,
            worker_id=attempt.worker_id,
            fencing_token=attempt.fencing_token,
            status=attempt.status,
            reason=attempt.reason,
            started_at=attempt.started_at,
            deadline_at=attempt.deadline_at,
            finished_at=attempt.finished_at,
            duration_ms=max(
                0,
                int((end - attempt.started_at).total_seconds() * 1000),
            ),
        )

    @staticmethod
    def _job_summary(
        job: DistributedExpertJob,
    ) -> OpsExpertJobSummary:
        return OpsExpertJobSummary(
            job_id=job.id,
            parent_run_id=job.parent_run_id,
            role=job.role.lower(),
            status=job.status,
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            error_code=job.error_code,
            deadline_at=job.deadline_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
        )

    @staticmethod
    def _trace_span(
        span: DistributedTraceSpan,
        now: datetime,
    ) -> OpsTraceSpan:
        attributes = {
            key: value
            for key, value in span.attributes.items()
            if key in _SAFE_TRACE_ATTRIBUTES
            and isinstance(value, (str, int, float, bool))
        }
        end = span.ended_at or now
        return OpsTraceSpan(
            span_id=span.span_id,
            trace_id=span.trace_id,
            parent_span_id=span.parent_span_id,
            name=span.name,
            status=span.status,
            attributes=attributes,
            started_at=span.started_at,
            ended_at=span.ended_at,
            duration_ms=max(
                0,
                int((end - span.started_at).total_seconds() * 1000),
            ),
        )

    @staticmethod
    def _verified_source_refs(payload: dict[str, Any]) -> set[str]:
        snapshot = payload.get("snapshot")
        if not isinstance(snapshot, dict):
            return set()
        refs = snapshot.get("verified_source_refs")
        if not isinstance(refs, list):
            return set()
        return {
            value
            for value in refs
            if isinstance(value, str) and 0 < len(value) <= 256
        }

    @staticmethod
    def _expert_attempt(
        result: DistributedExpertResult,
        verified_refs: set[str],
    ) -> OpsExpertAttempt:
        return OpsExpertAttempt(
            worker_id=result.worker_id,
            fencing_token=result.expert_fencing_token,
            disposition=result.disposition,
            rejection_code=result.rejection_code,
            usage=_usage(ExpertUsage.model_validate(result.usage)),
            source_refs=[
                ref
                for ref in _source_refs(result.draft)
                if ref in verified_refs
            ],
            created_at=result.created_at,
        )

    def _worker(
        self,
        row: DistributedWorkerRegistry,
        now: datetime,
    ) -> OpsWorker:
        age = max(
            0.0,
            (now - row.last_heartbeat_at).total_seconds(),
        )
        fresh = row.status == "running" and age <= self.worker_stale_seconds
        health = (
            "stopped"
            if row.status == "stopped"
            else "healthy"
            if fresh
            else "stale"
        )
        capabilities = [
            value
            for value in row.capabilities
            if isinstance(value, str) and 0 < len(value) <= 128
        ][:32]
        return OpsWorker(
            worker_id=row.worker_id,
            instance_id=row.instance_id,
            process_type=row.process_type,
            status=row.status,
            health=health,
            fresh=fresh,
            capabilities=capabilities,
            current_run_id=row.current_run_id,
            current_job_id=row.current_job_id,
            heartbeat_age_seconds=round(age, 3),
            started_at=row.started_at,
            last_heartbeat_at=row.last_heartbeat_at,
            stopped_at=row.stopped_at,
        )
