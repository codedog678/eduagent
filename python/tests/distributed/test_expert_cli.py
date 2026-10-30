from types import SimpleNamespace

import pytest

from core.distributed.cli import expert_roles, parser
from core.distributed.expert_contracts import ExpertRole
from core.distributed.runtime import DistributedRuntime


@pytest.mark.parametrize(
    "command",
    [
        "dispatcher",
        "worker",
        "reaper",
        "expert-dispatcher",
        "expert-worker",
        "expert-reaper",
    ],
)
def test_parser_exposes_run_and_expert_processes(command):
    assert parser().parse_args([command]).command == command


def test_expert_roles_are_normalized_and_validated():
    assert expert_roles("Assessment, tutor,Assessment") == {
        ExpertRole.ASSESSMENT,
        ExpertRole.TUTOR,
    }
    with pytest.raises(ValueError, match="unknown expert role"):
        expert_roles("Assessment,writer")
    with pytest.raises(ValueError, match="at least one"):
        expert_roles(" , ")


def test_runtime_builds_separate_expert_transport_and_processes():
    run_broker = SimpleNamespace(redis=object())
    settings = SimpleNamespace(
        expert_stream="test:experts",
        expert_consumer_group="test-expert-workers",
        distributed_outbox_batch_size=7,
        expert_lease_seconds=9,
        expert_heartbeat_seconds=2,
        expert_poll_block_ms=321,
        expert_demo_pause_before_result_seconds=4,
        ops_worker_stale_seconds=15,
        expert_queued_limit_per_role=50,
        expert_running_limit_per_role=2,
        expert_queued_payload_bytes_limit=1024,
        expert_max_payload_bytes=1024,
        expert_max_job_seconds=120,
        expert_retry_base_seconds=1,
        expert_retry_max_seconds=30,
    )
    runtime = DistributedRuntime(
        engine=object(),
        session_factory=object(),
        repository=object(),
        broker=run_broker,
        settings_obj=settings,
    )

    assert runtime.expert_broker.redis is run_broker.redis
    assert runtime.expert_broker.stream == "test:experts"
    assert runtime.expert_broker.group == "test-expert-workers"
    assert runtime.expert_dispatcher().batch_size == 7
    assert runtime.expert_reaper().repository is runtime.expert_repository

    engine = object()
    worker = runtime.expert_worker(
        "expert-a",
        engine,
        roles={ExpertRole.ASSESSMENT},
    )
    assert worker.engine is engine
    assert worker.roles == {ExpertRole.ASSESSMENT}
    assert worker.poll_block_ms == 321
    assert worker.pause_before_result_seconds == 4
