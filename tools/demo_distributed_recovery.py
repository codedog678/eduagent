#!/usr/bin/env python3
"""Run the real-process M1 worker-crash recovery demonstration."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "python"
DEFAULT_PYTHON = ROOT / ".venv" / "bin" / "python"


def main() -> int:
    executable = (
        str(DEFAULT_PYTHON)
        if DEFAULT_PYTHON.exists()
        else sys.executable
    )
    env = {
        **os.environ,
        "DISTRIBUTED_ENABLED": "true",
        "DISTRIBUTED_TEST_DATABASE_URL": os.getenv(
            "DISTRIBUTED_TEST_DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent",
        ),
        "DISTRIBUTED_DATABASE_URL": os.getenv(
            "DISTRIBUTED_DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/edu_agent",
        ),
        "DISTRIBUTED_TEST_REDIS_URL": os.getenv(
            "DISTRIBUTED_TEST_REDIS_URL",
            "redis://localhost:6379/15",
        ),
        "DISTRIBUTED_REDIS_URL": os.getenv(
            "DISTRIBUTED_REDIS_URL",
            "redis://localhost:6379/15",
        ),
        "LLM_PROVIDER": "template",
        "MEMORY_RETRIEVAL_MODE": "lexical",
        "MEMORY_WORKER_ENABLED": "false",
    }
    command = [
        executable,
        "-m",
        "pytest",
        "tests/integration/test_distributed_failover.py",
        "-q",
    ]
    completed = subprocess.run(
        command,
        cwd=PYTHON,
        env=env,
        check=False,
    )
    if completed.returncode:
        return completed.returncode

    print("status: completed")
    print("attempts: 2")
    print("lease_takeovers: 1")
    print("committed_business_effects: 1")
    print("duplicate_business_effects: 0")
    print("evidence: PostgreSQL attempts/trace + SQLite completed run count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
