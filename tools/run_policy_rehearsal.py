#!/usr/bin/env python3
"""Run a fail-closed trusted-policy promotion rehearsal."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import urlencode

import httpx


ARTIFACT_NAMES = (
    "manifest.json",
    "requests.jsonl",
    "gate_receipts.jsonl",
    "health_windows.jsonl",
    "audit_timeline.jsonl",
    "prometheus.txt",
    "summary.md",
)
TERMINAL_STATUSES = {
    "completed",
    "terminal_failed",
    "exhausted",
    "cancelled",
}
TOKEN_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
SENSITIVE_TEXT_PATTERN = re.compile(
    r"(?i)(authorization\s*:|bearer\s+|x-eduagent-rehearsal|"
    r'\\"(?:nonce|token)\\"\s*:|"(?:nonce|token)"\s*:)',
)


class RehearsalRejected(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Run a controlled trusted-policy promotion rehearsal",
    )
    value.add_argument("--api-url", required=True)
    value.add_argument(
        "--ops-token",
        required=True,
        help="env:VARIABLE or - to read the bearer token from stdin",
    )
    value.add_argument("--campaign", required=True, type=Path)
    value.add_argument("--actor", required=True)
    value.add_argument(
        "--candidate-basis-points",
        required=True,
        type=int,
        choices=range(1, 10000),
        metavar="1..9999",
    )
    value.add_argument("--healthy-runs", required=True, type=int)
    value.add_argument("--failure-runs", required=True, type=int)
    value.add_argument("--output", required=True, type=Path)
    return value


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RehearsalRejected(
            "campaign_missing",
            f"required campaign file does not exist: {path}",
        ) from None
    except (OSError, json.JSONDecodeError):
        raise RehearsalRejected(
            "campaign_invalid",
            f"cannot parse campaign file: {path}",
        ) from None
    if not isinstance(value, dict):
        raise RehearsalRejected(
            "campaign_invalid",
            "campaign document must be a JSON object",
        )
    return value


def preflight_campaign(
    root: Path,
    *,
    campaign_loader: Callable[[Path], Any] | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Validate release eligibility before opening runtime-backed campaign state."""
    root = root.resolve()
    campaign_data = _load_json(root / "campaign.json")
    config = campaign_data.get("config")
    protocol = campaign_data.get("protocol")
    if not isinstance(config, dict) or not isinstance(protocol, dict):
        raise RehearsalRejected(
            "campaign_invalid",
            "campaign config and protocol must be objects",
        )
    if config.get("simulation") is not False:
        raise RehearsalRejected(
            "campaign_simulation_not_release_eligible",
            "simulation campaigns cannot run a formal rehearsal",
        )
    if config.get("mode", "qualification") != "qualification":
        raise RehearsalRejected(
            "campaign_exploratory_not_release_eligible",
            "exploratory campaigns cannot run a formal rehearsal",
        )
    if campaign_data.get("state") != "eligible":
        raise RehearsalRejected(
            "campaign_not_eligible",
            "campaign state must be eligible",
        )
    if protocol.get("schema") != "eduagent.gepa.v3":
        raise RehearsalRejected(
            "campaign_protocol_not_judge_v3",
            "formal rehearsal requires eduagent.gepa.v3",
        )

    if campaign_loader is None:
        from evals.optimization.campaign import Campaign

        campaign_loader = Campaign.open
    try:
        campaign = campaign_loader(root)
        material = campaign.qualification_material()
    except RehearsalRejected:
        raise
    except Exception as exc:
        raise RehearsalRejected(
            "campaign_qualification_invalid",
            f"formal qualification failed ({type(exc).__name__})",
        ) from None
    return campaign, material


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def resolve_ops_token(reference: str) -> str:
    if reference == "-":
        value = sys.stdin.readline().strip()
    elif reference.startswith("env:"):
        name = reference[4:]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise RehearsalRejected(
                "ops_token_reference_invalid",
                "Ops token environment variable name is invalid",
            )
        value = os.getenv(name, "").strip()
    else:
        raise RehearsalRejected(
            "ops_token_transport_unsafe",
            "pass --ops-token env:VARIABLE or read it from stdin with -",
        )
    if not value:
        raise RehearsalRejected(
            "ops_token_missing",
            "Ops bearer token is empty",
        )
    return value


