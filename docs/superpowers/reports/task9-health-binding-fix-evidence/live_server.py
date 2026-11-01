from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from types import SimpleNamespace

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
import uvicorn

from api.distributed_main import create_app
from core.distributed.ops_queries import OpsQueries
from core.distributed.repository import DistributedRunRepository
from core.distributed.runtime import migrate_schema
from tests.distributed.test_policy_assignment import assigner
from tests.distributed.test_policy_health import candidate_head
from tests.distributed.test_ops_health_binding import health_pair

OWN = Path(os.environ["REVIEW_OWN"])
engine = create_async_engine(os.environ["DISTRIBUTED_TEST_DATABASE_URL"])
factory = async_sessionmaker(engine, expire_on_commit=False)
repo = DistributedRunRepository(factory)
queries = OpsQueries(factory)
api = create_app()
api.state.distributed = SimpleNamespace(
    repository=repo, ops_queries=queries,
    settings=SimpleNamespace(ops_api_token=SecretStr("")),
)


@asynccontextmanager
async def lifespan(app):
    await migrate_schema(engine)
    repo.policy_assigner = assigner(
        runtime_hash="f" * 64, source_revision="test-source", allow_fault_injection=True,
        settings_obj=SimpleNamespace(promotion_injected_latency_seconds=.05),
    )
    from core.distributed.promotion_repository import PromotionRepository
    public = {"role": "synthetic; release_eligible=false; no model execution", "scenarios": {}}
    selected = os.environ.get("LIVE_SCENARIO", "both")
    for name, healthy in (("current", False), ("history", True)):
        if selected != "both" and selected != name:
            continue
        first = await candidate_head(repo, state="canary", traffic=5000)
        old, current, old_window, current_window, receipts = await health_pair(
            (repo, PromotionRepository(factory), first), current_healthy=healthy,
        )
        original = next(r for r in receipts if r.details["deployment_id"] == old.deployment_id)
        assert old.candidate_policy_hash == current.candidate_policy_hash
        public["scenarios"][name] = {
            "old": old.deployment_id, "current": current.deployment_id,
            "policy_hash": old.candidate_policy_hash,
            "old_window": old_window.window_id, "current_window": current_window.window_id,
            "old_receipt_id": original.receipt_id,
            "old_detail": (await queries.get_policy_deployment(old.deployment_id)).model_dump(mode="json"),
            "current_detail": (await queries.get_policy_deployment(current.deployment_id)).model_dump(mode="json"),
        }
    (OWN / f"live-fixture-{os.environ.get('LIVE_LABEL', 'initial')}.json").write_text(json.dumps(public, indent=2) + "\n")
    yield
    await engine.dispose()


app = Starlette(lifespan=lifespan, routes=[
    Mount("/ops-api", app=api),
    Mount("/", app=StaticFiles(directory=OWN / "frontend/dist", html=True)),
])
uvicorn.run(app, host="127.0.0.1", port=33521, access_log=False)
