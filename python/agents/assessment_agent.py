"""Assessment agent for mastery updates after student submissions."""

from __future__ import annotations

import logging

from .base_agent import BaseAgent
from core.event_bus import Event, EventType

logger = logging.getLogger(__name__)


class AssessmentAgent(BaseAgent):
    """Update learner mastery and emit assessment-related events."""

    @property
    def subscribed_events(self) -> list[EventType]:
        return [EventType.STUDENT_SUBMISSION]

    async def handle_event(self, event: Event) -> None:
        if event.type == EventType.STUDENT_SUBMISSION:
            await self._handle_submission(event)

    async def _handle_submission(self, event: Event) -> None:
        learner_id = event.learner_id
        data = event.data
        knowledge_id = data.get("knowledge_id", "")
        is_correct = data.get("is_correct", False)

        model = self.get_learner_model(learner_id)
        state = model.update_mastery(knowledge_id, is_correct)

        await self.emit(
            EventType.MASTERY_UPDATED,
            learner_id,
            {
                "knowledge_id": knowledge_id,
                "mastery": state.mastery,
                "level": state.level.value,
                "attempts": state.attempts,
                "streak": state.streak,
                "confidence": state.confidence,
            },
            correlation_id=event.correlation_id,
        )

        if state.mastery < 0.3 and state.attempts >= 3:
            await self.emit(
                EventType.WEAKNESS_DETECTED,
                learner_id,
                {
                    "knowledge_id": knowledge_id,
                    "mastery": state.mastery,
                    "attempts": state.attempts,
                    "suggestion": "需要先回到前置知识点补一补，再继续当前题型。",
                },
                correlation_id=event.correlation_id,
            )

        await self.emit(
            EventType.ASSESSMENT_COMPLETE,
            learner_id,
            {
                "knowledge_id": knowledge_id,
                "is_correct": is_correct,
                "mastery": state.mastery,
                "level": state.level.value,
                "overall_progress": model.get_overall_progress(),
                "question": data.get("question", ""),
                "student_answer": data.get("student_answer", ""),
                "correct_answer": data.get("correct_answer", ""),
                "evaluation_feedback": data.get("evaluation_feedback", ""),
                "explanation": data.get("explanation", ""),
            },
            correlation_id=event.correlation_id,
        )
