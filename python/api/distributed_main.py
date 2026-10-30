from __future__ import annotations

import os
import socket
from collections.abc import Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI

from api.distributed_routes import metrics_router, router
from api.ops_routes import router as ops_router
from core.distributed.runtime import DistributedRuntime, build_runtime

RuntimeFactory = Callable[[], DistributedRuntime]


def create_app(
    runtime_factory: RuntimeFactory = build_runtime,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime = runtime_factory()
        app.state.distributed = runtime
        try:
            await runtime.start()
            worker_id = f"{socket.gethostname()}:{os.getpid()}:api"
            async with runtime.worker_registry.process(
                worker_id=worker_id,
                instance_id=uuid4().hex,
                process_type="api",
                heartbeat_seconds=runtime.settings.distributed_heartbeat_seconds,
                capabilities=["ops-api", "run-api"],
            ):
                yield
        finally:
            await runtime.close()

    app = FastAPI(
        title="EduAgent Distributed Run Plane",
        lifespan=lifespan,
    )
    app.include_router(router, prefix="/api")
    app.include_router(ops_router)
    app.include_router(metrics_router)
    return app


app = create_app()
