from __future__ import annotations

import argparse
import asyncio
import os
import socket

from config.settings import settings
from core.distributed.executor import LearningTaskExecutor
from core.distributed.runtime import build_runtime


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="EduAgent distributed run-plane process",
    )
    subcommands = value.add_subparsers(dest="command", required=True)
    subcommands.add_parser("dispatcher")
    subcommands.add_parser("worker")
    subcommands.add_parser("reaper")
    return value


async def run_forever(command: str) -> None:
    runtime = build_runtime()
    await runtime.start()
    try:
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
            worker_id = (
                settings.distributed_worker_id
                or f"{socket.gethostname()}:{os.getpid()}"
            )
            worker = runtime.worker(
                worker_id,
                LearningTaskExecutor(settings.harness_store_path),
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
