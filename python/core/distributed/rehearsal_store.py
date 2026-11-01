from __future__ import annotations

from pathlib import Path
import fcntl
import os
import re
import shutil
from uuid import UUID

from .promotion_contracts import Environment, PolicyExecutionBinding

NAMESPACE = re.compile(r"rehearsal-[a-z0-9][a-z0-9-]{0,62}", re.ASCII)


def validate_environment(binding: PolicyExecutionBinding, allowed_environment: Environment) -> None:
    if allowed_environment not in {"production", "rehearsal"}:
        raise ValueError("invalid allowed environment")
    if binding.environment != allowed_environment:
        raise ValueError("policy binding environment differs from worker capability")
    if binding.policy_cohort == "shadow":
        raise ValueError("shadow requires dedicated store capability")
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


def validate_shadow_binding(binding: PolicyExecutionBinding) -> tuple[str, str]:
    if binding.policy_cohort != "shadow":
        raise ValueError("shadow store requires shadow binding")
    parts = binding.state_namespace.removeprefix("shadow-")
    deployment, separator, parent = parts[:36], parts[36:37], parts[37:]
    try:
        if (separator != "-" or str(UUID(deployment)) != deployment
            or str(UUID(parent)) != parent or deployment != str(binding.deployment_id)
            or binding.state_namespace != f"shadow-{deployment}-{parent}"):
            raise ValueError("invalid shadow identity")
    except ValueError:
        raise ValueError("invalid server-derived shadow namespace") from None
    if binding.environment == "production":
        if binding.rehearsal_id is not None:
            raise ValueError("invalid production shadow rehearsal identity")
    elif binding.environment != "rehearsal" or not binding.rehearsal_id:
        raise ValueError("invalid shadow source environment")
    return deployment, parent


class ShadowStoreLock:
    def __init__(self, router, binding, fd):
        self.router, self.binding, self.fd = router, binding, fd

    def cleanup(self):
        if self.fd is None:
            raise ValueError("shadow cleanup requires live filesystem lock")
        path = self.router._path(self.binding, create=False)
        if path.parent.exists():
            shutil.rmtree(path.parent)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
            self.router._locks.pop(self.binding.state_namespace, None)


class ShadowStoreRouter:
    """Server-only capability. Lock inode lives outside the disposable store."""
    def __init__(self, rehearsal_root: str | Path):
        self.root = Path(rehearsal_root).absolute()
        self._locks = {}

    def assert_locked(self, binding):
        lock = self._locks.get(binding.state_namespace)
        if lock is None or lock.fd is None:
            raise ValueError("shadow execution requires filesystem lock")

    def _checked(self, parts, *, directory=True, create=True):
        current = self.root
        if current.is_symlink() or current.resolve() != current:
            raise ValueError("shadow root must be canonical and not a symlink")
        if create:
            current.mkdir(mode=0o700, parents=True, exist_ok=True)
        for index, part in enumerate(parts):
            current = current / part
            if current.is_symlink():
                raise ValueError("shadow store symlink forbidden")
            if create and (directory or index < len(parts) - 1):
                current.mkdir(mode=0o700, exist_ok=True)
        if not current.resolve().is_relative_to(self.root):
            raise ValueError("shadow store escapes configured root")
        return current

    def _path(self, binding, *, create):
        deployment, parent = validate_shadow_binding(binding)
        return self._checked(
            ["shadow", deployment, parent, "harness.sqlite3"],
            directory=False, create=create,
        )

    def path_for(self, binding):
        return self._path(binding, create=True)

    def try_lock(self, binding):
        deployment, parent = validate_shadow_binding(binding)
        path = self._checked([".locks", f"{deployment}-{parent}.lock"], directory=False)
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return None
        except BaseException:
            os.close(fd)
            raise
        lock = ShadowStoreLock(self, binding, fd)
        self._locks[binding.state_namespace] = lock
        return lock
