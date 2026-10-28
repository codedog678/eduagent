"""全局模型额度、排队失败和取消语义；所有请求均使用注入的 mock。"""

import asyncio
import json
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from api.orchestrator import AgentOrchestrator
from api.routes import router
from config.settings import Settings, settings
from core.concurrency import ModelLimiter, QueueTimeout, get_model_limiter, model_slot
from core.harness import LearningHarness
from core.llm_service import LLMService
from core.memory_retrieval import MemoryRetrieval, SiliconFlowEmbedding
from core.run_context import RunContext, RunExhausted, active_run
from core.versions import config_fingerprint


def reply():
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason="stop",
                                 message=SimpleNamespace(content="ok", tool_calls=[]))],
        usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1))


def service(create, provider="openai"):
    result = LLMService(provider=provider, api_key="test-only")
    result._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        messages=SimpleNamespace(create=create))
    return result


@pytest.fixture
async def limiter(monkeypatch):
    item = ModelLimiter(2, .05)
    monkeypatch.setattr(asyncio.get_running_loop(), "_eduagent_model_limiter", item, raising=False)
    return item


@pytest.mark.asyncio
async def test_multiple_services_and_both_chat_paths_share_limit(limiter, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    two_entered, release = asyncio.Event(), asyncio.Event()
    calls, peak, active = 0, 0, 0

    async def create(**kwargs):
        nonlocal calls, peak, active
        calls += 1
        active += 1
        peak = max(peak, active)
        if active == 2:
            two_entered.set()
        try:
            await release.wait()
            return reply()
        finally:
            active -= 1

    services = [service(create) for _ in range(4)]
    tasks = [asyncio.create_task(s.generate("q") if i % 2 else
             s.tool_turn([{"role": "user", "content": "q"}], [], 10))
             for i, s in enumerate(services)]
    try:
        await asyncio.wait_for(two_entered.wait(), 1)
        assert calls == 2 and limiter.snapshot()["active"] == 2
        assert limiter.waiting == 2
        release.set()
        await asyncio.gather(*tasks)
        assert peak == 2 and calls == 4
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert limiter.active == limiter.waiting == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["generate", "tool_turn", "embedding", "rerank"])
async def test_queue_timeout_never_sends_request(path, limiter, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        return reply()

    cfg = Settings(_env_file=None, llm_provider="template", memory_embedding_api_key="test")
    embedding = SiliconFlowEmbedding(cfg, transport=httpx.MockTransport(
        lambda request: calls.append(request)))
    svc = service(create)
    retrieval = MemoryRetrieval(None, config=cfg, provider=embedding)
    operation = {
        "generate": lambda: svc.generate("q"),
        "tool_turn": lambda: svc.tool_turn([], [], 10),
        "embedding": lambda: embedding.embed(["q"]),
        "rerank": lambda: retrieval.rerank("q", ["r"], {"r": {"content": "text"}}),
    }[path]
    ctx = RunContext("alice", "run", "attempt", time.monotonic() + 5)
    token = active_run.set(ctx)
    try:
        async with limiter.slot("holder"), limiter.slot("holder"):
            with pytest.raises(QueueTimeout, match="model_queue_timeout"):
                await operation()
            assert not calls
            assert limiter.waiting == 0 and limiter.active == 2
    finally:
        active_run.reset(token)
    assert any(s["kind"] == "model_queue" and s["status"] == "timeout" for s in ctx.steps)
    assert limiter.queue_timeouts == 1 and limiter.active == 0


@pytest.mark.asyncio
async def test_embedding_request_occupies_same_global_slot(limiter):
    entered, release = asyncio.Event(), asyncio.Event()

    async def respond(request):
        entered.set()
        await release.wait()
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1, 2]}]})

    cfg = Settings(_env_file=None, llm_provider="template", memory_embedding_api_key="test")
    embedding = SiliconFlowEmbedding(cfg, transport=httpx.MockTransport(respond))
    async with limiter.slot("chat"):
        task = asyncio.create_task(embedding.embed(["q"]))
        try:
            await asyncio.wait_for(entered.wait(), 1)
            assert limiter.active == 2
            with pytest.raises(QueueTimeout):
                async with model_slot("chat"):
                    pytest.fail("third model request must not be admitted")
            release.set()
            assert await task == [[1, 2]]
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    assert limiter.active == limiter.waiting == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["queued", "inflight"])
async def test_cancel_releases_permit_and_waiter(limiter, phase):
    entered = asyncio.Event()

    async def request():
        async with limiter.slot("chat"):
            entered.set()
            await asyncio.Event().wait()

    async with limiter.slot("holder"):
        if phase == "queued":
            async with limiter.slot("holder"):
                task = asyncio.create_task(request())
                await asyncio.sleep(0)
                assert limiter.waiting == 1 and not entered.is_set()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert limiter.waiting == 0 and limiter.active == 2
        else:
            task = asyncio.create_task(request())
            await asyncio.wait_for(entered.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert limiter.active == 1
        async with limiter.slot("reused"):
            assert limiter.active == 2
    assert limiter.active == limiter.waiting == 0


@pytest.mark.asyncio
async def test_parent_deadline_precedes_model_queue_timeout(limiter):
    limiter.queue_timeout = 10
    async with limiter.slot("holder"), limiter.slot("holder"):
        ctx = RunContext("alice", "run", "attempt", time.monotonic() + .02)
        token = active_run.set(ctx)
        try:
            with pytest.raises(RunExhausted, match="deadline"):
                async with limiter.slot("chat"):
                    pytest.fail("deadline expired")
            assert limiter.waiting == 0
        finally:
            active_run.reset(token)


@pytest.mark.asyncio
async def test_model_queue_failure_rolls_back_and_retry_succeeds(tmp_path, limiter, monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    calls = []

    async def create(**kwargs):
        calls.append(kwargs)
        return reply()

    svc = service(create)
    orch = AgentOrchestrator()
    store = LearningHarness(orch, str(tmp_path / "queue.sqlite3"))
    orch.harness = store
    orch.get_learner_model_sync("alice")
    before = json.loads(json.dumps(store.capture("alice")))

    async def operation():
        orch.learner_models["alice"].metadata["changed"] = True
        response = await svc.generate("q")
        return {"text": response.content}, None

    try:
        async with limiter.slot("holder"), limiter.slot("holder"):
            with pytest.raises(HTTPException) as error:
                await store.run("alice", "retry", {}, operation)
            assert error.value.status_code == 503
            assert store.capture("alice") == before and not calls
            assert store.run_status("alice", "retry")["error"] == "model_queue_timeout"
        result = await store.run("alice", "retry", {}, operation)
        assert result["text"] == "ok" and len(calls) == 1
        assert store.db.execute("SELECT count(*) FROM run_attempts").fetchone()[0] == 2
    finally:
        store.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "anthropic"])
