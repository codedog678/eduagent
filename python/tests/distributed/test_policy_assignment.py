import asyncio
import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text

from core.distributed.policy_assignment import (
    ArtifactUnavailable, InvalidRehearsalToken, PolicyAssigner,
    RehearsalTokenConflict, assignment_bucket, select_cohort,
)
from core.distributed.models import DistributedLease, DistributedOutbox, DistributedRun
from core.distributed.promotion_contracts import RehearsalClaims
from core.distributed.promotion_models import (
    PolicyArtifactRecord, PolicyAuditEventRecord, PolicyDeploymentRecord,
    PolicyEnvironmentHeadRecord, RehearsalTokenNonceRecord,
)
from core.distributed.promotion_repository import PromotionRepository
from core.distributed.runtime import (
    BUILTIN_POLICY_HASH, REHEARSAL_DEPLOYMENT_ID, upgrade_m3_schema,
)
from core.policy_store import artifact, builtin_components
from tests.distributed.helpers import spec

NOW = datetime(2026, 11, 1, tzinfo=UTC)
SECRET = b"a" * 32


def signed(values):
    body = json.dumps(values, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode()
    encode = lambda value: base64.urlsafe_b64encode(value).decode().rstrip("=")
    return encode(body) + "." + encode(hmac.digest(SECRET, body, "sha256"))


def claims(request_id="r1", **changes):
    values = RehearsalClaims(
        rehearsal_id="demo", namespace="rehearsal-demo",
        deployment_id=REHEARSAL_DEPLOYMENT_ID, deployment_version=1,
        learner_id="student", request_id=request_id, operations=["learning_task"],
        nonce="nonce-1", issued_at=NOW, expires_at=NOW + timedelta(minutes=5),
    ).model_dump(mode="json")
    return {**values, **changes}


def assigner(**kwargs):
    return PolicyAssigner(signing_secret=SECRET, assignment_secret=SECRET, **kwargs)


def test_hmac_fixed_vector_and_boundary():
    bucket = assignment_bucket(secret=SECRET, environment="rehearsal",
        deployment_id="11111111-1111-1111-1111-111111111111",
        learner_id="student", request_id="request-1")
    assert bucket == 4512
    assert select_cohort("canary", 4513, bucket) == "candidate"
    assert select_cohort("canary", 4512, bucket) == "stable"
    for state in ("registered", "shadow", "frozen", "rolled_back"):
        assert select_cohort(state, 10000, 0) == "stable"
    assert select_cohort("active", 10000, 9999) == "candidate"


def test_valid_canonical_claims_and_secret_length():
    assert assigner().verify(signed(claims()), spec(), NOW).namespace == "rehearsal-demo"
    with pytest.raises(ValueError):
        PolicyAssigner(signing_secret=b"short", assignment_secret=SECRET)


@pytest.mark.parametrize("changes", [
    {"issued_at": (NOW + timedelta(seconds=1)).isoformat()},
    {"learner_id": "other"}, {"request_id": "other"},
    {"operations": ["delete"]}, {"namespace": "rehearsal-other"},
    {"fault_profile": "unknown"}, {"fault_profile": "latency"},
])
def test_invalid_signed_claims_fail_closed(changes):
    with pytest.raises(InvalidRehearsalToken):
        assigner().verify(signed(claims(**changes)), spec(), NOW)


def test_expired_and_tampered_tokens():
    with pytest.raises(RehearsalTokenConflict):
        assigner().verify(signed(claims(expires_at=NOW.isoformat(),
            issued_at=(NOW - timedelta(minutes=1)).isoformat())), spec(), NOW)
    token = signed(claims())
    with pytest.raises(InvalidRehearsalToken):
        assigner().verify(token[:-2] + "xx", spec(), NOW)


@pytest.fixture
async def assignment_repo(repo):
    async with repo.session_factory.kw["bind"].begin() as conn:
        await upgrade_m3_schema(conn)
    repo.policy_assigner = assigner(allow_fault_injection=True)
    # Unit fixtures intentionally inject identities; production defaults must verify real ones.
    repo.policy_assigner.runtime_hash = "f" * 64
    repo.policy_assigner.source_revision = "test-source"
    repo._db_now = lambda session: asyncio.sleep(0, result=NOW)
    return repo


async def candidate_head(repo, *, state="active", traffic=10000, version=2):
    value = artifact({"retrieval_rules": "qualified retrieval"},
        parent=BUILTIN_POLICY_HASH, protocol="b" * 64, runtime="f" * 64,
        source="test-source", proposer="c" * 64, evidence={})
    async with repo.session_factory() as session, session.begin():
        if await session.get(PolicyArtifactRecord, value["policy_hash"]) is None:
            session.add(PolicyArtifactRecord(**{
                key: value[key] for key in ("policy_hash", "parent_policy_hash",
                "components", "fixed_components_hash", "runtime_hash", "source_revision",
                "protocol_hash", "proposer_hash", "data_role")},
                evidence_bindings=value["evidence_paths"],
                created_at=datetime.fromisoformat(value["created_at"])))
            await session.flush()
        old = await session.get(PolicyDeploymentRecord, REHEARSAL_DEPLOYMENT_ID)
        row = PolicyDeploymentRecord(deployment_id=str(uuid4()), environment="rehearsal",
            version=version, state=state, candidate_policy_hash=value["policy_hash"],
            stable_policy_hash=BUILTIN_POLICY_HASH, previous_stable_deployment_id=old.deployment_id,
            traffic_basis_points=traffic, assignment_salt_id="test", thresholds=old.thresholds,
            thresholds_hash=old.thresholds_hash, required_receipts=[], command_id=f"test-{version}",
            reason="test", actor="test", created_at=NOW)
        session.add(row)
        await session.flush()
        head = await session.get(PolicyEnvironmentHeadRecord, "rehearsal")
        head.current_deployment_id, head.current_version = row.deployment_id, version
        return row


def token_for(row, request_id="r1", **changes):
    return signed(claims(request_id, deployment_id=row.deployment_id,
                         deployment_version=row.version, **changes))


async def count(repo, model):
    async with repo.session_factory() as session:
        return await session.scalar(select(func.count()).select_from(model))


async def test_normal_admission_pins_builtin_and_claim(assignment_repo):
    repo = assignment_repo
    await candidate_head(repo)
    run, replay = await repo.accept_with_replay(spec())
    assert not replay
    assert run.policy_binding["environment"] == "production"
    assert run.effective_policy_hash == BUILTIN_POLICY_HASH
    assert run.policy_binding["components"] == builtin_components()
    claim = await repo.claim(run.id, "worker", 30)
    assert claim.policy_binding.model_dump(mode="json") == run.policy_binding
    assert await count(repo, RehearsalTokenNonceRecord) == 0


async def test_replay_and_takeover_copy_byte_exact_binding(assignment_repo):
    repo = assignment_repo
    row = await candidate_head(repo)
    run, _ = await repo.accept_with_replay(spec(), rehearsal_token=token_for(row, fault_profile="latency"))
    frozen = json.dumps(run.policy_binding, sort_keys=True)
    assert run.policy_cohort == "candidate"
    assert run.rehearsal_fault_profile == "latency"
    await candidate_head(repo, state="frozen", traffic=0, version=3)
    replay, hit = await repo.accept_with_replay(spec(), rehearsal_token="ignored-second-token")
    assert hit and json.dumps(replay.policy_binding, sort_keys=True) == frozen
    claim = await repo.claim(run.id, "worker", 30)
    assert json.dumps(claim.policy_binding.model_dump(mode="json"), sort_keys=True) == frozen
    await repo.fail(run.id, claim.fencing_token, "retry", retryable=True)
    retry = await repo.claim(run.id, "worker-2", 30)
    assert retry.policy_binding == claim.policy_binding
    assert await count(repo, RehearsalTokenNonceRecord) == 1
    async with repo.session_factory() as session:
        nonce = await session.scalar(select(RehearsalTokenNonceRecord))
        assert nonce.nonce_digest == hashlib.sha256(b"nonce-1").hexdigest()
        assert nonce.consumed_at == NOW
        topics = list(await session.scalars(select(DistributedOutbox.topic)))
        assert "run.rehearsal.accepted" in topics and "run.rehearsal.retry" in topics
        assert "run.retry" not in topics


async def test_concurrent_admission_consumes_one_nonce(assignment_repo):
    repo = assignment_repo
    row = await candidate_head(repo)
    results = await asyncio.gather(*(repo.accept_with_replay(spec(),
        rehearsal_token=token_for(row, nonce=f"nonce-{i}")) for i in range(8)))
    assert len({run.id for run, _ in results}) == 1
    assert sum(not replay for _, replay in results) == 1
    assert await count(repo, DistributedRun) == await count(repo, RehearsalTokenNonceRecord) == 1


async def test_nonce_replay_and_stale_version_leave_no_partial_run(assignment_repo):
    repo = assignment_repo
    row = await candidate_head(repo)
    await repo.accept_with_replay(spec(), rehearsal_token=token_for(row))
    with pytest.raises(RehearsalTokenConflict):
        await repo.accept_with_replay(spec("r2"), rehearsal_token=token_for(row, "r2"))
    await candidate_head(repo, state="frozen", traffic=0, version=3)
    with pytest.raises(InvalidRehearsalToken):
        await repo.accept_with_replay(spec("r3"), rehearsal_token=token_for(row, "r3", nonce="fresh"))
    assert await count(repo, DistributedRun) == await count(repo, RehearsalTokenNonceRecord) == 1


async def test_stable_clears_signed_fault_profile(assignment_repo):
    repo = assignment_repo
    row = await candidate_head(repo, state="shadow", traffic=0)
    run, _ = await repo.accept_with_replay(spec(), rehearsal_token=token_for(row, fault_profile="commit_failure"))
    assert run.state_namespace == "rehearsal-demo"
    assert run.policy_cohort == "stable" and run.rehearsal_fault_profile == "none"


@pytest.mark.parametrize("failure", ["missing", "tamper", "runtime", "source", "fixed", "legacy"])
async def test_bad_artifact_freezes_durably_without_run_or_nonce(assignment_repo, monkeypatch, failure):
    repo = assignment_repo
    row = await candidate_head(repo)
    if failure == "missing":
        monkeypatch.setattr(repo.policy_assigner, "load_artifact", lambda *args: asyncio.sleep(0, result=None))
    elif failure == "runtime":
        repo.policy_assigner.runtime_hash = "e" * 64
    elif failure == "source":
        repo.policy_assigner.source_revision = "wrong-source"
    else:
        async with repo.session_factory() as session, session.begin():
            await session.execute(text("ALTER TABLE policy_artifacts DISABLE TRIGGER USER"))
            item = await session.get(PolicyArtifactRecord, row.candidate_policy_hash)
            if failure == "tamper":
                item.components = {"retrieval_rules": "tampered"}
            elif failure == "fixed":
                item.fixed_components_hash = "e" * 64
            else:
                item.data_role = "legacy"
            await session.flush()
            await session.execute(text("ALTER TABLE policy_artifacts ENABLE TRIGGER USER"))
    with pytest.raises(ArtifactUnavailable):
        await repo.accept_with_replay(spec(), rehearsal_token=token_for(row))
    async with repo.session_factory() as session:
        head = await session.get(PolicyEnvironmentHeadRecord, "rehearsal")
        frozen = await session.get(PolicyDeploymentRecord, head.current_deployment_id)
        assert frozen.state == "frozen" and frozen.version == row.version + 1
    assert await count(repo, DistributedRun) == await count(repo, DistributedLease) == 0
    assert await count(repo, RehearsalTokenNonceRecord) == 0
    promotion = PromotionRepository(repo.session_factory)
    async with repo.session_factory() as session, session.begin():
        assert not await promotion.freeze_if_current(session, row.deployment_id, row.version)
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyAuditEventRecord)
            .where(PolicyAuditEventRecord.event_type == "admission_artifact_rejected")) == 1
        topics = list(await session.scalars(select(DistributedOutbox.topic)))
        assert topics == ["policy.deployment.changed"]


