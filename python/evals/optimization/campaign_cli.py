"""python -m evals.optimization.campaign_cli；准备、恢复、整链、注册和发布分离。"""

import argparse
import asyncio
import json
from pathlib import Path

from config.settings import settings
from core.policy_store import PolicyRegistry
from evals.optimization.campaign import Campaign
from evals.optimization.cli import DEFAULT_DATASET, configured_service
from evals.optimization.ledger import SharedLedger
from evals.optimization.loop import FailureQueue, ImprovementLoop
from evals.optimization.runtime import run_harness_evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    prepare.add_argument("--protocol", type=Path, required=True)
    prepare.add_argument("--registry", type=Path, required=True)
    prepare.add_argument("--config", type=Path, required=True)
    for name in ("run", "harness", "register", "status", "release", "rollback"):
        command = commands.add_parser(name)
        command.add_argument("--campaign", type=Path, required=True)
        if name in {"run", "harness"}:
            command.add_argument("--allow-remote", action="store_true")
        if name == "run":
            command.add_argument("--holdout", type=Path)
            command.add_argument("--harness-evidence", type=Path)
        if name in {"release", "rollback"}:
            command.add_argument("--enable-release", action="store_true")
    loop = commands.add_parser("loop")
    loop.add_argument("--config", type=Path, required=True)
    loop.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "loop" or args.command in {"run", "harness"}:
        if getattr(args, "allow_remote", False):
            # 初始化服务之前关闭后台或旁路调用；所有模型请求由执行器统一计费。
            settings.memory_worker_enabled = False
            settings.memory_extraction_enabled = False
            settings.memory_retrieval_mode = "lexical"
            settings.memory_rerank_enabled = False
    if args.command == "prepare":
        config = json.loads(args.config.read_text())
        registry = PolicyRegistry(args.registry, runtime_hash=config["deployment_runtime_hash"],
                                  source_revision=config["source_revision"])
        campaign = Campaign.create(args.output, dataset=args.dataset, protocol_path=args.protocol,
                                   registry=registry, config=config)
    elif args.command == "loop":
        config = json.loads(args.config.read_text())
        if not args.allow_remote or config["campaign"]["simulation"]:
            raise ValueError("remote loop requires explicit authorization and real configuration")
        registry = PolicyRegistry(config["registry"],
                                  runtime_hash=config["campaign"]["deployment_runtime_hash"],
                                  source_revision=config["campaign"]["source_revision"])
        runner = ImprovementLoop(config["output"], queue=FailureQueue(config["queue"]),
                                 ledger=SharedLedger(), config=config["limits"])

        def create(index, parent, records, caps):
            per_generation = {**config["campaign"], **config.get("generations", {}).get(str(index), {}),
                              **caps, "failure_summaries": records}
            return Campaign.create(Path(config["output"]) / f"generation-{index:03d}",
                                   dataset=Path(config["dataset"]), protocol_path=Path(config["protocol"]),
                                   registry=registry, config=per_generation, ledger=runner.ledger,
                                   parent_hash=parent)
        def execute(campaign):
            campaign.execute(configured_service(), holdout=campaign.config.get("holdout_path"),
                             harness_evidence=campaign.config.get("harness_evidence"))
        state = runner.run(create, execute)
        print(json.dumps({"status": state["status"], "reason": state.get("reason")}))
        return 0
    else:
        campaign = Campaign.open(args.campaign)
        if args.command in {"run", "harness"}:
            if not args.allow_remote or campaign.config["simulation"]:
                raise ValueError("remote calls require explicit authorization and real configuration")
            service = configured_service()
            if args.command == "run":
                campaign.execute(service, holdout=args.holdout, harness_evidence=args.harness_evidence)
            else:
                campaign.require_qualification()
                if campaign.data["state"] != "holdout_passed":
                    raise ValueError("harness gate requires completed holdout")
                campaign.verify_receipt("holdout")
                asyncio.run(run_harness_evidence(campaign, service))
        elif args.command == "register":
            campaign.register()
        elif args.command in {"release", "rollback"}:
            campaign.require_qualification()
            registry = PolicyRegistry(campaign.data["registry"],
                                      runtime_hash=campaign.config["deployment_runtime_hash"],
                                      source_revision=campaign.config["source_revision"])
            if args.command == "release":
                registry.activate(campaign.policy_artifact()["policy_hash"],
                                  release_enabled=args.enable_release)
            else:
                registry.rollback(release_enabled=args.enable_release)
    print(json.dumps({"campaign": str(campaign.root), "state": campaign.data["state"],
                      "budget": campaign.budget.summary()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
