from core.distributed.contracts import DistributedRunRequest, RunOperation
from core.distributed.expert_contracts import RunExecutionAuthority
from datetime import UTC, datetime, timedelta
from uuid import UUID


def spec(request_id="r1", question="复习"):
    return DistributedRunRequest(
        learner_id="student",
        request_id=request_id,
        operation=RunOperation.LEARNING_TASK,
        payload={
            "learner_id": "student",
            "request_id": request_id,
            "knowledge_id": "grammar_tenses",
            "question": question,
        },
    )


def authority(worker_id="parent-worker", binding=None):
    from core.distributed.runtime import BUILTIN_POLICY_HASH, PRODUCTION_DEPLOYMENT_ID

    return RunExecutionAuthority(
        distributed_run_id=UUID(
            "12345678-1234-5678-1234-567812345678"
        ),
        run_fencing_token=1,
        trace_id="a" * 32,
        attempt_number=1,
        worker_id=worker_id,
        parent_deadline_at=datetime.now(UTC) + timedelta(minutes=2),
        deployment_id=binding.deployment_id if binding else PRODUCTION_DEPLOYMENT_ID,
        effective_policy_hash=binding.effective_policy_hash if binding else BUILTIN_POLICY_HASH,
        policy_cohort=binding.policy_cohort if binding else "stable",
        state_namespace=binding.state_namespace if binding else "production",
        rehearsal_id=binding.rehearsal_id if binding else None,
    )


async def bootstrap_production(repo):
    from core.distributed.promotion_models import (
        PolicyArtifactRecord, PolicyDeploymentRecord, PolicyEnvironmentHeadRecord,
    )
    from core.distributed.runtime import (
        BUILTIN_POLICY_HASH, BUILTIN_POLICY_COMPONENTS, BUILTIN_FIXED_COMPONENTS_HASH,
        BUILTIN_RUNTIME_HASH, BUILTIN_PROTOCOL_HASH, BUILTIN_PROPOSER_HASH,
        DEFAULT_POLICY_THRESHOLDS, DEFAULT_POLICY_THRESHOLDS_HASH, PRODUCTION_DEPLOYMENT_ID,
    )
    now = datetime.now(UTC)
    async with repo.session_factory() as session, session.begin():
        session.add(PolicyArtifactRecord(policy_hash=BUILTIN_POLICY_HASH,
            parent_policy_hash=None, components=BUILTIN_POLICY_COMPONENTS,
            fixed_components_hash=BUILTIN_FIXED_COMPONENTS_HASH, runtime_hash=BUILTIN_RUNTIME_HASH,
            source_revision="builtin", protocol_hash=BUILTIN_PROTOCOL_HASH,
            proposer_hash=BUILTIN_PROPOSER_HASH, data_role="builtin", evidence_bindings={}, created_at=now))
        await session.flush()
        session.add(PolicyDeploymentRecord(deployment_id=PRODUCTION_DEPLOYMENT_ID,
            environment="production", version=1, state="registered", candidate_policy_hash=None,
            stable_policy_hash=BUILTIN_POLICY_HASH, previous_stable_deployment_id=None,
            traffic_basis_points=0, assignment_salt_id="builtin", thresholds=DEFAULT_POLICY_THRESHOLDS,
            thresholds_hash=DEFAULT_POLICY_THRESHOLDS_HASH, required_receipts=[],
            command_id="bootstrap-production", reason="test bootstrap", actor="system", created_at=now))
        await session.flush()
        session.add(PolicyEnvironmentHeadRecord(environment="production",
            current_deployment_id=PRODUCTION_DEPLOYMENT_ID, current_version=1, updated_at=now))