async def test_freeze_cannot_change_newer_head(assignment_repo):
    repo = assignment_repo
    old = await candidate_head(repo)
    newer = await candidate_head(repo, version=3)
    promotion = PromotionRepository(repo.session_factory)
    async with repo.session_factory() as session, session.begin():
        assert not await promotion.freeze_if_current(session, old.deployment_id, old.version)
    async with repo.session_factory() as session:
        head = await session.get(PolicyEnvironmentHeadRecord, "rehearsal")
        assert head.current_deployment_id == newer.deployment_id


async def test_binding_json_is_immutable_in_database(assignment_repo):
    from sqlalchemy.exc import DBAPIError
    repo = assignment_repo
    run = await repo.accept(spec())
    with pytest.raises(DBAPIError, match="immutable"):
        async with repo.session_factory() as session, session.begin():
            await session.execute(text("UPDATE distributed_runs SET policy_binding = '{}' WHERE id = :id"), {"id": run.id})


async def test_dispatch_routes_rehearsal_retry_and_deployment_events(assignment_repo, broker):
    from core.distributed.broker import RedisStreamBroker
    from core.distributed.dispatcher import OutboxDispatcher
    from core.distributed.telemetry import DurableTracer
    repo = assignment_repo
    rehearsal = RedisStreamBroker(broker.redis, broker.stream + ":rehearsal", "rehearsal")
    control = RedisStreamBroker(broker.redis, broker.stream + ":control", "control")
    row = await candidate_head(repo)
    run = await repo.accept(spec("prod"))
    candidate, _ = await repo.accept_with_replay(spec("candidate"), rehearsal_token=token_for(row, "candidate"))
    claim = await repo.claim(candidate.id, "worker", 30)
    await repo.fail(candidate.id, claim.fencing_token, "retry", retryable=True)
    async with repo.session_factory() as session, session.begin():
        await PromotionRepository(repo.session_factory).freeze_if_current(session, row.deployment_id, row.version)
        session.add(DistributedOutbox(event_key="future-topic", topic="future.unhandled",
            payload={}, created_at=NOW, publish_attempts=0))
    dispatcher = OutboxDispatcher(repo, broker, tracer=DurableTracer(repo),
        rehearsal_broker=rehearsal, deployment_broker=control)
    try:
        assert await dispatcher.dispatch_once() == 4
        assert await dispatcher.dispatch_once() == 0
        prod_messages = await broker.read("prod", 10, 10)
        rehearsal_messages = await rehearsal.read("rehearsal", 10, 10)
        control_messages = await control.read("control", 10, 10)
        assert [item.payload["run_id"] for item in prod_messages] == [run.id]
        assert [item.payload["run_id"] for item in rehearsal_messages] == [candidate.id, candidate.id]
        assert len(control_messages) == 1 and "run_id" not in control_messages[0].payload
        async with repo.session_factory() as session:
            pending = list(await session.scalars(select(DistributedOutbox).where(DistributedOutbox.published_at.is_(None))))
            assert [item.topic for item in pending] == ["future.unhandled"]
            assert pending[0].publish_attempts == 0
    finally:
        await rehearsal.reset_for_tests()
        await control.reset_for_tests()


