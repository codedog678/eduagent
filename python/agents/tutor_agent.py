"""Tutor agent for student-facing teaching responses and hints."""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Awaitable, Callable

from .base_agent import BaseAgent
from core.event_bus import Event, EventType
from core.llm_service import TeachingReply, get_llm_service

logger = logging.getLogger(__name__)


class HintLevel:
    METACOGNITIVE = 1
    SCAFFOLDING = 2
    TARGETED = 3


def _normalize_text(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^\w\u4e00-\u9fff]+", "", value)
    return value


class TutorAgent(BaseAgent):
    """Generate teacher replies for wrong answers, questions, and hints."""

    MAX_HISTORY = 16
    MAX_TOPIC_HISTORY = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._student_attempts: dict[str, int] = {}
        self._hint_history: dict[str, int] = {}
        self._conversation_history: dict[str, list[dict[str, Any]]] = {}
        self._topic_history: dict[str, dict[str, list[dict[str, Any]]]] = {}

    @property
    def subscribed_events(self) -> list[EventType]:
        return [
            EventType.ASSESSMENT_COMPLETE,
            EventType.STUDENT_QUESTION,
            EventType.STUDENT_MESSAGE,
            EventType.ENGAGEMENT_ALERT,
        ]

    async def handle_event(self, event: Event) -> None:
        if event.type == EventType.ASSESSMENT_COMPLETE:
            await self._handle_assessment(event)
        elif event.type == EventType.STUDENT_QUESTION:
            await self._handle_student_question(event)
        elif event.type == EventType.STUDENT_MESSAGE:
            await self._handle_student_message(event)
        elif event.type == EventType.ENGAGEMENT_ALERT:
            await self._handle_engagement_alert(event)

    async def _handle_assessment(self, event: Event) -> None:
        learner_id = event.learner_id
        knowledge_id = event.data.get("knowledge_id", "")
        mastery = float(event.data.get("mastery", 0.0))
        level = event.data.get("level", "beginner")
        is_correct = bool(event.data.get("is_correct", False))

        question = str(event.data.get("question", ""))
        student_answer = str(event.data.get("student_answer", ""))
        correct_answer = str(event.data.get("correct_answer", ""))
        evaluation_feedback = str(event.data.get("evaluation_feedback", ""))
        attempt_key = self._build_attempt_key(learner_id, knowledge_id, question, correct_answer)

        if question or student_answer:
            self._add_to_history(
                learner_id,
                role="student",
                content=self._format_submission_summary(question, student_answer, correct_answer),
                knowledge_id=knowledge_id,
                context_type="submission",
            )

        if is_correct:
            self._student_attempts[attempt_key] = 0
            self._hint_history.pop(attempt_key, None)
            return

        attempts = self._student_attempts.get(attempt_key, 0) + 1
        self._student_attempts[attempt_key] = attempts

        if attempts >= 2:
            reply, hint_level, hint_count = await self._provide_hint(
                learner_id=learner_id,
                knowledge_id=knowledge_id,
                attempt_key=attempt_key,
                attempts=attempts,
            )
            self._record_teacher_reply(learner_id, knowledge_id, reply, "hint")
            await self._emit_teaching_response(
                learner_id=learner_id,
                knowledge_id=knowledge_id,
                reply=reply,
                context_type="hint",
                teaching_style="hint",
                correlation_id=event.correlation_id,
                extra={
                    "attempts": attempts,
                    "hint_count": hint_count,
                    "hint_level": hint_level,
                },
            )
            return

        llm_service = get_llm_service()
        reply = await self._generate_distinct_reply(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            builder=lambda avoid_responses, variant_offset: llm_service.generate_answer_wrong_response(
                knowledge_id=knowledge_id,
                level=level,
                mastery=mastery,
                question=question,
                student_answer=student_answer,
                correct_answer=correct_answer,
                evaluation_feedback=evaluation_feedback,
                topic_history=self._get_topic_history(learner_id, knowledge_id),
                session_history=self._get_history(learner_id),
                avoid_responses=avoid_responses,
                variant_offset=variant_offset,
            ),
        )
        self._record_teacher_reply(learner_id, knowledge_id, reply, "wrong_answer")
        await self._emit_teaching_response(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            reply=reply,
            context_type="wrong_answer",
            teaching_style="guided_explanation",
            correlation_id=event.correlation_id,
            extra={"attempts": attempts},
        )

    async def _handle_student_question(self, event: Event) -> None:
        learner_id = event.learner_id
        knowledge_id = event.data.get("knowledge_id", "general")
        question = str(event.data.get("question", ""))

        self._add_to_history(
            learner_id,
            role="student",
            content=question,
            knowledge_id=knowledge_id,
            context_type="question",
        )

        llm_service = get_llm_service()
        reply = await self._generate_distinct_reply(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            builder=lambda avoid_responses, variant_offset: llm_service.generate_student_question_response(
                knowledge_id=knowledge_id,
                question=question,
                topic_history=self._get_topic_history(learner_id, knowledge_id),
                session_history=self._get_history(learner_id),
                avoid_responses=avoid_responses,
                variant_offset=variant_offset,
            ),
        )
        self._record_teacher_reply(learner_id, knowledge_id, reply, "question")
        await self._emit_teaching_response(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            reply=reply,
            context_type="question",
            teaching_style="question_answer",
            correlation_id=event.correlation_id,
        )

    async def _handle_student_message(self, event: Event) -> None:
        learner_id = event.learner_id
        knowledge_id = event.data.get("knowledge_id", "general")
        message = str(event.data.get("message", ""))

        self._add_to_history(
            learner_id,
            role="student",
            content=message,
            knowledge_id=knowledge_id,
            context_type="message",
        )

        llm_service = get_llm_service()
        reply = await self._generate_distinct_reply(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            builder=lambda avoid_responses, variant_offset: llm_service.generate_message_response(
                knowledge_id=knowledge_id,
                message=message,
                topic_history=self._get_topic_history(learner_id, knowledge_id),
                session_history=self._get_history(learner_id),
                avoid_responses=avoid_responses,
                variant_offset=variant_offset,
            ),
        )
        self._record_teacher_reply(learner_id, knowledge_id, reply, "message")
        await self._emit_teaching_response(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            reply=reply,
            context_type="message",
            teaching_style="conversation",
            correlation_id=event.correlation_id,
        )

    async def _handle_engagement_alert(self, event: Event) -> None:
        logger.info(
            "[TutorAgent] engagement alert for %s: %s",
            event.learner_id,
            event.data.get("alert_type", "unknown"),
        )

    async def _provide_hint(
        self,
        learner_id: str,
        knowledge_id: str,
        attempt_key: str,
        attempts: int,
    ) -> tuple[TeachingReply, int, int]:
        hint_count = self._hint_history.get(attempt_key, 0) + 1
        self._hint_history[attempt_key] = hint_count

        if hint_count <= 2:
            hint_level = HintLevel.METACOGNITIVE
        elif hint_count <= 4:
            hint_level = HintLevel.SCAFFOLDING
        else:
            hint_level = HintLevel.TARGETED

        llm_service = get_llm_service()
        reply = await self._generate_distinct_reply(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            builder=lambda avoid_responses, variant_offset: llm_service.generate_hint_response(
                knowledge_id=knowledge_id,
                hint_level=hint_level,
                hint_count=hint_count,
                topic_history=self._get_topic_history(learner_id, knowledge_id),
                session_history=self._get_history(learner_id),
                avoid_responses=avoid_responses,
                variant_offset=variant_offset,
            ),
        )
        logger.info(
            "[TutorAgent] hint learner=%s, knowledge=%s, attempts=%d, hint_count=%d",
            learner_id,
            knowledge_id,
            attempts,
            hint_count,
        )
        reply_data = reply.model_copy(
            update={"response_variant": f"{reply.response_variant}|c{hint_count}|l{hint_level}"}
        )
        return reply_data, hint_level, hint_count

    async def _generate_distinct_reply(
        self,
        learner_id: str,
        knowledge_id: str,
        builder: Callable[[list[str], int], Awaitable[TeachingReply]],
    ) -> TeachingReply:
        recent = self._recent_teacher_responses(learner_id, knowledge_id, limit=2)
        reply = await builder(recent, 0)
        if self._is_too_similar(reply.response, recent):
            reply = await builder(recent, 1)
        return reply

    def _is_too_similar(self, candidate: str, previous_responses: list[str]) -> bool:
        candidate_norm = _normalize_text(candidate)
        if not candidate_norm:
            return False

        candidate_first = self._first_sentence(candidate_norm)
        for previous in previous_responses:
            previous_norm = _normalize_text(previous)
            if not previous_norm:
                continue
            if self._first_sentence(previous_norm) == candidate_first:
                return True
            if SequenceMatcher(None, candidate_norm, previous_norm).ratio() >= 0.86:
                return True
        return False

    def _first_sentence(self, text: str) -> str:
        if not text:
            return ""
        parts = re.split(r"[。！？!?]", text, maxsplit=1)
        return parts[0]

    async def _emit_teaching_response(
        self,
        learner_id: str,
        knowledge_id: str,
        reply: TeachingReply,
        context_type: str,
        teaching_style: str,
        correlation_id: str | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "knowledge_id": knowledge_id,
            "response": reply.response,
            "teaching_style": teaching_style,
            "context_type": context_type,
            "generation_mode": reply.generation_mode,
            "response_variant": reply.response_variant,
            "history_scope": reply.history_scope,
        }
        if extra:
            payload.update(extra)
        await self.emit(
            EventType.TEACHING_RESPONSE,
            learner_id,
            payload,
            correlation_id=correlation_id,
        )

    def _record_teacher_reply(
        self,
        learner_id: str,
        knowledge_id: str,
        reply: TeachingReply,
        context_type: str,
    ) -> None:
        self._add_to_history(
            learner_id,
            role="teacher",
            content=reply.response,
            knowledge_id=knowledge_id,
            context_type=context_type,
            generation_mode=reply.generation_mode,
            response_variant=reply.response_variant,
            history_scope=reply.history_scope,
        )

    def _format_submission_summary(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
    ) -> str:
        parts = []
        if question:
            parts.append(f"题目：{question}")
        if student_answer:
            parts.append(f"我的答案：{student_answer}")
        if correct_answer:
            parts.append(f"参考答案：{correct_answer}")
        return "；".join(parts) if parts else "我刚做完了一道题。"

    def _build_attempt_key(
        self,
        learner_id: str,
        knowledge_id: str,
        question: str,
        correct_answer: str,
    ) -> str:
        normalized_question = _normalize_text(question or knowledge_id)
        normalized_answer = _normalize_text(correct_answer)
        return f"{learner_id}:{knowledge_id}:{normalized_question}:{normalized_answer}"

    def _add_to_history(
        self,
        learner_id: str,
        role: str,
        content: str,
        knowledge_id: str | None = None,
        context_type: str | None = None,
        **extra: Any,
    ) -> None:
        entry = {
            "role": role,
            "content": content,
            "knowledge_id": knowledge_id,
            "context_type": context_type,
            **extra,
        }
        history = self._conversation_history.setdefault(learner_id, [])
        history.append(entry)
        if len(history) > self.MAX_HISTORY:
            self._conversation_history[learner_id] = history[-self.MAX_HISTORY :]

        if knowledge_id:
            learner_topics = self._topic_history.setdefault(learner_id, {})
            topic_history = learner_topics.setdefault(knowledge_id, [])
            topic_history.append(entry)
            if len(topic_history) > self.MAX_TOPIC_HISTORY:
                learner_topics[knowledge_id] = topic_history[-self.MAX_TOPIC_HISTORY :]

    def _get_history(self, learner_id: str) -> list[dict[str, Any]]:
        return list(self._conversation_history.get(learner_id, []))

    def _get_topic_history(self, learner_id: str, knowledge_id: str) -> list[dict[str, Any]]:
        return list(self._topic_history.get(learner_id, {}).get(knowledge_id, []))

    def _recent_teacher_responses(
        self,
        learner_id: str,
        knowledge_id: str,
        limit: int = 2,
    ) -> list[str]:
        responses = [
            item["content"]
            for item in self._get_topic_history(learner_id, knowledge_id)
            if item.get("role") == "teacher" and item.get("content")
        ]
        return responses[-limit:]

    def get_hint_usage(self, learner_id: str) -> int:
        prefix = f"{learner_id}:"
        return sum(count for key, count in self._hint_history.items() if key.startswith(prefix))

    def get_state_for_save(self, learner_id: str) -> dict[str, Any] | None:
        attempts_data = {
            key[len(f"{learner_id}:") :]: count
            for key, count in self._student_attempts.items()
            if key.startswith(f"{learner_id}:") and count
        }
        hint_data = {
            key[len(f"{learner_id}:") :]: count
            for key, count in self._hint_history.items()
            if key.startswith(f"{learner_id}:") and count
        }

        state: dict[str, Any] = {}
        if attempts_data:
            state["student_attempts"] = attempts_data
        if hint_data:
            state["hint_history"] = hint_data
        return state or None

    def load_state(self, learner_id: str, state_data: dict[str, Any]) -> None:
        for suffix, count in state_data.get("student_attempts", {}).items():
            self._student_attempts[f"{learner_id}:{suffix}"] = count
        for suffix, count in state_data.get("hint_history", {}).items():
            self._hint_history[f"{learner_id}:{suffix}"] = count
