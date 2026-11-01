import copy
import json
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from pydantic import SecretStr
from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
import uvicorn

from api.distributed_main import create_app
from core.distributed.ops_queries import OpsQueries
from core.distributed.policy_health import PolicyHealthEvaluator
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyDeploymentRecord, PolicyGateReceiptRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from tests.distributed.conftest import raw_repo
from tests.distributed.test_policy_health import health_repo, admitted, fill_window, NOW

OWN = Path("/tmp/m3-task9-spec-independent")
inner = create_app()


@asynccontextmanager
async def lifespan(app):
    raw = raw_repo.__wrapped__()
    repository = await anext(raw)
    try:
        fixture = await health_repo.__wrapped__(repository)
        repo, promotion, deployment = fixture
        old_run, _ = await admitted(fixture, "spec-live-old", cohort="candidate")
        await fill_window(fixture, changes={
            "commit_outcome": "failed", "terminal_status": "commit_failed",
        })
        window = await PolicyHealthEvaluator(promotion).evaluate(deployment.deployment_id)
        assert window.decision == "fail"
        head = await promotion.get_head("rehearsal")
        assert head.state.value == "rolled_back"
        async with repo.session_factory() as s:
            rolled = await s.get(PolicyDeploymentRecord, str(head.deployment_id))
        new_run, _ = await admitted((repo, promotion, rolled), "spec-live-new", cohort="stable")
        async with repo.session_factory() as s, s.begin():
            for version in range(4, 57):
                s.add(PolicyDeploymentRecord(
                    **{c.name: copy.deepcopy(getattr(deployment, c.name))
                       for c in deployment.__table__.columns
                       if c.name not in {"deployment_id", "version", "command_id", "state", "traffic_basis_points"}},
                    deployment_id=str(uuid4()), version=version, state="registered",
                    traffic_basis_points=0, command_id=f"spec-live-{version}",
                ))
            if os.environ.get("SPEC_GATE_TIE") == "1":
                artifact = await s.get(PolicyArtifactRecord, old_run.effective_policy_hash)
                for receipt_id, status, created_at, evidence in [
                    ("ffffffff-ffff-ffff-ffff-ffffffffffff", "passed", NOW, "7" * 64),
                    ("00000000-0000-0000-0000-000000000001", "failed", NOW + timedelta(seconds=60), "8" * 64),
                ]:
                    s.add(PolicyGateReceiptRecord(
                        receipt_id=receipt_id, policy_hash=artifact.policy_hash,
                        gate_type="formal_holdout", status=status, evidence_hash=evidence,
                        protocol_hash=artifact.protocol_hash, runtime_hash=artifact.runtime_hash,
                        source_revision=artifact.source_revision, model_identity="test-fixture",
                        data_role="holdout_validated", sample_count=20, cost=Decimal(".1"),
                        details={"evidence_role": "test_fixture", "release_eligible": False},
                        issuer="test-fixture", issued_at=NOW, created_at=created_at,
                    ))
        if os.environ.get("SPEC_GATE_TIE") == "1":
            async with repo.session_factory() as s:
                artifact = await s.get(PolicyArtifactRecord, old_run.effective_policy_hash)
                missing, rows = await PromotionRepository._bound_gate_receipts(
                    s, artifact=artifact, required={"formal_holdout"}, health_bindings={},
                )
                assert missing == ["formal_holdout"] and rows == {}
                print("AUTHORITATIVE_GATE_REJECTS_NEWER_FAILED_RECEIPT", flush=True)
        inner.state.distributed = SimpleNamespace(
            repository=repo, ops_queries=OpsQueries(repo.session_factory),
            settings=SimpleNamespace(ops_api_token=SecretStr("")),
        )
        (OWN / "live-fixture.json").write_text(json.dumps({
            "evidence_role": "test_fixture", "release_eligible": False,
            "old_run_id": old_run.id, "new_run_id": new_run.id,
            "old_deployment_id": deployment.deployment_id,
            "current_deployment_id": str(head.deployment_id),
            "old_policy_hash": old_run.effective_policy_hash,
            "new_policy_hash": new_run.effective_policy_hash,
            "window_id": window.window_id,
        }, indent=2))
        yield
    finally:
        await anext(raw, None)


app = Starlette(lifespan=lifespan, routes=[
    Mount("/ops-api", app=inner),
    Mount("/", app=StaticFiles(directory=str(OWN / "frontend/dist"), html=True)),
])

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=3001)