async def test_unconfigured_rehearsal_route_stays_pending(assignment_repo, broker):
    from core.distributed.dispatcher import OutboxDispatcher
    repo = assignment_repo
    row = await candidate_head(repo)
    await repo.accept_with_replay(spec(), rehearsal_token=token_for(row))
    assert await OutboxDispatcher(repo, broker).dispatch_once() == 0
    async with repo.session_factory() as session:
        pending = await session.scalar(select(DistributedOutbox))
        assert pending.published_at is None and pending.publish_attempts == 0


async def test_api_valid_token_replay_and_error_mapping(assignment_repo):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from types import SimpleNamespace
    from api.distributed_routes import router
    from core.distributed.metrics import DistributedMetrics
    repo = assignment_repo
    row = await candidate_head(repo)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.distributed = SimpleNamespace(repository=repo, metrics=DistributedMetrics())
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        async def post(request_id, token, question="复习"):
            return await client.post("/api/distributed/runs", json=spec(request_id, question).model_dump(mode="json"),
                headers={"X-EduAgent-Rehearsal": token})
        first = await post("r1", token_for(row))
        assert first.status_code == 202 and first.json()["policy_binding"]["environment"] == "rehearsal"
        replay = await post("r1", "invalid-but-ignored-on-replay")
        assert replay.json() == first.json()
        assert (await post("r1", "invalid", "different")).status_code == 409
        assert (await post("r2", token_for(row, "r2"))).status_code == 409
        expired = token_for(row, "r3", issued_at=(NOW-timedelta(seconds=60)).isoformat(), expires_at=NOW.isoformat())
        assert (await post("r3", expired)).status_code == 409
        assert (await post("r4", "invalid")).status_code == 401
        repo.policy_assigner.runtime_hash = "e" * 64
        response = await post("r5", token_for(row, "r5", nonce="fresh"))
        assert response.status_code == 503 and "fresh" not in response.text


