"""Engagement agent for detecting frustration, boredom, and fatigue."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from agents.base import BaseAgent
from config.settings import settings
from core.event_bus import Event, EventType
from core.learner_model import LearnerModel
from core.llm_service import get_llm_service

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
    """
    参与度 Agent。

    职责：
    1. 检测学习者情绪状态（挫败、无聊、疲劳、空闲）
    2. 分析学习节奏
    3. 生成干预建议
    4. 发送鼓励消息

    事件流：
    - 订阅: STUDENT_SUBMISSION, ASSESSMENT_COMPLETE, STUDENT_MESSAGE
    - 发布: ENGAGEMENT_ALERT, PACE_ADJUSTMENT, ENCOURAGEMENT
    """

    def __init__(
        self,
        event_bus,
        learner_models: dict[str, LearnerModel] | None = None,
        name: str = "EngagementAgent",
        **_: Any,
    ) -> None:
        super().__init__(
            name=name,
            event_bus=event_bus,
            description="检测学习者情绪状态，生成干预建议",
            learner_models=learner_models,
        )
        self._engagements: dict[str, LearnerEngagement] = {}
        self.register()

    def get_subscribed_events(self) -> list[EventType]:
        return [
            EventType.STUDENT_SUBMISSION,
            EventType.ASSESSMENT_COMPLETE,
            EventType.STUDENT_MESSAGE,
        ]

    def _get_engagement(self, learner_id: str) -> LearnerEngagement:
        if learner_id not in self._engagements:
            self._engagements[learner_id] = LearnerEngagement(learner_id)
        return self._engagements[learner_id]

    async def handle_event(self, event: Event) -> Optional[dict[str, Any]]:
        if event.type == EventType.STUDENT_SUBMISSION:
            await self._track_submission(event)
            return None
        elif event.type == EventType.ASSESSMENT_COMPLETE:
            return await self._analyze_engagement(event)
        elif event.type == EventType.STUDENT_MESSAGE:
            await self._track_activity(event)
            return None
        return None

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

    def _build_engagement_snapshot(self, engagement: LearnerEngagement, event: Event) -> dict[str, Any]:
        knowledge_id = event.data.get("knowledge_id", "")
        times = engagement.recent_response_times[-10:]
        speed_trend = "稳定"
        if len(times) >= 4:
            first_half = sum(times[: len(times) // 2]) / max(1, len(times) // 2)
            second_half = sum(times[len(times) // 2 :]) / max(1, len(times) // 2)
            if second_half > first_half * 1.3:
                speed_trend = "变慢（可能在犹豫）"
            elif second_half < first_half * 0.7:
                speed_trend = "变快（可能在猜测）"

        recent_topics = []
        for r in reversed(engagement.recent_results[-10:]):
            pass
        if knowledge_id:
            recent_topics.append(knowledge_id)

        return {
            "session_minutes": engagement.session_duration_minutes,
            "recent_accuracy": engagement.recent_accuracy,
            "consecutive_errors": engagement.consecutive_errors,
            "consecutive_correct": engagement.consecutive_correct,
            "speed_trend": speed_trend,
            "recent_topics": ", ".join(recent_topics) if recent_topics else "无",
        }

    async def _analyze_engagement(self, event: Event) -> dict[str, Any]:
        """分析参与度。"""
        engagement = self._get_engagement(event.learner_id)
        old_state = engagement.state

        snapshot = self._build_engagement_snapshot(engagement, event)

        new_state = old_state
        llm_suggestion = ""
        llm_reason = ""
        generation_mode = "local_policy"
        response = None
        if settings.enable_agent_llm_decisions:
            llm_service = get_llm_service()
            response = await llm_service.generate_engagement_assessment(snapshot)

        if response and response.content:
            try:
                import json
                parsed = json.loads(response.content)
                state_str = parsed.get("state", "").lower()
                valid_states = {s.value for s in LearningState}
                if state_str in valid_states:
                    new_state = LearningState(state_str)
                llm_suggestion = parsed.get("suggestion", "")
                llm_reason = parsed.get("reason", "")
                generation_mode = "remote_llm"
            except Exception:
                new_state = self._detect_state(engagement)
        else:
            new_state = self._detect_state(engagement)

        engagement.state = new_state
        engagement_strategy = {
            "state": new_state.value,
            "reason": llm_reason or self._local_reason(new_state, engagement),
            "suggestion": llm_suggestion or self._local_suggestion(new_state, engagement),
            "generation_mode": generation_mode,
            "recent_accuracy": round(engagement.recent_accuracy, 3),
            "consecutive_errors": engagement.consecutive_errors,
            "consecutive_correct": engagement.consecutive_correct,
        }

        await self.emit(
            EventType.EMOTION_DETECTED,
            event.learner_id,
            {"engagement_strategy": engagement_strategy},
            correlation_id=event.correlation_id,
        )

        if new_state != old_state:
            logger.info(
                "[EngagementAgent] learner=%s state: %s -> %s (llm=%s)",
                event.learner_id,
                old_state.value,
                new_state.value,
                bool(response and response.content),
            )

        # 生成干预
        needs_intervention = False
        intervention_type = ""

        if new_state == LearningState.FRUSTRATED:
            await self._intervene_frustration(event.learner_id, engagement, event.correlation_id, llm_suggestion)
            needs_intervention = True
            intervention_type = "encouragement"
        elif new_state == LearningState.BORED:
            await self._intervene_boredom(event.learner_id, engagement, event.correlation_id, llm_suggestion)
            needs_intervention = True
            intervention_type = "difficulty_adjustment"
        elif new_state == LearningState.FATIGUED:
            await self._intervene_fatigue(event.learner_id, engagement, event.correlation_id, llm_suggestion)
            needs_intervention = True
            intervention_type = "break_suggestion"
        elif new_state == LearningState.FOCUSED and engagement.consecutive_correct >= 3:
            await self._encourage(event.learner_id, engagement, event.correlation_id)

        return {
            "emotion_state": {
                "primary": new_state.value,
                "confidence": 0.8,
                "indicators": [],
            },
            "is_engaged": new_state == LearningState.FOCUSED,
            "needs_intervention": needs_intervention,
            "intervention_type": intervention_type,
            "engagement_strategy": engagement_strategy,
            "events": [],
        }

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

    def _local_reason(self, state: LearningState, engagement: LearnerEngagement) -> str:
        if state == LearningState.FRUSTRATED:
            return f"连续答错 {engagement.consecutive_errors} 次，可能出现挫败。"
        if state == LearningState.BORED:
            return "近期正确率高且连续答对，当前难度可能偏低。"
        if state == LearningState.FATIGUED:
            return "学习时间较长且正确率下降，可能需要休息。"
        if state == LearningState.STRUGGLING:
            return "刚出现错误，需要放慢一步确认规则。"
        if state == LearningState.IDLE:
            return "长时间无操作，可能暂时离开学习。"
        return "学习状态稳定。"

    def _local_suggestion(self, state: LearningState, engagement: LearnerEngagement) -> str:
        if state == LearningState.FRUSTRATED:
            return "降低难度，先给一个可完成的小步骤。"
        if state == LearningState.BORED:
            return "提高挑战度或推进到下一知识点。"
        if state == LearningState.FATIGUED:
            return "建议短暂休息后再继续。"
        if state == LearningState.STRUGGLING:
            return "提供提示并聚焦关键判断线索。"
        if state == LearningState.IDLE:
            return "用简短提醒帮助学习者回到任务。"
        return "保持当前节奏。"

    async def _intervene_frustration(
        self,
        learner_id: str,
        engagement: LearnerEngagement,
        correlation_id: str | None,
        llm_suggestion: str = "",
    ) -> None:
        message = llm_suggestion or "先别急着追求做对，我们先把这类题的关键判断点拆清楚，再继续往下做。"
        await self.emit(
            EventType.ENGAGEMENT_ALERT,
            learner_id,
            {
                "alert_type": "frustration",
                "consecutive_errors": engagement.consecutive_errors,
                "recent_accuracy": engagement.recent_accuracy,
                "message": message,
                "engagement_strategy": {
                    "state": LearningState.FRUSTRATED.value,
                    "suggestion": message,
                    "generation_mode": "remote_llm" if llm_suggestion else "local_policy",
                },
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
        llm_suggestion: str = "",
    ) -> None:
        message = llm_suggestion or "你这几题掌握得很稳，我们可以把难度再往上提一点，试试更有挑战的题型。"
        await self.emit(
            EventType.ENGAGEMENT_ALERT,
            learner_id,
            {
                "alert_type": "boredom",
                "consecutive_correct": engagement.consecutive_correct,
                "recent_accuracy": engagement.recent_accuracy,
                "message": message,
                "engagement_strategy": {
                    "state": LearningState.BORED.value,
                    "suggestion": message,
                    "generation_mode": "remote_llm" if llm_suggestion else "local_policy",
                },
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
        llm_suggestion: str = "",
    ) -> None:
        message = llm_suggestion or (
            f"你已经连续学习了 {engagement.session_duration_minutes:.0f} 分钟，"
            "可以先休息 10 分钟，再回来继续，效果通常会更好。"
        )
        await self.emit(
            EventType.ENCOURAGEMENT,
            learner_id,
            {
                "message": message,
                "type": "fatigue_break",
                "session_minutes": engagement.session_duration_minutes,
                "engagement_strategy": {
                    "state": LearningState.FATIGUED.value,
                    "suggestion": message,
                    "generation_mode": "remote_llm" if llm_suggestion else "local_policy",
                },
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
            "last_activity": engagement.last_activity.isoformat(),
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
        if state_data.get("last_activity"):
            engagement.last_activity = datetime.fromisoformat(state_data["last_activity"])
        if session_start:
            try:
                engagement.session_start = datetime.fromisoformat(session_start)
            except (ValueError, TypeError):
                pass
