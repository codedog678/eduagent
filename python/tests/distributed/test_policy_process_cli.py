import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from api.ops_routes import _PROCESS_TYPES, _validate_filter
from core.distributed import cli


async def test_policy_health_uses_dedicated_poll_interval(monkeypatch):
    observed = []

    class Health:
        async def poll_once(self):
            observed.append("poll")

    @asynccontextmanager
    async def process(**_kwargs):
        yield SimpleNamespace()

    async def no_op():
        return None

    runtime = SimpleNamespace(
        start=no_op,
        close=no_op,
        worker_registry=SimpleNamespace(process=process),
        policy_health=Health,
    )

    async def stop_after_observation(seconds):
        observed.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(cli, "build_runtime", lambda: runtime)
    monkeypatch.setattr(cli.asyncio, "sleep", stop_after_observation)
    monkeypatch.setattr(cli.settings, "promotion_enabled", True)
    monkeypatch.setattr(cli.settings, "promotion_health_poll_seconds", 0.125)
    monkeypatch.setattr(cli.settings, "distributed_heartbeat_seconds", 9)

    with pytest.raises(asyncio.CancelledError):
        await cli.run_forever("policy-health")

    assert observed == ["poll", 0.125]


@pytest.mark.parametrize(
    "process_type",
    [
        "policy-health",
        "rehearsal-worker",
        "shadow-reaper",
        "shadow-worker",
    ],
)
def test_ops_accepts_policy_promotion_process_filters(process_type):
    assert _validate_filter(
        "process_type",
        process_type,
        _PROCESS_TYPES,
    ) == process_type