async def test_claim_components_ignore_changed_artifact_and_repeated_upgrade(assignment_repo):
    repo = assignment_repo
    row = await candidate_head(repo)
    run, _ = await repo.accept_with_replay(spec(), rehearsal_token=token_for(row))
    original = json.dumps(run.policy_binding, sort_keys=True)
    async with repo.session_factory() as session, session.begin():
        await session.execute(text("ALTER TABLE policy_artifacts DISABLE TRIGGER USER"))
        item = await session.get(PolicyArtifactRecord, row.candidate_policy_hash)
        item.components = {"retrieval_rules": "changed after admission"}
        await session.flush()
        await session.execute(text("ALTER TABLE policy_artifacts ENABLE TRIGGER USER"))
    async with repo.session_factory.kw["bind"].begin() as connection:
        await upgrade_m3_schema(connection)
        await upgrade_m3_schema(connection)
    claim = await repo.claim(run.id, "worker", 30)
    assert json.dumps(claim.policy_binding.model_dump(mode="json"), sort_keys=True) == original
    await repo.force_lease_expiry(run.id, NOW - timedelta(seconds=1))
    await repo.requeue_expired(NOW)
    takeover = await repo.claim(run.id, "worker-2", 30)
    assert takeover.policy_binding == claim.policy_binding
    async with repo.session_factory() as session:
        assert "run.rehearsal.retry" in list(await session.scalars(select(DistributedOutbox.topic)))


