"""Engagement agent for detecting frustration, boredom, and fatigue."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any

from .base_agent import BaseAgent
from core.event_bus import Event, EventType

logger = logging.getLogger(__name__)


class LearningState(str, Enum):
    FOCUSED = "focused"
    STRUGGLING = "struggling"
    FRUSTRATED = "frustrated"
    BORED = "bored"
    FATIGUED = "fatigued"
    IDLE = "idle"


class LearnerEngagement:
    def __init__(self, learner_id: str):
        self.learner_id = learner_id
        self.state = LearningState.FOCUSED
        self.recent_response_times: list[float] = []
        self.recent_results: list[bool] = []
        self.session_start = datetime.now()
        self.last_activity = datetime.now()
        self.consecutive_errors = 0
        self.consecutive_correct = 0
        self.total_interactions = 0
        self.encouragement_count = 0

    @property
    def session_duration_minutes(self) -> float:
        return (datetime.now() - self.session_start).total_seconds() / 60

    @property
    def idle_seconds(self) -> float:
        return (datetime.now() - self.last_activity).total_seconds()

    @property
    def recent_accuracy(self) -> float:
        recent = self.recent_results[-10:]
        return sum(recent) / max(1, len(recent)) if recent else 0.5


class EngagementAgent(BaseAgent):
    """Track learning behavior and emit pacing interventions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._engagements: dict[str, LearnerEngagement] = {}

    @property
    def subscribed_events(self) -> list[EventType]:
        return [
            EventType.STUDENT_SUBMISSION,
            EventType.ASSESSMENT_COMPLETE,
            EventType.STUDENT_MESSAGE,
        ]

    def _get_engagement(self, learner_id: str) -> LearnerEngagement:
        if learner_id not in self._engagements:
            self._engagements[learner_id] = LearnerEngagement(learner_id)
        return self._engagements[learner_id]

    async def handle_event(self, event: Event) -> None:
        if event.type == EventType.STUDENT_SUBMISSION:
            await self._track_submission(event)
        elif event.type == EventType.ASSESSMENT_COMPLETE:
            await self._analyze_engagement(event)
        elif event.type == EventType.STUDENT_MESSAGE:
            await self._track_activity(event)

    async def _track_submission(self, event: Event) -> None:
        engagement = self._get_engagement(event.learner_id)
        is_correct = bool(event.data.get("is_correct", False))
        time_spent = float(event.data.get("time_spent_seconds", 0))

        engagement.last_activity = datetime.now()
        engagement.total_interactions += 1
        engagement.recent_results.append(is_correct)
        if time_spent > 0:
            engagement.recent_response_times.append(time_spent)

        if is_correct:
            engagement.consecutive_correct += 1
            engagement.consecutive_errors = 0
        else:
            engagement.consecutive_errors += 1
            engagement.consecutive_correct = 0

        engagement.recent_results = engagement.recent_results[-20:]
        engagement.recent_response_times = engagement.recent_response_times[-20:]

    async def _track_activity(self, event: Event) -> None:
        engagement = self._get_engagement(event.learner_id)
        engagement.last_activity = datetime.now()
        engagement.total_interactions += 1

    async def _analyze_engagement(self, event: Event) -> None:
        engagement = self._get_engagement(event.learner_id)
        old_state = engagement.state
        new_state = self._detect_state(engagement)
        engagement.state = new_state

        if new_state != old_state:
            logger.info(
                "[EngagementAgent] learner=%s state: %s -> %s",
                event.learner_id,
                old_state.value,
                new_state.value,
            )

        if new_state == LearningState.FRUSTRATED:
            await self._intervene_frustration(event.learner_id, engagement, event.correlation_id)
        elif new_state == LearningState.BORED:
            await self._intervene_boredom(event.learner_id, engagement, event.correlation_id)
        elif new_state == LearningState.FATIGUED:
            await self._intervene_fatigue(event.learner_id, engagement, event.correlation_id)
        elif new_state == LearningState.FOCUSED and engagement.consecutive_correct >= 3:
            await self._encourage(event.learner_id, engagement, event.correlation_id)

    def _detect_state(self, engagement: LearnerEngagement) -> LearningState:
        if engagement.idle_seconds > 300:
            return LearningState.IDLE
        if engagement.consecutive_errors >= 3:
            return LearningState.FRUSTRATED
        if engagement.session_duration_minutes > 45 and engagement.recent_accuracy < 0.5:
            return LearningState.FATIGUED
        if engagement.recent_accuracy > 0.9 and engagement.consecutive_correct >= 5:
            return LearningState.BORED
        if engagement.consecutive_errors >= 1:
            return LearningState.STRUGGLING
        return LearningState.FOCUSED

    async def _intervene_frustration(
        self,
        learner_id: str,
        engagement: LearnerEngagement,
        correlation_id: str | None,
    ) -> None:
        await self.emit(
            EventType.ENGAGEMENT_ALERT,
            learner_id,
            {
                "alert_type": "frustration",
                "consecutive_errors": engagement.consecutive_errors,
                "recent_accuracy": engagement.recent_accuracy,
                "message": "先别急着追求做对，我们先把这类题的关键判断点拆清楚，再继续往下做。",
            },
            correlation_id=correlation_id,
        )
        await self.emit(
            EventType.PACE_ADJUSTMENT,
            learner_id,
            {"action": "slow_down", "reason": "frustration_detected"},
            correlation_id=correlation_id,
        )

    async def _intervene_boredom(
        self,
        learner_id: str,
        engagement: LearnerEngagement,
        correlation_id: str | None,
    ) -> None:
        await self.emit(
            EventType.ENGAGEMENT_ALERT,
            learner_id,
            {
                "alert_type": "boredom",
                "consecutive_correct": engagement.consecutive_correct,
                "recent_accuracy": engagement.recent_accuracy,
                "message": "你这几题掌握得很稳，我们可以把难度再往上提一点，试试更有挑战的题型。",
            },
            correlation_id=correlation_id,
        )
        await self.emit(
            EventType.PACE_ADJUSTMENT,
            learner_id,
            {"action": "speed_up", "reason": "boredom_detected"},
            correlation_id=correlation_id,
        )

    async def _intervene_fatigue(
        self,
        learner_id: str,
        engagement: LearnerEngagement,
        correlation_id: str | None,
    ) -> None:
        await self.emit(
            EventType.ENCOURAGEMENT,
            learner_id,
            {
                "message": (
                    f"你已经连续学习了 {engagement.session_duration_minutes:.0f} 分钟，"
                    "可以先休息 10 分钟，再回来继续，效果通常会更好。"
                ),
                "type": "fatigue_break",
                "session_minutes": engagement.session_duration_minutes,
            },
            correlation_id=correlation_id,
        )

    async def _encourage(
        self,
        learner_id: str,
        engagement: LearnerEngagement,
        correlation_id: str | None,
    ) -> None:
        if engagement.encouragement_count % 3 == 0:
            await self.emit(
                EventType.ENCOURAGEMENT,
                learner_id,
                {
                    "message": f"你已经连续答对 {engagement.consecutive_correct} 题了，状态很稳，继续保持。",
                    "type": "positive_streak",
                    "streak": engagement.consecutive_correct,
                },
                correlation_id=correlation_id,
            )
        engagement.encouragement_count += 1

    def get_state_for_save(self, learner_id: str) -> dict[str, Any] | None:
        engagement = self._engagements.get(learner_id)
        if not engagement:
            return None

        return {
            "state": engagement.state.value,
            "consecutive_errors": engagement.consecutive_errors,
            "consecutive_correct": engagement.consecutive_correct,
            "total_interactions": engagement.total_interactions,
            "encouragement_count": engagement.encouragement_count,
            "recent_results": engagement.recent_results[-20:],
            "recent_response_times": engagement.recent_response_times[-20:],
            "session_start": engagement.session_start.isoformat(),
        }

    def load_state(self, learner_id: str, state_data: dict[str, Any]) -> None:
        engagement = self._get_engagement(learner_id)
        engagement.state = LearningState(state_data.get("state", "focused"))
        engagement.consecutive_errors = state_data.get("consecutive_errors", 0)
        engagement.consecutive_correct = state_data.get("consecutive_correct", 0)
        engagement.total_interactions = state_data.get("total_interactions", 0)
        engagement.encouragement_count = state_data.get("encouragement_count", 0)
        engagement.recent_results = state_data.get("recent_results", [])
        engagement.recent_response_times = state_data.get("recent_response_times", [])

        session_start = state_data.get("session_start")
        if session_start:
            try:
                engagement.session_start = datetime.fromisoformat(session_start)
            except (ValueError, TypeError):
                pass