async def test_sdk_error_releases_global_slot(provider, limiter):
    async def create(**kwargs):
        raise RuntimeError("injected")

    with pytest.raises(RuntimeError, match="injected"):
        await service(create, provider).tool_turn([], [], 10)
    assert limiter.active == limiter.waiting == 0


@pytest.mark.asyncio
async def test_health_exposes_non_sensitive_queue_counters(limiter):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.state.orchestrator = AgentOrchestrator()
    async with limiter.slot("test"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/health")
    assert response.json()["model_concurrency"]["active"] == 1
    assert response.json()["model_concurrency"]["limit"] == 2
    assert "test-only" not in json.dumps(response.json())


@pytest.mark.asyncio
async def test_limiter_reads_config_once_per_service_loop(monkeypatch):
    loop = asyncio.get_running_loop()
    monkeypatch.delattr(loop, "_eduagent_model_limiter", raising=False)
    monkeypatch.setattr(settings, "llm_max_concurrency", 3)
    monkeypatch.setattr(settings, "llm_queue_timeout_seconds", .25)
    limiter = get_model_limiter()
    assert get_model_limiter() is limiter
    assert limiter.limit == 3 and limiter.queue_timeout == .25


@pytest.mark.parametrize("field,value", [
    ("llm_max_concurrency", 0), ("llm_max_concurrency", 257),
    ("llm_queue_timeout_seconds", 0), ("llm_queue_timeout_seconds", float("inf")),
    ("harness_queue_timeout_seconds", -1), ("harness_queue_timeout_seconds", float("nan")),
])
def test_invalid_concurrency_config_rejected(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="template", **{field: value})


@pytest.mark.parametrize("field,value", [
    ("llm_max_concurrency", 3), ("llm_queue_timeout_seconds", 2),
    ("harness_queue_timeout_seconds", 2),
])
def test_concurrency_changes_execution_fingerprint(field, value):
    cfg = Settings(_env_file=None, llm_provider="template")
    changed = cfg.model_copy(update={field: value})
    assert config_fingerprint(cfg) != config_fingerprint(changed)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "anthropic", "deepseek", "minimax"])
async def test_legacy_adapters_share_global_limit(provider, limiter, monkeypatch):
    from llm.base import Message
    from llm.openai_adapter import OpenAILLM
    from llm.anthropic_adapter import AnthropicLLM
    from llm.deepseek_adapter import DeepSeekLLM
    from llm.minimax_adapter import MiniMaxLLM

    adapters = {"openai": OpenAILLM, "anthropic": AnthropicLLM,
                "deepseek": DeepSeekLLM, "minimax": MiniMaxLLM}
    adapter = adapters[provider](api_key="test-only")
    calls = []

    def respond(request):
        calls.append(request)
        assert limiter.active == 2
        return httpx.Response(200, json={
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "content": [{"type": "text", "text": "ok"}], "usage": {}})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    async with limiter.slot("main-runtime"), limiter.slot("background"):
        with pytest.raises(QueueTimeout):
            await adapter.chat([Message(role="user", content="q")])
        assert not calls
    async with limiter.slot("main-runtime"):
        assert (await adapter.chat([Message(role="user", content="q")])).content == "ok"
    assert len(calls) == 1 and limiter.active == 0


@pytest.mark.asyncio
async def test_rerank_uses_same_remote_permit(limiter, monkeypatch):
    calls = []
    real_client = httpx.AsyncClient

    def respond(request):
        calls.append(request)
        assert limiter.active == 2
        assert request.url.path.endswith("/rerank")
        return httpx.Response(200, json={"results": [{"index": 1}, {"index": 0}],
                                        "usage": {"total_tokens": 2}})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: real_client(
        **kwargs, transport=httpx.MockTransport(respond)))
    cfg = Settings(_env_file=None, llm_provider="template", memory_embedding_api_key="test")
    retrieval = MemoryRetrieval(None, config=cfg)
    async with limiter.slot("chat"):
        refs, usage = await retrieval.rerank("q", ["a", "b"],
                                           {"a": {"content": "A"}, "b": {"content": "B"}})
    assert refs == ["b", "a"] and usage == {"total_tokens": 2}
    assert len(calls) == 1 and limiter.active == 0


@pytest.mark.asyncio
async def test_cancel_actual_sdk_request_releases_global_permit(limiter):
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def create(**kwargs):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    task = asyncio.create_task(service(create).tool_turn([], [], 10))
    try:
        await asyncio.wait_for(entered.wait(), 1)
        assert limiter.active == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set() and limiter.active == limiter.waiting == 0
        async with limiter.slot("first"), limiter.slot("second"):
            assert limiter.active == 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
