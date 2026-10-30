"""单轮执行上下文；领域事件和 Tutor 共用关联 ID 与截止时间。"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from core.distributed.expert_contracts import RunExecutionAuthority


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
    effective_policy_hash: str = ""
    quiz: dict | None = None
    history: Any = None
    knowledge_graph: Any = None
    model_state: dict = field(default_factory=dict)
    steps: list[dict] = field(default_factory=list)
    events: list[Any] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    retrieved_refs: list[str] = field(default_factory=list)
    read_refs: list[str] = field(default_factory=list)
    cited_refs: list[str] = field(default_factory=list)
    dialogue_state: str = "answered"
    pending_question: str | None = None
    answered_question_id: str | None = None
    parent_event_id: str | None = None
    input_text: str = ""
    memory_proposals: list[dict] = field(default_factory=list)
    profile_state: dict = field(default_factory=dict)
    review_queue: list[dict] = field(default_factory=list)
    prepare_practice: Any = None
    prepared_quiz: Any = None
    plan: dict | None = None
    plan_thread_id: str | None = None
    expert_results: list[dict] = field(default_factory=list)
    model_calls: int = 0
    tool_calls: int = 0
    max_model_calls: int = 8
    max_tool_calls: int = 16
    tool_cache: dict = field(default_factory=dict)
    read_evidence: dict = field(default_factory=dict)
    sensitive_payloads: set[str] = field(default_factory=set)
    retrieved_items: list | None = None
    history_discovery_used: bool = False
    role: str = "Tutor"
    task_id: str | None = None
    execution_authority: RunExecutionAuthority | None = None
    expert_gateway: Any = None

    def consume(self, resource):
        self.remaining()
        attr = resource + "_calls"
        value = getattr(self, attr) + 1
        if value > getattr(self, "max_" + attr):
            raise RunExhausted(resource + "_call_budget")
        setattr(self, attr, value)
        self.record("budget_used", self.role, resource=resource, used=value,
                    task_id=self.task_id, parent_run_id=self.run_id)

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
