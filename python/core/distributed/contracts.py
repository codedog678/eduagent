from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    model_validator,
)

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
Question = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=4000),
]


class RunOperation(StrEnum):
    LEARNING_TASK = "learning_task"


class RunStatus(StrEnum):
    ACCEPTED = "accepted"
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    COMMITTING = "committing"
    RETRYABLE_FAILED = "retryable_failed"
    COMPLETED = "completed"
    TERMINAL_FAILED = "terminal_failed"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"

    @property
    def terminal(self) -> bool:
        return self in {
            self.COMPLETED,
            self.TERMINAL_FAILED,
            self.EXHAUSTED,
            self.CANCELLED,
        }


def canonical_hash(value: Any) -> str:
    body = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


class LearningTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_id: Identifier
    request_id: Identifier
    knowledge_id: Identifier
    question: Question
    session_id: Identifier | None = None
    thread_id: Identifier | None = None
    quiz_id: Identifier | None = None


class DistributedRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learner_id: Identifier
    request_id: Identifier
    operation: RunOperation
    payload: LearningTaskPayload

    @model_validator(mode="after")
    def validate_scope(self) -> "DistributedRunRequest":
        if self.payload.learner_id != self.learner_id:
            raise ValueError("payload learner_id must match envelope")
        if self.payload.request_id != self.request_id:
            raise ValueError("payload request_id must match envelope")
        return self

    @property
    def input_hash(self) -> str:
        return canonical_hash(self.model_dump(mode="json"))