@pytest.mark.parametrize("column,value", [
    ("deployment_id", REHEARSAL_DEPLOYMENT_ID),
    ("effective_policy_hash", "a" * 64), ("policy_cohort", "candidate"),
    ("assignment_key_hash", "e" * 64), ("assignment_reason", "changed"),
    ("state_namespace", "rehearsal-other"), ("rehearsal_id", "other"),
    ("rehearsal_fault_profile", "latency"),
])
async def test_all_assignment_columns_are_immutable(assignment_repo, column, value):
    from sqlalchemy.exc import DBAPIError
    repo = assignment_repo
    run = await repo.accept(spec())
    with pytest.raises(DBAPIError, match="immutable"):
        async with repo.session_factory() as session, session.begin():
            await session.execute(text(f"UPDATE distributed_runs SET {column} = :value WHERE id = :id"),
                {"id": run.id, "value": value})


async def test_builtin_special_hash_requires_exact_builtin_material(assignment_repo):
    repo = assignment_repo
    async with repo.session_factory() as session, session.begin():
        await session.execute(text("ALTER TABLE policy_artifacts DISABLE TRIGGER USER"))
        item = await session.get(PolicyArtifactRecord, BUILTIN_POLICY_HASH)
        item.components = {"retrieval_rules": "tampered builtin"}
        await session.flush()
        await session.execute(text("ALTER TABLE policy_artifacts ENABLE TRIGGER USER"))
    with pytest.raises(ArtifactUnavailable):
        await repo.accept(spec())
    assert await count(repo, DistributedRun) == 0
    async with repo.session_factory() as session:
        head = await session.get(PolicyEnvironmentHeadRecord, "production")
        deployment = await session.get(PolicyDeploymentRecord, head.current_deployment_id)
        assert deployment.state == "frozen"


