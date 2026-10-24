"""EduAgent 离线评测命令行入口。"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from evals.adapters.mrbench import fetch_and_convert
from evals.io import DatasetError, load_cases, write_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="eduagent-eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate JSONL cases")
    validate.add_argument("--dataset", type=Path)
    validate.add_argument("--suite")

    listing = subparsers.add_parser("list", help="list cases")
    listing.add_argument("--dataset", type=Path)
    listing.add_argument("--suite")

    run = subparsers.add_parser("run", help="run an offline evaluation suite")
    run.add_argument("--dataset", type=Path)
    run.add_argument("--suite", default="builtin")
    run.add_argument("--output", type=Path)

    live = subparsers.add_parser("run-live", help="run reviewed scripts with a real tutor model")
    live.add_argument("--dataset", type=Path, required=True)
    live.add_argument("--output", type=Path, default=Path("eval-results/tutor-live12.json"))
    live.add_argument("--max-requests", type=int, default=42)
    live.add_argument("--max-cny", type=float, default=3.0)

    fetch = subparsers.add_parser("fetch", help="fetch an external dataset")
    fetch.add_argument("dataset", choices=["mrbench"])
    fetch.add_argument("--cache-dir", type=Path)
    fetch.add_argument("--force", action="store_true")
    return parser


def _default_output(suite: str) -> Path:
    return Path("eval-results") / f"{suite}.json"


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            cases = load_cases(args.dataset, suite=args.suite)
            print(f"valid: {len(cases)} cases")
            return 0
        if args.command == "list":
            cases = load_cases(args.dataset, suite=args.suite)
            for case in cases:
                print(f"{case.case_id}\t{case.kind}\t{','.join(case.tags)}")
            return 0
        if args.command == "fetch":
            converted = fetch_and_convert(args.cache_dir, force=args.force)
            print(converted)
            return 0
        if args.command == "run-live":
            from evals.live_runner import run_live_suite

            def progress(result, budget):
                print(f"{result['case_id']}: {result['status']} "
                      f"(requests={budget['requests']}, "
                      f"peak_estimate={budget['estimated_peak_cny']:.6f} CNY)", flush=True)

            report = asyncio.run(run_live_suite(
                path=args.dataset, output=args.output,
                max_requests=args.max_requests, max_cny=args.max_cny, progress=progress,
            ))
            for role, metrics in report["groups"].items():
                print(f"{role}: {metrics['automatic_passed']}/{metrics['valid_fixtures']} "
                      f"automatic contracts passed; {metrics['review_pending']} review pending")
            print(f"report: {args.output}")
            return 1 if any(r["status"] in {"failed", "fixture_invalid"}
                            for r in report["results"]) else 0
        if args.command == "run":
            from evals.runner import run_suite

            report = asyncio.run(
                run_suite(path=args.dataset, suite=args.suite)
            )
            output = args.output or _default_output(args.suite)
            write_json(output, report.model_dump(mode="json"))
            print(
                f"{report.suite}: {report.passed}/{report.total} passed "
                f"({report.pass_rate:.1%})"
            )
            for result in report.results:
                if not result.passed:
                    messages = "; ".join(
                        detail.message for detail in result.details if detail.message
                    )
                    print(f"FAIL {result.case_id}: {messages}")
            print(f"report: {output}")
            return 0 if report.failed == 0 else 1
    except DatasetError as exc:
        print(f"dataset error: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"evaluation error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
