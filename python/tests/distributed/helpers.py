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


def authority(worker_id="parent-worker"):
    return RunExecutionAuthority(
        distributed_run_id=UUID(
            "12345678-1234-5678-1234-567812345678"
        ),
        run_fencing_token=1,
        trace_id="a" * 32,
        attempt_number=1,
        worker_id=worker_id,
        parent_deadline_at=datetime.now(UTC) + timedelta(minutes=2),
    )
