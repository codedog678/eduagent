from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError


@dataclass(frozen=True)
class RunMessage:
    redis_id: str
    event_key: str
    payload: dict


class RedisRunBroker:
    def __init__(self, redis: Redis, stream: str, group: str) -> None:
        self.redis = redis
        self.stream = stream
        self.group = group

    async def ensure_group(self) -> None:
        try:
            await self.redis.xgroup_create(
                self.stream,
                self.group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish(self, event_key: str, payload: dict) -> str:
        redis_id = await self.redis.xadd(
            self.stream,
            {
                "event_key": event_key,
                "payload": json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        )
        return self._text(redis_id)

    async def read(
        self,
        consumer: str,
        count: int,
        block_ms: int,
    ) -> list[RunMessage]:
        await self.ensure_group()
        rows = await self.redis.xreadgroup(
            self.group,
            consumer,
            {self.stream: ">"},
            count=count,
            block=block_ms,
        )
        return [
            self._message(message_id, fields)
            for _, messages in rows
            for message_id, fields in messages
        ]

    async def reclaim(
        self,
        consumer: str,
        min_idle_ms: int,
        count: int,
    ) -> list[RunMessage]:
        await self.ensure_group()
        response = await self.redis.xautoclaim(
            self.stream,
            self.group,
            consumer,
            min_idle_ms,
            start_id="0-0",
            count=count,
        )
        messages = response[1] if len(response) > 1 else []
        return [
            self._message(message_id, fields)
            for message_id, fields in messages
        ]

    async def ack(self, redis_id: str) -> bool:
        return bool(
            await self.redis.xack(
                self.stream,
                self.group,
                redis_id,
            )
        )

    async def reset_for_tests(self) -> None:
        await self.redis.delete(self.stream)

    @classmethod
    def _message(
        cls,
        message_id: Any,
        fields: dict[Any, Any],
    ) -> RunMessage:
        normalized = {
            cls._text(key): cls._text(value)
            for key, value in fields.items()
        }
        return RunMessage(
            redis_id=cls._text(message_id),
            event_key=normalized["event_key"],
            payload=json.loads(normalized["payload"]),
        )

    @staticmethod
    def _text(value: Any) -> str:
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)
