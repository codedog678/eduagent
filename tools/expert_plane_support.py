"""Shared real-infrastructure helpers for Expert Plane evidence tools."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
DEFAULT_PYTHON = ROOT / ".venv" / "bin" / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from core.distributed.contracts import (
    DistributedRunRequest,
    RunOperation,
)
from core.distributed.expert_contracts import (
    ExpertBudget,
    ExpertJobRequest,
    ExpertRole,
    ExpertSnapshot,
    RunExecutionAuthority,
)
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

def python_executable() -> str:
    return str(DEFAULT_PYTHON) if DEFAULT_PYTHON.exists() else sys.executable


def database_url() -> str:
    return os.getenv(
        "DISTRIBUTED_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent",
    )


def redis_url() -> str:
    return os.getenv(
        "DISTRIBUTED_REDIS_URL",
        "redis://localhost:6379/15",
    )


@dataclass
class IsolatedDatabase:
    name: str
    url: str
    engine: Any
    admin_engine: Any

    async def close(self) -> None:
        await self.engine.dispose()
        try:
            async with self.admin_engine.connect() as connection:
                connection = await connection.execution_options(
                    isolation_level="AUTOCOMMIT"
                )
                await connection.execute(
                    text(
                        f'DROP DATABASE IF EXISTS "{self.name}" '
                        "WITH (FORCE)"
                    )
                )
        finally:
            await self.admin_engine.dispose()


async def isolated_database(prefix: str) -> IsolatedDatabase:
    name = f"{prefix}_{os.urandom(8).hex()}"
    source_url = make_url(database_url())
    target_url = source_url.set(database=name)
    rendered_url = target_url.render_as_string(hide_password=False)
    admin_engine = create_async_engine(source_url, pool_pre_ping=True)
    try:
        async with admin_engine.connect() as connection:
            connection = await connection.execution_options(
                isolation_level="AUTOCOMMIT"
            )
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
        engine = create_async_engine(
            target_url,
            pool_pre_ping=True,
        )
        return IsolatedDatabase(
            name=name,
            url=rendered_url,
            engine=engine,
            admin_engine=admin_engine,
        )
    except BaseException:
        await admin_engine.dispose()
        raise


def git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def git_worktree_evidence() -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    digest = hashlib.sha256()
    digest.update(
        subprocess.run(
            ["git", "diff", "--binary", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    for raw_path in sorted(path for path in untracked if path):
        path = ROOT / raw_path.decode("utf-8")
        digest.update(raw_path)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return {
        "dirty": bool(status),
        "diff_sha256": digest.hexdigest(),
    }


def fingerprint(config: dict[str, Any]) -> str:
    encoded = json.dumps(
        config,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def run_request(
    request_id: str,
    *,
    learner_id: str,
) -> DistributedRunRequest:
    return DistributedRunRequest(
        learner_id=learner_id,
        request_id=request_id,
        operation=RunOperation.LEARNING_TASK,
        payload={
            "learner_id": learner_id,
            "request_id": request_id,
            "knowledge_id": "grammar_tenses",
            "question": "Assess understanding of English tense selection.",
        },
    )


def expert_request(
    claim,
    *,
    logical_key: str,
    role: ExpertRole = ExpertRole.ASSESSMENT,
) -> ExpertJobRequest:
    deadline = min(
        claim.deadline_at,
        datetime.now(UTC) + timedelta(seconds=60),
    )
    return ExpertJobRequest(
        logical_key=logical_key,
        learner_id=claim.learner_id,
        step_id=f"step-{logical_key}",
        role=role,
        objective="Assess current tense understanding",
        plan_id=f"plan-{claim.request_id}",
        plan_version=1,
        snapshot=ExpertSnapshot(
            learner_id=claim.learner_id,
            knowledge_id="grammar_tenses",
            current_input="Explain when to use the present perfect.",
            goal="Assess tense understanding",
            effective_policy_hash="a" * 64,
        ),
        budget=ExpertBudget(
            max_model_calls=3,
            max_tool_calls=4,
            max_output_tokens=800,
            max_context_tokens=6000,
            max_attempts=3,
            deadline_at=deadline,
        ),
        authority=RunExecutionAuthority(
            distributed_run_id=claim.run_id,
            run_fencing_token=claim.fencing_token,
            trace_id=claim.trace_id,
            attempt_number=claim.attempt_count,
            worker_id="evidence-parent",
            parent_deadline_at=claim.deadline_at,
        ),
    )


def worker_environment(
    *,
    stream: str,
    group: str,
    worker_id: str,
    pause_before_result: float,
    suffix: str,
    database_url_value: str | None = None,
) -> dict[str, str]:
    inherited = {
        key: os.environ[key]
        for key in (
            "HOME",
            "LANG",
            "LC_ALL",
            "PATH",
            "TMPDIR",
        )
        if key in os.environ
    }
    return {
        **inherited,
        "PYTHONPATH": str(PYTHON_ROOT),
        "DISTRIBUTED_ENABLED": "true",
        "DISTRIBUTED_EXPERTS_ENABLED": "true",
        "DISTRIBUTED_DATABASE_URL": (
            database_url_value or database_url()
        ),
        "DISTRIBUTED_REDIS_URL": redis_url(),
        "DISTRIBUTED_STREAM": f"eduagent:evidence:runs:{suffix}",
        "DISTRIBUTED_CONSUMER_GROUP": (
            f"eduagent-evidence-run-workers-{suffix}"
        ),
        "EXPERT_STREAM": stream,
        "EXPERT_CONSUMER_GROUP": group,
        "EXPERT_WORKER_ID": worker_id,
        "EXPERT_WORKER_ROLES": "Assessment",
        "EXPERT_LEASE_SECONDS": "3",
        "EXPERT_HEARTBEAT_SECONDS": "0.5",
        "EXPERT_POLL_BLOCK_MS": "50",
        "EXPERT_RETRY_BASE_SECONDS": "0.1",
        "EXPERT_RETRY_MAX_SECONDS": "0.1",
        "EXPERT_DEMO_PAUSE_BEFORE_RESULT_SECONDS": str(
            pause_before_result
        ),
        "LLM_PROVIDER": "template",
        "MEMORY_RETRIEVAL_MODE": "lexical",
        "MEMORY_WORKER_ENABLED": "false",
    }


@dataclass
class ManagedProcess:
    process: subprocess.Popen
    log_path: Path

    @property
    def pid(self) -> int:
        return self.process.pid

    def assert_running(self, label: str) -> None:
        code = self.process.poll()
        if code is None:
            return
        raise RuntimeError(
            f"{label} exited with code {code}: {self.stderr()}"
        )

    def stop(self, *, kill: bool = False) -> None:
        if self.process.poll() is None:
            self.process.kill() if kill else self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait(timeout=5)

    def stderr(self) -> str:
        try:
            return self.log_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            return ""


def spawn_expert_worker(
    *,
    stream: str,
    group: str,
    worker_id: str,
    pause_before_result: float,
    suffix: str,
    log_dir: Path,
    database_url_value: str | None = None,
) -> ManagedProcess:
    log_path = log_dir / f"{worker_id}.stderr.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                python_executable(),
                "-m",
                "core.distributed.cli",
                "expert-worker",
            ],
            cwd=PYTHON_ROOT,
            env=worker_environment(
                stream=stream,
                group=group,
                worker_id=worker_id,
                pause_before_result=pause_before_result,
                suffix=suffix,
                database_url_value=database_url_value,
            ),
            stdout=subprocess.DEVNULL,
            stderr=log,
            text=True,
        )
    return ManagedProcess(process=process, log_path=log_path)


async def wait_until(
    predicate: Callable[[], Awaitable[Any]],
    *,
    timeout: float = 20,
    interval: float = 0.05,
) -> Any:
    async with asyncio.timeout(timeout):
        while True:
            value = await predicate()
            if value:
                return value
            await asyncio.sleep(interval)


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(
        0,
        min(len(ordered) - 1, int(quantile * len(ordered) - 1e-12)),
    )
    return ordered[index]