@pytest.mark.parametrize("iteration", range(12))
async def test_concurrent_bad_admissions_freeze_exactly_once(assignment_repo, iteration):
    repo = assignment_repo
    row = await candidate_head(repo)
    repo.policy_assigner.runtime_hash = "e" * 64
    results = await asyncio.gather(*(repo.accept_with_replay(spec(f"bad-{i}"),
        rehearsal_token=token_for(row, f"bad-{i}", nonce=f"nonce-{i}")) for i in range(8)),
        return_exceptions=True)
    assert all(isinstance(result, (ArtifactUnavailable, InvalidRehearsalToken)) for result in results), [(type(result).__name__, getattr(getattr(result, "orig", None), "sqlstate", None)) for result in results]
    async with repo.session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(PolicyAuditEventRecord)
            .where(PolicyAuditEventRecord.event_type == "admission_artifact_rejected")) == 1
    assert await count(repo, DistributedRun) == await count(repo, RehearsalTokenNonceRecord) == 0


async def test_default_production_validator_rejects_arbitrary_runtime(assignment_repo):
    repo = assignment_repo
    row = await candidate_head(repo)
    repo.policy_assigner.runtime_hash = None
    repo.policy_assigner.source_revision = None
    with pytest.raises(ArtifactUnavailable):
        await repo.accept_with_replay(spec(), rehearsal_token=token_for(row))
    assert await count(repo, DistributedRun) == 0


async def test_token_issuer_interoperates_without_exposing_nonce_in_binding(assignment_repo):
    from core.distributed.promotion_service import RehearsalTokenIssuer
    repo = assignment_repo
    row = await candidate_head(repo)
    issued = await RehearsalTokenIssuer(PromotionRepository(repo.session_factory),
        signing_secret="a" * 32, assignment_secret="a" * 32, clock=lambda: NOW).issue(
        rehearsal_id="demo", namespace="rehearsal-demo", learner_id="student", request_id="r1",
        operation="learning_task", fault_profile="none", ttl_seconds=300)
    run, _ = await repo.accept_with_replay(spec(), rehearsal_token=issued["token"])
    assert run.policy_cohort == issued["expected_cohort"] == "candidate"
    assert "nonce" not in json.dumps(run.policy_binding)
    assert issued["token"] not in json.dumps(run.public_dict())


