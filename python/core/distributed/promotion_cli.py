"""Isolated command line interface for trusted policy promotion."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from config.settings import settings

from .promotion_contracts import PromotionCommand
from .runtime import build_promotion_command_runtime


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        prog="promotion-cli",
        description="Audited policy promotion command plane",
    )
    commands = value.add_subparsers(dest="command", required=True)

    register = commands.add_parser("register-campaign")
    register.add_argument("--campaign", required=True)
    register.add_argument("--actor", required=True)
    register.add_argument("--command-id", required=True)

    shadow = commands.add_parser("start-shadow")
    _transition_arguments(shadow, reason_default="start shadow qualification")

    canary = commands.add_parser("start-canary")
    _transition_arguments(canary, reason_default="start bounded canary")
    canary.add_argument("--basis-points", required=True, type=int)

    activate = commands.add_parser("activate")
    _transition_arguments(
        activate,
        reason_default=None,
        reason_required=True,
    )

    freeze = commands.add_parser("freeze")
    _transition_arguments(freeze, reason_default=None, reason_required=True)

    rollback = commands.add_parser("rollback")
    _transition_arguments(rollback, reason_default=None, reason_required=True)

    token = commands.add_parser("issue-token")
    token.add_argument("--rehearsal-id", required=True)
    token.add_argument("--namespace", required=True)
    token.add_argument("--learner-id", required=True)
    token.add_argument("--request-id", required=True)
    token.add_argument("--operation", choices=["learning_task"], required=True)
    token.add_argument(
        "--fault-profile",
        choices=["none", "latency", "commit_failure"],
        required=True,
    )
    token.add_argument("--ttl-seconds", required=True, type=int)

    head = commands.add_parser("show-head")
    head.add_argument("--environment", choices=["rehearsal"], required=True)
    return value


def _transition_arguments(
    command: argparse.ArgumentParser,
    *,
    reason_default: str | None,
    reason_required: bool = False,
) -> None:
    command.add_argument(
        "--environment",
        choices=["rehearsal"],
        required=True,
    )
    command.add_argument("--expected-version", required=True, type=int)
    command.add_argument("--actor", required=True)
    command.add_argument("--command-id", required=True)
    command.add_argument(
        "--reason",
        required=reason_required,
        default=reason_default,
    )


def _canonical_json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


async def _transition(runtime, args, target: str, traffic: int = 0):
    current = await runtime.service.show_head(args.environment)
    command = PromotionCommand(
        command_id=args.command_id,
        environment=args.environment,
        expected_version=args.expected_version,
        current_state=current.state,
        target_state=target,
        traffic_basis_points=traffic,
        actor=args.actor,
        reason=args.reason,
    )
    return await runtime.service.transition(command)


async def run(args: argparse.Namespace) -> Any:
    runtime = build_promotion_command_runtime(settings)
    try:
        await runtime.start()
        if args.command == "register-campaign":
            from evals.optimization.campaign import Campaign

            from .promotion_service import PromotionService

            return await PromotionService(
                runtime.service.repository
            ).register_campaign(
                Campaign.open(args.campaign),
                actor=args.actor,
                command_id=args.command_id,
            )
        if args.command == "start-shadow":
            return await _transition(runtime, args, "shadow")
        if args.command == "start-canary":
            return await _transition(
                runtime,
                args,
                "canary",
                traffic=args.basis_points,
            )
        if args.command == "activate":
            return await _transition(runtime, args, "active", traffic=10000)
        if args.command == "freeze":
            return await _transition(runtime, args, "frozen")
        if args.command == "rollback":
            return await _transition(runtime, args, "rolled_back")
        if args.command == "issue-token":
            return await runtime.token_issuer.issue(
                rehearsal_id=args.rehearsal_id,
                namespace=args.namespace,
                learner_id=args.learner_id,
                request_id=args.request_id,
                operation=args.operation,
                fault_profile=args.fault_profile,
                ttl_seconds=args.ttl_seconds,
            )
        if args.command == "show-head":
            return await runtime.service.show_head(args.environment)
        raise ValueError(f"unsupported command: {args.command}")
    finally:
        await runtime.close()


def main() -> None:
    args = parser().parse_args()
    print(_canonical_json(asyncio.run(run(args))))


if __name__ == "__main__":
    main()
