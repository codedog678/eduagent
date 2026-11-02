"""Deterministic executor boundary for the real Task 10 process integration."""
from __future__ import annotations

import asyncio
import os

from core.distributed import cli
from tests.distributed.helpers import business_result


class FixtureExecutor:
    def __init__(self, *args, **kwargs):
        self.usage_recorder = None

    async def execute(self, request, authority, binding):
        pause_prefix = os.getenv("PROMOTION_FIXTURE_PAUSE_REQUEST_PREFIX")
        if pause_prefix and request.request_id.startswith(pause_prefix):
            await asyncio.sleep(30)
        usage = {
            "input_tokens": 10,
            "output_tokens": 5,
            "model_calls": 0,
            "tool_calls": 0,
            "cost": "0.01",
            "structured_decision_count": 1,
            "unknown_decision_count": 0,
        }
        if (
            self.usage_recorder is not None
            and authority.execution_mode != "shadow"
        ):
            await self.usage_recorder(
                str(authority.distributed_run_id),
                authority.run_fencing_token,
                usage,
            )
        return business_result(binding, usage=usage)


cli.LearningTaskExecutor = FixtureExecutor


if __name__ == "__main__":
    cli.main()
