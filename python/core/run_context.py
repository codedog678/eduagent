"""单轮执行上下文；领域事件和 Tutor 共用关联 ID 与截止时间。"""

from contextvars import ContextVar
from dataclasses import dataclass, field
import time
from typing import Any


class RunExhausted(RuntimeError):
    """本轮运行预算耗尽。"""


@dataclass
class RunContext:
    learner: str
    run_id: str
    attempt_id: str
    deadline: float
    session_id: str = ""
    thread_id: str = ""
    knowledge_id: str = ""
    conversation: bool = False
    quiz: dict | None = None
    history: Any = None
    knowledge_graph: Any = None
    model_state: dict = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    dialogue_state: str = "answered"
    pending_question: str | None = None
    answered_question_id: str | None = None
    parent_event_id: str | None = None

    def remaining(self) -> float:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise RunExhausted("deadline")
        return remaining

    def record(self, kind: str, agent: str = "Harness", **data):
        self.steps.append({
            "seq": len(self.steps) + 1, "kind": kind, "agent": agent,
            "timestamp": time.time(), **data,
        })


active_run: ContextVar[RunContext | None] = ContextVar("learning_run", default=None)
