from __future__ import annotations

from pathlib import Path
import re

from .promotion_contracts import Environment, PolicyExecutionBinding

NAMESPACE = re.compile(r"rehearsal-[a-z0-9][a-z0-9-]{0,62}", re.ASCII)


def validate_environment(binding: PolicyExecutionBinding, allowed_environment: Environment) -> None:
    if allowed_environment not in {"production", "rehearsal"}:
        raise ValueError("invalid allowed environment")
    if binding.environment != allowed_environment:
        raise ValueError("policy binding environment differs from worker capability")
    if binding.environment == "production":
        if binding.state_namespace != "production" or binding.rehearsal_id is not None:
            raise ValueError("invalid production policy binding namespace")
    elif (
        not NAMESPACE.fullmatch(binding.state_namespace)
        or not binding.rehearsal_id
        or binding.state_namespace != f"rehearsal-{binding.rehearsal_id}"
    ):
        raise ValueError("invalid rehearsal policy binding namespace")


class RehearsalStoreRouter:
    def __init__(
        self, production_path: str | Path, rehearsal_root: str | Path,
        *, allowed_environment: Environment,
    ) -> None:
        if allowed_environment not in {"production", "rehearsal"}:
            raise ValueError("invalid allowed environment")
        self.production_path = Path(production_path)
        self.rehearsal_root = Path(rehearsal_root)
        self.allowed_environment = allowed_environment

    def path_for(self, binding: PolicyExecutionBinding) -> Path:
        validate_environment(binding, self.allowed_environment)
        if binding.environment == "production":
            return self.production_path
        root = self.rehearsal_root.resolve()
        candidate = (root / binding.state_namespace / "harness.sqlite3").resolve()
        try:
            candidate.relative_to(root)
        except ValueError:
            raise ValueError("rehearsal store escapes configured root") from None
        candidate.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        return candidate