async def test_actual_unreachable_postgres_is_503_not_cached_admission(assignment_repo):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from types import SimpleNamespace
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from api.distributed_routes import router
    from core.distributed.repository import DistributedRunRepository
    from core.distributed.metrics import DistributedMetrics
    repo = assignment_repo
    # Warm the real production binding first; an unavailable DB still cannot admit.
    await repo.accept(spec("warm"))
    engine = create_async_engine("postgresql+asyncpg://postgres@127.0.0.1:1/unreachable", connect_args={"timeout": 1})
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.distributed = SimpleNamespace(repository=DistributedRunRepository(
        async_sessionmaker(engine, expire_on_commit=False), policy_assigner=repo.policy_assigner), metrics=DistributedMetrics())
    try:
        async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
            response = await client.post("/api/distributed/runs", json=spec("unavailable").model_dump(mode="json"))
        assert response.status_code == 503
        assert "unreachable" not in response.text and "postgres" not in response.text
        assert await count(repo, DistributedRun) == 1
    finally:
        await engine.dispose()


async def test_legacy_builtin_backfill_frozen_but_unknown_hash_cannot_claim(assignment_repo):
    from core.distributed.runtime import PRODUCTION_DEPLOYMENT_ID
    repo = assignment_repo
    now = NOW
    async with repo.session_factory() as session, session.begin():
        for key, policy_hash in (("old-builtin", BUILTIN_POLICY_HASH), ("old-unknown", "a" * 64)):
            session.add(DistributedRun(id=str(uuid4()), learner_id="student", request_id=key,
                operation="learning_task", input_hash="f" * 64, payload=spec(key).payload.model_dump(mode="json"),
                status="accepted", trace_id="a" * 32, attempt_count=0, created_at=now, updated_at=now,
                deployment_id=PRODUCTION_DEPLOYMENT_ID, effective_policy_hash=policy_hash,
                policy_cohort="stable", assignment_key_hash="f" * 64, assignment_reason="legacy_backfill",
                state_namespace="production", rehearsal_fault_profile="none"))
    async with repo.session_factory.kw["bind"].begin() as connection:
        await upgrade_m3_schema(connection)
    builtin = await repo.get_by_request("student", "old-builtin")
    unknown = await repo.get_by_request("student", "old-unknown")
    assert builtin.policy_binding["components"] == builtin_components()
    assert builtin.assignment_reason == "legacy_backfill"
    # Supply leases to model pre-M3 admitted Runs.
    async with repo.session_factory() as session, session.begin():
        for run in (builtin, unknown):
            session.add(DistributedLease(run_id=run.id, owner=None, fencing_token=0, updated_at=now))
    assert (await repo.claim(builtin.id, "worker", 30)).policy_binding.components.model_dump() == builtin_components()
    with pytest.raises(ArtifactUnavailable):
        await repo.claim(unknown.id, "worker", 30)


async def test_public_api_projects_binding_without_artifact_components(assignment_repo):
    from fastapi import FastAPI
    from httpx import ASGITransport, AsyncClient
    from types import SimpleNamespace
    from api.distributed_routes import router
    from core.distributed.metrics import DistributedMetrics
    repo = assignment_repo
    row = await candidate_head(repo)
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.distributed = SimpleNamespace(repository=repo, metrics=DistributedMetrics())
    public_fields = {"deployment_id", "environment", "effective_policy_hash", "policy_cohort",
                     "state_namespace", "rehearsal_id", "rehearsal_fault_profile"}
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        accepted = await client.post("/api/distributed/runs", json=spec().model_dump(mode="json"),
            headers={"X-EduAgent-Rehearsal": token_for(row)})
        assert accepted.status_code == 202
        assert set(accepted.json()["policy_binding"]) == public_fields
        assert "retrieval_rules" not in accepted.text
        status = await client.get(accepted.json()["status_url"])
        cancelled = await client.post(accepted.json()["status_url"] + "/cancel")
        for response in (status, cancelled):
            assert set(response.json()["policy_binding"]) == public_fields
            assert "components" not in response.text and "qualified retrieval" not in response.text
        run = await repo.get(accepted.json()["run_id"])
        assert run.policy_binding["components"] == {"retrieval_rules": "qualified retrieval"}