class PromotionCLI:
    def __init__(
        self,
        *,
        python_dir: Path,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.python_dir = python_dir
        self.runner = runner

    def run(self, *arguments: str) -> dict[str, Any]:
        completed = self.runner(
            [
                sys.executable,
                "-m",
                "core.distributed.promotion_cli",
                *arguments,
            ],
            cwd=self.python_dir,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            digest = hashlib.sha256(
                completed.stderr.encode("utf-8", errors="replace")
            ).hexdigest()
            raise RehearsalRejected(
                "promotion_command_failed",
                f"{arguments[0]} failed; stderr_sha256={digest}",
            )
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raise RehearsalRejected(
                "promotion_command_invalid_output",
                f"{arguments[0]} returned non-JSON output",
            ) from None
        if not isinstance(value, dict):
            raise RehearsalRejected(
                "promotion_command_invalid_output",
                f"{arguments[0]} returned a non-object",
            )
        return value


class RehearsalAPI:
    def __init__(
        self,
        api_url: str,
        ops_token: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = api_url.rstrip("/")
        self.ops_token = ops_token
        self.client = client or httpx.Client(timeout=15)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> httpx.Response:
        response = self.client.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            json=json_body,
        )
        response.raise_for_status()
        return response

    def ops(self, path: str) -> dict[str, Any]:
        response = self._request(
            "GET",
            path,
            headers={"Authorization": f"Bearer {self.ops_token}"},
        )
        value = response.json()
        if not isinstance(value, dict):
            raise RehearsalRejected(
                "ops_invalid_response",
                f"{path} returned a non-object",
            )
        return value

    def submit(
        self,
        *,
        token: str,
        learner_id: str,
        request_id: str,
    ) -> dict[str, Any]:
        body = {
            "learner_id": learner_id,
            "request_id": request_id,
            "operation": "learning_task",
            "payload": {
                "learner_id": learner_id,
                "request_id": request_id,
                "knowledge_id": "grammar_tenses",
                "question": "Review tense selection with one example.",
            },
        }
        response = self._request(
            "POST",
            "/api/distributed/runs",
            headers={
                "Content-Type": "application/json",
                "X-EduAgent-Rehearsal": token,
            },
            json_body=body,
        )
        return response.json()

    def run_status(self, run_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            f"/api/distributed/runs/{run_id}",
        ).json()

    def metrics(self) -> str:
        return self._request("GET", "/metrics").text


def _wait_until(
    operation: Callable[[], Any],
    predicate: Callable[[Any], bool],
    *,
    timeout: float = 180,
    interval: float = 0.5,
) -> Any:
    deadline = time.monotonic() + timeout
    latest = None
    while time.monotonic() < deadline:
        latest = operation()
        if predicate(latest):
            return latest
        time.sleep(interval)
    raise RehearsalRejected(
        "rehearsal_timeout",
        f"timed out waiting for condition; latest={_canonical(latest)[:500]}",
    )


def _command_id(rehearsal_id: str, action: str) -> str:
    return f"{rehearsal_id}-{action}"


def _start_transition(
    cli: PromotionCLI,
    action: str,
    snapshot: dict[str, Any],
    *,
    actor: str,
    rehearsal_id: str,
    basis_points: int | None = None,
) -> dict[str, Any]:
    args = [
        action,
        "--environment",
        "rehearsal",
        "--expected-version",
        str(snapshot["version"]),
        "--actor",
        actor,
        "--command-id",
        _command_id(rehearsal_id, action),
    ]
    if basis_points is not None:
        args.extend(["--basis-points", str(basis_points)])
    return cli.run(*args)


def _issue_and_submit(
    *,
    cli: PromotionCLI,
    api: RehearsalAPI,
    rehearsal_id: str,
    learner_id: str,
    request_id: str,
    fault_profile: str,
) -> dict[str, Any]:
    issued = cli.run(
        "issue-token",
        "--rehearsal-id",
        rehearsal_id,
        "--namespace",
        f"rehearsal-{rehearsal_id}",
        "--learner-id",
        learner_id,
        "--request-id",
        request_id,
        "--operation",
        "learning_task",
        "--fault-profile",
        fault_profile,
        "--ttl-seconds",
        "300",
    )
    token = issued.pop("token", None)
    if not isinstance(token, str) or not token:
        raise RehearsalRejected(
            "rehearsal_token_missing",
            "token issuer did not return an in-memory token",
        )
    accepted = api.submit(
        token=token,
        learner_id=learner_id,
        request_id=request_id,
    )
    run_id = accepted["run_id"]
    terminal = _wait_until(
        lambda: api.run_status(run_id),
        lambda value: value.get("status") in TERMINAL_STATUSES,
    )
    ops_run = api.ops(f"/ops/runs/{run_id}")
    return {
        "request_id": request_id,
        "run_id": run_id,
        "expected_cohort": issued.get("expected_cohort"),
        "policy_binding": accepted.get("policy_binding"),
        "status": terminal.get("status"),
        "usage": ops_run.get("usage"),
        "latency_ms": ops_run.get("latency_ms"),
        "fault_profile": fault_profile,
    }


def _detail_has_passed_gate(detail: dict[str, Any], gate: str) -> bool:
    return any(
        receipt.get("gate_type") == gate and receipt.get("status") == "passed"
        for receipt in detail.get("gate_receipts", [])
    )


def _common_evidence(
    material: dict[str, Any],
    *,
    rehearsal_id: str,
    requested: dict[str, int],
    actual: dict[str, int],
    rehearsal_cost: dict[str, Any],
) -> dict[str, Any]:
    artifact = material["artifact"]
    receipts = material["receipts"]
    identities = sorted(
        {
            receipt["model_identity"]
            for receipt in receipts
            if receipt.get("model_identity")
        }
    )
    return {
        "schema_version": 1,
        "rehearsal_id": rehearsal_id,
        "source_revision": artifact["source_revision"],
        "runtime_hash": artifact["runtime_hash"],
        "protocol_hash": artifact["protocol_hash"],
        "threshold_hashes": [],
        "provider_model_identity": identities,
        "data_role": "controlled_rehearsal",
        "release_eligible": False,
        "requested_counts": requested,
        "actual_counts": actual,
        "cost": {
            "qualification_budget": material["budget"],
            "rehearsal": rehearsal_cost,
        },
    }


def _write_jsonl(
    path: Path,
    rows: Iterable[dict[str, Any]],
    evidence: dict[str, Any],
) -> None:
    wrote = False
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(_canonical({"evidence": evidence, "record": row}))
            handle.write("\n")
            wrote = True
        if not wrote:
            handle.write(_canonical({"evidence": evidence, "record": None}))
            handle.write("\n")


def _scan_tree(root: Path, forbidden: Iterable[str]) -> None:
    forbidden_values = [value for value in forbidden if value]
    for path in root.iterdir():
        text = path.read_text(encoding="utf-8")
        if TOKEN_PATTERN.search(text) or SENSITIVE_TEXT_PATTERN.search(text):
            raise RehearsalRejected(
                "artifact_secret_scan_failed",
                f"sensitive token shape found in {path.name}",
            )
        for value in forbidden_values:
            if value in text:
                raise RehearsalRejected(
                    "artifact_secret_scan_failed",
                    f"sensitive value found in {path.name}",
                )


def _ops_items(
    api: RehearsalAPI,
    path: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    items = []
    cursor = None
    seen = set()
    while True:
        query = {**params, "limit": 100}
        if cursor is not None:
            query["cursor"] = cursor
        page = api.ops(f"{path}?{urlencode(query)}")
        page_items = page.get("items")
        if not isinstance(page_items, list):
            raise RehearsalRejected(
                "ops_invalid_response",
                f"{path} did not return an item list",
            )
        items.extend(page_items)
        cursor = page.get("next_cursor")
        if cursor is None:
            return items
        if not isinstance(cursor, str) or cursor in seen:
            raise RehearsalRejected(
                "ops_invalid_response",
                f"{path} returned an invalid cursor chain",
            )
        seen.add(cursor)


def publish_artifacts(
    output: Path,
    *,
    evidence: dict[str, Any],
    requests: list[dict[str, Any]],
    deployments: list[dict[str, Any]],
    health_windows: list[dict[str, Any]],
    audits: list[dict[str, Any]],
    metrics: str,
    forbidden: Iterable[str],
) -> None:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output.parent / f".{output.name}.lock"
    lock_handle = lock_path.open("a+")
    try:
        try:
            fcntl.flock(lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RehearsalRejected(
                "output_locked",
                f"another publisher owns output: {output}",
            ) from None
        if output.exists():
            raise RehearsalRejected(
                "output_exists",
                f"refusing to overwrite existing output: {output}",
            )
        staging = Path(
            tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent)
        )
        try:
            manifest = {
                "evidence": evidence,
                "artifacts": list(ARTIFACT_NAMES),
                "generated_at": datetime.now(UTC).isoformat(),
            }
            (staging / "manifest.json").write_text(
                f"{_canonical(manifest)}\n",
                encoding="utf-8",
            )
            _write_jsonl(staging / "requests.jsonl", requests, evidence)
            _write_jsonl(
                staging / "gate_receipts.jsonl",
                (
                    receipt
                    for deployment in deployments
                    for receipt in deployment.get("gate_receipts", [])
                ),
                evidence,
            )
            _write_jsonl(
                staging / "health_windows.jsonl",
                health_windows,
                evidence,
            )
            _write_jsonl(staging / "audit_timeline.jsonl", audits, evidence)
            (staging / "prometheus.txt").write_text(
                f"# eduagent_rehearsal_metadata {_canonical(evidence)}\n{metrics}",
                encoding="utf-8",
            )
            counts = evidence["actual_counts"]
            summary = f"""# Trusted Policy Promotion Rehearsal

This is controlled rehearsal traffic, not production student traffic.
Operational guardrails do not establish learning-effect improvement.

- Rehearsal: `{evidence["rehearsal_id"]}`
- Data role: `{evidence["data_role"]}`
- Release eligible: `{str(evidence["release_eligible"]).lower()}`
- Requests: `{counts["requests"]}`
- Failed: `{counts["failed"]}`
- Interrupted: `{counts["interrupted"]}`
- Source revision: `{evidence["source_revision"]}`
- Runtime hash: `{evidence["runtime_hash"]}`
- Protocol hash: `{evidence["protocol_hash"]}`
- Threshold hashes: `{_canonical(evidence["threshold_hashes"])}`
- Provider/model identity: `{_canonical(evidence["provider_model_identity"])}`
- Requested counts: `{_canonical(evidence["requested_counts"])}`
- Cost ledger: `{_canonical(evidence["cost"])}`
"""
            (staging / "summary.md").write_text(summary, encoding="utf-8")
            _scan_tree(staging, forbidden)
            os.rename(staging, output)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
    finally:
        lock_handle.close()
        lock_path.unlink(missing_ok=True)


def run_rehearsal(args: argparse.Namespace) -> Path:
    if args.healthy_runs < 1 or args.failure_runs < 1:
        raise RehearsalRejected(
            "invalid_run_counts",
            "healthy-runs and failure-runs must both be positive",
        )
    _, material = preflight_campaign(args.campaign)
    if args.output.resolve().exists():
        raise RehearsalRejected(
            "output_exists",
            f"refusing to overwrite existing output: {args.output.resolve()}",
        )

    repo_root = Path(__file__).resolve().parents[1]
    cli = PromotionCLI(python_dir=repo_root / "python")
    ops_token = resolve_ops_token(args.ops_token)
    api = RehearsalAPI(args.api_url, ops_token)
    now = datetime.now(UTC)
    rehearsal_id = f"m3-{now:%Y%m%d}-{hashlib.sha256(os.urandom(16)).hexdigest()[:10]}"
    learner_id = f"{rehearsal_id}-learner"
    rows: list[dict[str, Any]] = []
    deployments: list[dict[str, Any]] = []
    secrets_seen = [
        ops_token,
        os.getenv("PROMOTION_REHEARSAL_SECRET", ""),
        os.getenv("PROMOTION_ASSIGNMENT_SECRET", ""),
    ]

    try:
        registered = cli.run(
            "register-campaign",
            "--campaign",
            str(args.campaign.resolve()),
            "--actor",
            args.actor,
            "--command-id",
            _command_id(rehearsal_id, "register"),
        )
        shadow = _start_transition(
            cli,
            "start-shadow",
            registered,
            actor=args.actor,
            rehearsal_id=rehearsal_id,
        )
        shadow_minimum = int(
            shadow.get("thresholds", {}).get("candidate_min_runs", 20)
        )
        for index in range(shadow_minimum):
            rows.append(
                _issue_and_submit(
                    cli=cli,
                    api=api,
                    rehearsal_id=rehearsal_id,
                    learner_id=learner_id,
                    request_id=f"{rehearsal_id}-shadow-{index}",
                    fault_profile="none",
                )
            )
        shadow_detail = _wait_until(
            lambda: api.ops(
                f"/ops/policies/deployments/{shadow['deployment_id']}"
            ),
            lambda value: _detail_has_passed_gate(value, "shadow_health"),
        )
        deployments.append(shadow_detail)

        canary = _start_transition(
            cli,
            "start-canary",
            shadow,
            actor=args.actor,
            rehearsal_id=rehearsal_id,
            basis_points=args.candidate_basis_points,
        )
        minimums = canary.get("thresholds", {})
        required_candidate = int(minimums.get("candidate_min_runs", 20))
        required_stable = int(minimums.get("stable_min_runs", 20))
        healthy_target = max(
            args.healthy_runs,
            required_candidate + required_stable,
        )
        cohort_counts = {"candidate": 0, "stable": 0}
        index = 0
        while (
            index < healthy_target
            or cohort_counts["candidate"] < required_candidate
            or cohort_counts["stable"] < required_stable
        ):
            row = _issue_and_submit(
                cli=cli,
                api=api,
                rehearsal_id=rehearsal_id,
                learner_id=learner_id,
                request_id=f"{rehearsal_id}-healthy-{index}",
                fault_profile="none",
            )
            rows.append(row)
            cohort = row.get("expected_cohort")
            if cohort in cohort_counts:
                cohort_counts[cohort] += 1
            index += 1
            if index > healthy_target + 10000:
                raise RehearsalRejected(
                    "cohort_assignment_unavailable",
                    "could not satisfy both canary cohort minimums",
                )
        canary_detail = _wait_until(
            lambda: api.ops(
                f"/ops/policies/deployments/{canary['deployment_id']}"
            ),
            lambda value: _detail_has_passed_gate(value, "canary_health"),
        )
        deployments.append(canary_detail)

        rollback_detail = None
        candidate_faults = 0
        index = 0
        while candidate_faults < args.failure_runs:
            row = _issue_and_submit(
                cli=cli,
                api=api,
                rehearsal_id=rehearsal_id,
                learner_id=learner_id,
                request_id=f"{rehearsal_id}-failure-{index}",
                fault_profile="commit_failure",
            )
            rows.append(row)
            if row.get("expected_cohort") == "candidate":
                candidate_faults += 1
            detail = api.ops(
                f"/ops/policies/deployments/{canary['deployment_id']}"
            )
            if any(
                event.get("event_type") == "health_rollback"
                for event in detail.get("audit_events", [])
            ):
                rollback_detail = detail
                break
            index += 1
            if index > args.failure_runs + 10000:
                raise RehearsalRejected(
                    "candidate_fault_assignment_unavailable",
                    "could not assign bounded fault traffic to candidate",
                )
        if rollback_detail is None:
            rollback_detail = _wait_until(
                lambda: api.ops(
                    f"/ops/policies/deployments/{canary['deployment_id']}"
                ),
                lambda value: any(
                    event.get("event_type") == "health_rollback"
                    for event in value.get("audit_events", [])
                ),
            )
        deployments[-1] = rollback_detail

        health_windows = []
        for deployment in (shadow, canary):
            health_windows.extend(
                _ops_items(
                    api,
                    "/ops/policies/health-windows",
                    {
                        "environment": "rehearsal",
                        "deployment_id": deployment["deployment_id"],
                    },
                )
            )
        audit_by_id = {}
        for deployment in (registered, shadow, canary):
            for event in _ops_items(
                api,
                "/ops/policies/audit",
                {
                    "environment": "rehearsal",
                    "deployment_id": deployment["deployment_id"],
                },
            ):
                audit_by_id[event["event_id"]] = event
        audits = sorted(
            audit_by_id.values(),
            key=lambda event: (event["created_at"], event["event_id"]),
        )
        registered_detail = api.ops(
            f"/ops/policies/deployments/{registered['deployment_id']}"
        )
        deployments.insert(0, registered_detail)
        failed = sum(
            row["status"] in {"terminal_failed", "exhausted"}
            for row in rows
        )
        interrupted = sum(row["status"] == "cancelled" for row in rows)
        known_cost = [
            (row.get("usage") or {}).get("estimated_cost_usd")
            for row in rows
            if (row.get("usage") or {}).get("estimated_cost_usd") is not None
        ]
        actual = {
            "requests": len(rows),
            "failed": failed,
            "interrupted": interrupted,
            "model_calls": sum(
                int((row.get("usage") or {}).get("model_calls") or 0)
                for row in rows
            ),
        }
        evidence = _common_evidence(
            material,
            rehearsal_id=rehearsal_id,
            requested={
                "healthy": args.healthy_runs,
                "failure": args.failure_runs,
            },
            actual=actual,
            rehearsal_cost={
                "currency": "USD",
                "estimated_total": str(
                    sum(float(value) for value in known_cost)
                ),
                "known_run_count": len(known_cost),
                "unknown_run_count": len(rows) - len(known_cost),
            },
        )
        evidence["threshold_hashes"] = sorted(
            {
                value["thresholds_hash"]
                for value in deployments
                if value.get("thresholds_hash")
            }
        )
        publish_artifacts(
            args.output,
            evidence=evidence,
            requests=rows,
            deployments=deployments,
            health_windows=health_windows,
            audits=audits,
            metrics=api.metrics(),
            forbidden=secrets_seen,
        )
        return args.output.resolve()
    finally:
        api.close()


def main() -> int:
    args = parser().parse_args()
    try:
        output = run_rehearsal(args)
    except RehearsalRejected as exc:
        print(f"rehearsal rejected [{exc.code}]: {exc.detail}", file=sys.stderr)
        return 2
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        print(
            f"rehearsal failed [runtime_error]: {type(exc).__name__}",
            file=sys.stderr,
        )
        return 1
    print(f"rehearsal evidence published: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
