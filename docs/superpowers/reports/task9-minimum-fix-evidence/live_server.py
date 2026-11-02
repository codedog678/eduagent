from contextlib import asynccontextmanager
from pathlib import Path
import json
import os
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
import uvicorn

from api.distributed_main import create_app
from core.distributed.ops_queries import OpsQueries
from core.distributed.repository import DistributedRunRepository
from core.distributed.runtime import migrate_schema
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.test_policy_assignment import assigner
from tests.distributed.test_policy_health import candidate_head
from tests.distributed.test_ops_health_binding import health_pair
from test_spec_relations import synthetic_active
from test_spec_corroboration import genuine_malformed_latest
from tests.distributed.test_policy_health_corrections import real_active_fixture
from test_independent_integrity import transition_fixture
from test_minimum_evidence import minimum_fixture
import safety

safety.pytest_configure(None)

OWN = Path(__file__).parent
SCENARIO = os.environ["SPEC_SCENARIO"]
engine = create_async_engine(os.environ["DISTRIBUTED_TEST_DATABASE_URL"])
factory = async_sessionmaker(engine, expire_on_commit=False)
repo = DistributedRunRepository(factory)
queries = OpsQueries(factory)
api = create_app()
api.state.distributed = SimpleNamespace(
    ops_queries=queries, settings=SimpleNamespace(ops_api_token=""))


@asynccontextmanager
async def lifespan(app):
    await migrate_schema(engine)
    repo.policy_assigner = assigner(runtime_hash="f" * 64, source_revision="test-source")
    first = await candidate_head(repo, state="canary", traffic=5000)
    fixture = (repo, PromotionRepository(factory), first)
    public = {"role": "synthetic engineering; no model calls; no release qualification",
              "scenario": SCENARIO}
    if SCENARIO in {"current", "history", "history_visible"}:
        old, current, ow, cw, receipts = await health_pair(
            fixture, current_healthy=SCENARIO.startswith("history"))
        original = next(r for r in receipts if r.details["deployment_id"] == old.deployment_id)
        public.update(id=current.deployment_id if SCENARIO == "current" else old.deployment_id,
                      old=old.deployment_id, current=current.deployment_id,
                      old_receipt=original.receipt_id, old_window=ow.window_id,
                      current_window=cw.window_id, policy_hash=old.candidate_policy_hash)
    elif SCENARIO == "genuine_valid":
        _, _, _ = fixture
        prepared, _, _ = await real_active_fixture(fixture, command_prefix="production-genuine")
        _, _, active = prepared
        public.update(id=str(active.deployment_id), policy_hash=active.candidate_policy_hash)
    elif SCENARIO == "genuine_malformed_latest_valid":
        _, active, original, newer = await genuine_malformed_latest(fixture)
        public.update(id=str(active.deployment_id), policy_hash=active.candidate_policy_hash,
                      original_approval=original, newer_malformed_approval=newer)
    elif SCENARIO == "minimum_zero":
        _, active, proof = await minimum_fixture(fixture, 0, 0)
        public.update(id=str(active.deployment_id), policy_hash=active.candidate_policy_hash,
                      minimum_proof=proof)
    elif SCENARIO == "referenced_canary_poison":
        _, active, proof = await transition_fixture(fixture, "active", health_poison={"sample_count": 0})
        public.update(id=str(active.deployment_id), policy_hash=active.candidate_policy_hash, **proof)
    else:
        _, active, actual, stored = await synthetic_active(fixture, SCENARIO)
        public.update(id=active.deployment_id, policy_hash=active.candidate_policy_hash,
                      actual_command_hash=actual, stored_command_hash=stored)
    public["detail"] = (await queries.get_policy_deployment(public["id"])).model_dump(mode="json")
    with (OWN / f"live-fixture-{os.environ['EVIDENCE_RUN']}.json").open("x") as output:
        json.dump(public, output, indent=2)
        output.write("\n")
    yield
    await engine.dispose()


app = Starlette(lifespan=lifespan, routes=[
    Mount("/ops-api", app=api),
    Mount("/", app=StaticFiles(directory=OWN / "frontend/dist", html=True)),
])
uvicorn.run(app, host="127.0.0.1", port=61805, access_log=False)
