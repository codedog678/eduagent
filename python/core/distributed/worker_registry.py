"""PostgreSQL-backed process registration and best-effort heartbeats."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .expert_models import DistributedWorkerRegistry
from .models import new_id


class WorkerRegistry:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    async def register(
        self,
        *,
        worker_id: str,
        instance_id: str,
        process_type: str,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DistributedWorkerRegistry:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            statement = (
                pg_insert(DistributedWorkerRegistry)
                .values(
                    id=new_id(),
                    worker_id=worker_id,
                    instance_id=instance_id,
                    process_type=process_type,
                    status="running",
                    current_run_id=None,
                    current_job_id=None,
                    capabilities=list(capabilities or []),
                    registry_metadata=dict(metadata or {}),
                    started_at=now,
                    last_heartbeat_at=now,
                    stopped_at=None,
                )
                .on_conflict_do_update(
                    index_elements=["worker_id", "instance_id"],
                    set_={
                        "process_type": process_type,
                        "status": "running",
                        "current_run_id": None,
                        "current_job_id": None,
                        "capabilities": list(capabilities or []),
                        "metadata": dict(metadata or {}),
                        "started_at": now,
                        "last_heartbeat_at": now,
                        "stopped_at": None,
                    },
                )
                .returning(DistributedWorkerRegistry)
            )
            return (await session.scalars(statement)).one()

    async def heartbeat(
        self,
        worker_id: str,
        instance_id: str,
    ) -> DistributedWorkerRegistry:
        return await self._update_identity(
            worker_id,
            instance_id,
            status="running",
            stopped_at=None,
            heartbeat=True,
        )

    async def assign(
        self,
        worker_id: str,
        instance_id: str,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> DistributedWorkerRegistry:
        return await self._update_identity(
            worker_id,
            instance_id,
            current_run_id=run_id,
            current_job_id=job_id,
            heartbeat=True,
        )

    async def clear_assignment(
        self,
        worker_id: str,
        instance_id: str,
    ) -> DistributedWorkerRegistry:
        return await self.assign(
            worker_id,
            instance_id,
            run_id=None,
            job_id=None,
        )

    async def stop(
        self,
        worker_id: str,
        instance_id: str,
    ) -> DistributedWorkerRegistry:
        async with self.session_factory() as session, session.begin():
            now = await self._db_now(session)
            statement = (
                update(DistributedWorkerRegistry)
                .where(
                    DistributedWorkerRegistry.worker_id == worker_id,
                    DistributedWorkerRegistry.instance_id == instance_id,
                )
                .values(
                    status="stopped",
                    current_run_id=None,
                    current_job_id=None,
                    last_heartbeat_at=now,
                    stopped_at=now,
                )
                .returning(DistributedWorkerRegistry)
            )
            row = (await session.scalars(statement)).one_or_none()
            if row is None:
                raise LookupError(
                    f"worker registry identity not found: "
                    f"{worker_id}/{instance_id}"
                )
            return row

    async def _update_identity(
        self,
        worker_id: str,
        instance_id: str,
        *,
        heartbeat: bool = False,
        **values,
    ) -> DistributedWorkerRegistry:
        async with self.session_factory() as session, session.begin():
            if heartbeat:
                values["last_heartbeat_at"] = await self._db_now(session)
            statement = (
                update(DistributedWorkerRegistry)
                .where(
                    DistributedWorkerRegistry.worker_id == worker_id,
                    DistributedWorkerRegistry.instance_id == instance_id,
                )
                .values(**values)
                .returning(DistributedWorkerRegistry)
            )
            row = (await session.scalars(statement)).one_or_none()
            if row is None:
                raise LookupError(
                    f"worker registry identity not found: "
                    f"{worker_id}/{instance_id}"
                )
            return row

    @staticmethod
    async def _db_now(session: AsyncSession) -> datetime:
        return await session.scalar(select(func.now()))

    @asynccontextmanager
    async def process(
        self,
        *,
        worker_id: str,
        instance_id: str,
        process_type: str,
        heartbeat_seconds: float,
        io_timeout_seconds: float = 1,
        capabilities: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[RegistryProcess]:
        process = RegistryProcess(
            registry=self,
            worker_id=worker_id,
            instance_id=instance_id,
            process_type=process_type,
            heartbeat_seconds=heartbeat_seconds,
            io_timeout_seconds=io_timeout_seconds,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )
        await process.start()
        try:
            yield process
        finally:
            await process.close()


@dataclass
class RegistryProcess:
    registry: WorkerRegistry
    worker_id: str
    instance_id: str
    process_type: str
    heartbeat_seconds: float
    capabilities: list[str]
    metadata: dict[str, Any]
    io_timeout_seconds: float = 1
    active: bool = False
    _heartbeat_task: asyncio.Task | None = None
    _desired_run_id: str | None = None
    _desired_job_id: str | None = None
    _assignment_dirty: bool = False
    _write_lock: asyncio.Lock = field(
        default_factory=asyncio.Lock,
        init=False,
        repr=False,
    )

    async def start(self) -> None:
        if self.io_timeout_seconds <= 0:
            raise ValueError("registry I/O timeout must be positive")
        await self._register_once()
        self._heartbeat_task = asyncio.create_task(self._heartbeat())

    async def assign(
        self,
        *,
        run_id: str | None = None,
        job_id: str | None = None,
    ) -> None:
        async with self._write_lock:
            self._desired_run_id = run_id
            self._desired_job_id = job_id
            self._assignment_dirty = True
            if not self.active:
                return
            try:
                await self._bounded(
                    self.registry.assign(
                        self.worker_id,
                        self.instance_id,
                        run_id=run_id,
                        job_id=job_id,
                    )
                )
            except Exception:
                return
            self._assignment_dirty = False

    async def clear_assignment(self) -> None:
        await self.assign(run_id=None, job_id=None)

    async def close(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._heartbeat_task
        async with self._write_lock:
            if self.active:
                with suppress(Exception):
                    await self._bounded(
                        self.registry.stop(
                            self.worker_id,
                            self.instance_id,
                        )
                    )
            self.active = False

    async def _heartbeat(self) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            async with self._write_lock:
                if not self.active:
                    await self._register_once()
                    continue
                try:
                    if self._assignment_dirty:
                        await self._bounded(
                            self.registry.assign(
                                self.worker_id,
                                self.instance_id,
                                run_id=self._desired_run_id,
                                job_id=self._desired_job_id,
                            )
                        )
                        self._assignment_dirty = False
                    else:
                        await self._bounded(
                            self.registry.heartbeat(
                                self.worker_id,
                                self.instance_id,
                            )
                        )
                except Exception:
                    self.active = False
                    self._assignment_dirty = True

    async def _register_once(self) -> None:
        try:
            await self._bounded(
                self.registry.register(
                    worker_id=self.worker_id,
                    instance_id=self.instance_id,
                    process_type=self.process_type,
                    capabilities=self.capabilities,
                    metadata=self.metadata,
                )
            )
        except Exception:
            self.active = False
            return
        self.active = True
        if self._desired_run_id is not None or self._desired_job_id is not None:
            self._assignment_dirty = True

    async def _bounded(self, operation):
        return await asyncio.wait_for(
            operation,
            timeout=self.io_timeout_seconds,
        )
