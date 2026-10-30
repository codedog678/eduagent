from __future__ import annotations

import argparse
import asyncio
import os
import socket
from uuid import uuid4

from config.settings import settings
from core.distributed.executor import LearningTaskExecutor
from core.distributed.expert_contracts import ExpertRole
from core.distributed.runtime import build_runtime


def expert_roles(value: str) -> set[ExpertRole]:
    known = {role.value.lower(): role for role in ExpertRole}
    parsed: set[ExpertRole] = set()
    for item in value.split(","):
        normalized = item.strip().lower()
        if not normalized:
            continue
        role = known.get(normalized)
        if role is None:
            raise ValueError(f"unknown expert role: {item.strip()}")
        parsed.add(role)
    if not parsed:
        raise ValueError("expert worker requires at least one role")
    return parsed


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="EduAgent distributed run-plane process",
    )
    subcommands = value.add_subparsers(dest="command", required=True)
    subcommands.add_parser("dispatcher")
    subcommands.add_parser("worker")
    subcommands.add_parser("reaper")
    subcommands.add_parser("expert-dispatcher")
    subcommands.add_parser("expert-worker")
    subcommands.add_parser("expert-reaper")
    return value


async def run_forever(command: str) -> None:
    if command.startswith("expert-") and not settings.distributed_experts_enabled:
        raise RuntimeError(
            "expert processes require DISTRIBUTED_EXPERTS_ENABLED=true"
        )
    roles = (
        expert_roles(settings.expert_worker_roles)
        if command == "expert-worker"
        else set()
    )
    runtime = build_runtime()
    worker_id = (
        settings.distributed_worker_id
        if command == "worker" and settings.distributed_worker_id
        else settings.expert_worker_id
        if command == "expert-worker" and settings.expert_worker_id
        else f"{socket.gethostname()}:{os.getpid()}:{command}"
    )
    process_type = (
        "run-worker"
        if command == "worker"
        else command
    )
    capabilities = (
        ["learning_task"]
        if command == "worker"
        else sorted(role.value.lower() for role in roles)
    )
    heartbeat_seconds = (
        settings.expert_heartbeat_seconds
        if command.startswith("expert-")
        else settings.distributed_heartbeat_seconds
    )
    try:
        await runtime.start()
        async with runtime.worker_registry.process(
            worker_id=worker_id,
            instance_id=uuid4().hex,
            process_type=process_type,
            heartbeat_seconds=heartbeat_seconds,
            capabilities=capabilities,
        ) as registry_process:
            if command == "dispatcher":
                dispatcher = runtime.dispatcher()
                while True:
                    await dispatcher.dispatch_once()
                    await asyncio.sleep(0.25)
            elif command == "reaper":
                reaper = runtime.reaper()
                while True:
                    await reaper.reap_once()
                    await asyncio.sleep(
                        settings.distributed_heartbeat_seconds,
                    )
            elif command == "worker":
                worker = runtime.worker(
                    worker_id,
                    LearningTaskExecutor(
                        settings.harness_store_path,
                        expert_gateway=runtime.expert_gateway(),
                    ),
                    registry_process=registry_process,
                )
                while True:
                    await worker.run_once()
            elif command == "expert-dispatcher":
                dispatcher = runtime.expert_dispatcher()
                while True:
                    await dispatcher.dispatch_once()
                    await asyncio.sleep(0.25)
            elif command == "expert-reaper":
                reaper = runtime.expert_reaper()
                while True:
                    await reaper.reap_once()
                    await asyncio.sleep(settings.expert_heartbeat_seconds)
            elif command == "expert-worker":
                from core.distributed.expert_engine import ExpertEngine
                from core.llm_service import get_llm_service

                worker = runtime.expert_worker(
                    worker_id,
                    ExpertEngine(get_llm_service()),
                    roles=roles,
                    registry_process=registry_process,
                )
                while True:
                    await worker.run_once()
            else:
                raise ValueError(f"unsupported command: {command}")
    finally:
        await runtime.close()


def main() -> None:
    args = parser().parse_args()
    asyncio.run(run_forever(args.command))


if __name__ == "__main__":
    main()
