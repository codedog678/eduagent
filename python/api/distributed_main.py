from __future__ import annotations

from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.distributed_routes import metrics_router, router
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
            yield
        finally:
            await runtime.close()

    app = FastAPI(
        title="EduAgent Distributed Run Plane",
        lifespan=lifespan,
    )
    app.include_router(router, prefix="/api")
    app.include_router(metrics_router)
    return app


app = create_app()
