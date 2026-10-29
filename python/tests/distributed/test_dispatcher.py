import asyncio

import pytest

from core.distributed.dispatcher import OutboxDispatcher
from tests.distributed.helpers import spec

pytestmark = pytest.mark.distributed_integration


async def test_dispatch_marks_outbox_and_publishes_once(repo, broker):
    run = await repo.accept(spec())
    dispatcher = OutboxDispatcher(repo, broker, batch_size=10)

    assert await dispatcher.dispatch_once() == 1
    assert await dispatcher.dispatch_once() == 0

    messages = await broker.read("consumer-a", count=10, block_ms=10)
    assert [item.event_key for item in messages] == [
        f"run:{run.id}:accepted"
    ]


async def test_unmarked_publish_can_be_republished(repo, broker):
    run = await repo.accept(spec(request_id="republished"))
    row = (await repo.pending_outbox(1))[0]

    await broker.publish(row.event_key, row.payload)
    await broker.publish(row.event_key, row.payload)

    messages = await broker.read("consumer-a", count=10, block_ms=10)
    assert len(messages) == 2
    assert {item.event_key for item in messages} == {
        f"run:{run.id}:accepted"
    }


async def test_pending_delivery_can_be_reclaimed_by_another_consumer(
    broker,
):
    await broker.publish("run:test:accepted", {"run_id": "test"})
    original = await broker.read("consumer-a", count=1, block_ms=10)
    assert len(original) == 1

    await asyncio.sleep(0.01)
    reclaimed = await broker.reclaim(
        "consumer-b",
        min_idle_ms=1,
        count=10,
    )

    assert reclaimed == original
    await broker.ack(reclaimed[0].redis_id)
    assert await broker.reclaim(
        "consumer-c",
        min_idle_ms=0,
        count=10,
    ) == []
