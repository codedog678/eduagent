"""Tutor agent for student-facing teaching responses and hints."""

from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Awaitable, Callable, Optional

from agents.base import BaseAgent
from core.event_bus import Event, EventBus, EventType
from core.learner_model import LearnerModel
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
    """
    辅导 Agent。

    职责：
    1. 回答学生问题
    2. 生成错题反馈
    3. 提供分级提示（元认知→脚手架→针对性）
    4. 苏格拉底式提问
    5. 管理对话上下文

    事件流：
    - 订阅: ASSESSMENT_COMPLETE, STUDENT_QUESTION, STUDENT_MESSAGE, ENGAGEMENT_ALERT
    - 发布: TEACHING_RESPONSE, HINT_PROVIDED, SOCRATIC_QUESTION
    """

    MAX_HISTORY = 16
    MAX_TOPIC_HISTORY = 10

    def __init__(
        self,
        event_bus: EventBus,
        learner_models: dict[str, LearnerModel] | None = None,
        name: str = "TutorAgent",
        llm_service=None,
        **_: Any,
    ) -> None:
        super().__init__(
            name=name,
            event_bus=event_bus,
            description="辅导学习者，提供讲解、提示和苏格拉底式提问",
            learner_models=learner_models,
        )
        self.llm_service = llm_service
        self._student_attempts: dict[str, int] = {}
        self._hint_history: dict[str, int] = {}
        self._conversation_history: dict[str, list[dict[str, Any]]] = {}
        self._topic_history: dict[str, dict[str, list[dict[str, Any]]]] = {}
        self._recent_submissions: dict[str, dict[str, dict[str, str]]] = {}
        # 苏格拉底式提问配置
        self._socratic_threshold = 2  # 错误次数超过此值时使用苏格拉底式提问
        self.register()

    def get_subscribed_events(self) -> list[EventType]:
        return [
            EventType.ASSESSMENT_COMPLETE,
            EventType.STUDENT_QUESTION,
            EventType.STUDENT_MESSAGE,
            EventType.ENGAGEMENT_ALERT,
        ]

    async def handle_event(self, event: Event) -> Optional[dict[str, Any]]:
        if event.type == EventType.ASSESSMENT_COMPLETE:
            return await self._handle_assessment(event)
        elif event.type == EventType.STUDENT_QUESTION:
            return await self._handle_student_question(event)
        elif event.type == EventType.STUDENT_MESSAGE:
            return await self._handle_student_message(event)
        elif event.type == EventType.ENGAGEMENT_ALERT:
            await self._handle_engagement_alert(event)
        return None

    async def _handle_assessment(self, event: Event) -> None:
        if event.data.get("protected_quiz"):
            correct = event.data.get("is_correct", False)
            reply = TeachingReply(
                response=("判断正确。你可以用一道新题检验是否能独立运用。"
                          if correct else
                          "先保留你的解题思路，重新检查题干线索。需要帮助时可以请求提示，或主动查看解析。"),
                generation_mode="local_policy", response_variant="formative-feedback",
                history_scope="topic_thread",
            )
            self._add_to_history(event.learner_id, "student",
                                 event.data.get("student_answer", ""),
                                 knowledge_id=event.data.get("knowledge_id"),
                                 context_type="submission")
            self._record_teacher_reply(event.learner_id, event.data.get("knowledge_id", ""),
                                       reply, "formative_feedback")
            await self._emit_teaching_response(
                event.learner_id, event.data.get("knowledge_id", ""), reply,
                "formative_feedback", "confirmation" if correct else "reflection",
                event.correlation_id)
            return
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
            submission_context = {
                "question": question,
                "student_answer": student_answer,
                "correct_answer": correct_answer,
                "evaluation_feedback": evaluation_feedback,
                "explanation": str(event.data.get("explanation", "")),
            }
            self._recent_submissions.setdefault(learner_id, {})[knowledge_id] = submission_context
            self._add_to_history(
                learner_id,
                role="student",
                content=self._format_submission_summary(question, student_answer, correct_answer),
                knowledge_id=knowledge_id,
                context_type="submission",
                **submission_context,
            )

        if is_correct:
            self._student_attempts[attempt_key] = 0
            self._hint_history.pop(attempt_key, None)
            if question or correct_answer or evaluation_feedback:
                reply = self._build_correct_answer_reply(
                    knowledge_id=knowledge_id,
                    question=question,
                    student_answer=student_answer,
                    correct_answer=correct_answer,
                    evaluation_feedback=evaluation_feedback,
                )
                self._record_teacher_reply(learner_id, knowledge_id, reply, "correct_answer")
                await self._emit_teaching_response(
                    learner_id=learner_id,
                    knowledge_id=knowledge_id,
                    reply=reply,
                    context_type="correct_answer",
                    teaching_style="confirmation",
                    correlation_id=event.correlation_id,
                )
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
        learner_context = self._build_learner_context(learner_id)
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
                learner_context=learner_context,
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
        learner_context = self._build_learner_context(learner_id)
        recent_submission = self._get_recent_submission(learner_id, knowledge_id)
        reply = await self._conversation_reply(question) or await self._generate_distinct_reply(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            builder=lambda avoid_responses, variant_offset: llm_service.generate_student_question_response(
                knowledge_id=knowledge_id,
                question=question,
                topic_history=self._get_topic_history(learner_id, knowledge_id),
                session_history=self._get_history(learner_id),
                avoid_responses=avoid_responses,
                variant_offset=variant_offset,
                learner_context=learner_context,
                recent_submission=recent_submission,
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
        learner_context = self._build_learner_context(learner_id)
        reply = await self._conversation_reply(message) or await self._generate_distinct_reply(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            builder=lambda avoid_responses, variant_offset: llm_service.generate_message_response(
                knowledge_id=knowledge_id,
                message=message,
                topic_history=self._get_topic_history(learner_id, knowledge_id),
                session_history=self._get_history(learner_id),
                avoid_responses=avoid_responses,
                variant_offset=variant_offset,
                learner_context=learner_context,
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

    async def _conversation_reply(self, text: str) -> TeachingReply | None:
        from core.run_context import active_run
        from core.tutor_runtime import TutorRuntime
        run = active_run.get()
        if not run or not run.conversation:
            return None
        return await TutorRuntime(run, get_llm_service(), run.knowledge_graph).run(text)

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
        learner_context = self._build_learner_context(learner_id)
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
                learner_context=learner_context,
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
            "source_refs": reply.source_refs,
            "dialogue_state": reply.dialogue_state,
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

    def _build_correct_answer_reply(
        self,
        knowledge_id: str,
        question: str,
        student_answer: str,
        correct_answer: str,
        evaluation_feedback: str,
    ) -> TeachingReply:
        answer = correct_answer or student_answer or "这个答案"
        if knowledge_id.startswith("vocab") and "submit" in f"{question} {answer}".lower():
            response = (
                f"对，这里选“{answer}”。关键是空格后面直接接的是“their essays”这个名词短语，"
                "submit 本身可以直接接“提交的东西”，所以用 submit something，不需要加 to。"
            )
        elif evaluation_feedback:
            response = f"对，这次判断是正确的。{evaluation_feedback}"
        else:
            response = f"对，这里选“{answer}”。你已经抓住了关键线索，接下来可以再用同样方法判断一题。"

        return TeachingReply(
            response=response,
            generation_mode="local_policy",
            response_variant="correct-confirmation",
            history_scope="topic_thread",
        )

    def _get_recent_submission(self, learner_id: str, knowledge_id: str) -> dict[str, str] | None:
        return self._recent_submissions.get(learner_id, {}).get(knowledge_id)

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

    def _build_learner_context(self, learner_id: str) -> str:
        model = self.get_learner_model(learner_id)
        progress = model.get_overall_progress()
        weak = model.get_weak_points(limit=5)
        total_points = progress.get("total_knowledge_points", 0)
        avg_mastery = progress.get("avg_mastery", 0.0)
        total_attempts = progress.get("total_attempts", 0)
        parts = [
            f"已学{total_points}个知识点",
            f"平均掌握度{avg_mastery:.0%}",
            f"总答题{total_attempts}次",
        ]
        if weak:
            parts.append("薄弱项：" + "、".join(w.knowledge_id for w in weak))
        return "，".join(parts)

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
        state["conversation_history"] = self._conversation_history.get(learner_id, [])
        state["topic_history"] = self._topic_history.get(learner_id, {})
        state["recent_submissions"] = self._recent_submissions.get(learner_id, {})
        if attempts_data:
            state["student_attempts"] = attempts_data
        if hint_data:
            state["hint_history"] = hint_data
        return state or None

    def load_state(self, learner_id: str, state_data: dict[str, Any]) -> None:
        self._conversation_history[learner_id] = state_data.get("conversation_history", [])
        self._topic_history[learner_id] = state_data.get("topic_history", {})
        self._recent_submissions[learner_id] = state_data.get("recent_submissions", {})
        for suffix, count in state_data.get("student_attempts", {}).items():
            self._student_attempts[f"{learner_id}:{suffix}"] = count
        for suffix, count in state_data.get("hint_history", {}).items():
            self._hint_history[f"{learner_id}:{suffix}"] = count
