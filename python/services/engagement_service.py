"""
Engagement Service。

封装参与度相关的业务逻辑。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from core.event_bus import Event, EventType

logger = logging.getLogger(__name__)


class EngagementService:
    """参与度业务逻辑层。"""

    def __init__(self) -> None:
        self._session_data: dict[str, dict] = {}  # learner_id -> session data

    async def analyze_engagement(
        self,
        learner_id: str,
        is_correct: bool,
        time_spent: float = 0,
        session_summary: Optional[dict] = None,
    ) -> dict:
        """分析参与度。"""
        # 获取或创建会话数据
        if learner_id not in self._session_data:
            self._session_data[learner_id] = {
                "recent_results": [],
                "recent_times": [],
                "last_activity": datetime.now(),
                "consecutive_wrong": 0,
                "total_time": 0,
            }

        session = self._session_data[learner_id]

        # 更新会话数据
        session["recent_results"].append(is_correct)
        session["recent_times"].append(time_spent)
        session["last_activity"] = datetime.now()
        session["total_time"] += time_spent

        # 保持最近20次记录
        session["recent_results"] = session["recent_results"][-20:]
        session["recent_times"] = session["recent_times"][-20:]

        # 更新连续错误计数
        if is_correct:
            session["consecutive_wrong"] = 0
        else:
            session["consecutive_wrong"] += 1

        # 分析情绪状态
        emotion_state = self._detect_emotion(session)

        # 判断是否需要干预
        needs_intervention = False
        intervention_type = ""

        if emotion_state["primary"] == "frustrated":
            needs_intervention = True
            intervention_type = "encouragement"
        elif emotion_state["primary"] == "bored":
            needs_intervention = True
            intervention_type = "difficulty_adjustment"
        elif emotion_state["primary"] == "fatigued":
            needs_intervention = True
            intervention_type = "break_suggestion"

        # 构建事件
        events = []
        if needs_intervention:
            events.append({
                "type": EventType.ENGAGEMENT_ALERT.value,
                "data": {
                    "emotion": emotion_state["primary"],
                    "intervention_type": intervention_type,
                },
            })

        return {
            "emotion_state": emotion_state,
            "is_engaged": emotion_state["primary"] == "engaged",
            "needs_intervention": needs_intervention,
            "intervention_type": intervention_type,
            "events": events,
        }

    def _detect_emotion(self, session: dict) -> dict:
        """检测情绪状态。"""
        recent_results = session["recent_results"]
        recent_times = session["recent_times"]
        consecutive_wrong = session["consecutive_wrong"]
        total_time = session["total_time"]

        # 检测挫败感：连续3次以上错误
        if consecutive_wrong >= 3:
            return {
                "primary": "frustrated",
                "confidence": 0.8,
                "indicators": [f"连续{consecutive_wrong}次错误"],
            }

        # 检测疲劳：单次学习超过15分钟
        if total_time > 900:  # 15分钟
            return {
                "primary": "fatigued",
                "confidence": 0.7,
                "indicators": ["学习时间过长"],
            }

        # 检测无聊：正确但时间过长
        if recent_times and recent_results:
            avg_time = sum(recent_times) / len(recent_times)
            accuracy = sum(recent_results) / len(recent_results)
            if accuracy > 0.8 and avg_time > 60:  # 正确率高但时间长
                return {
                    "primary": "bored",
                    "confidence": 0.6,
                    "indicators": ["正确但耗时较长"],
                }

        # 检测参与：最近5次中至少3次正确
        if len(recent_results) >= 5:
            recent_accuracy = sum(recent_results[-5:]) / 5
            if recent_accuracy >= 0.6:
                return {
                    "primary": "engaged",
                    "confidence": 0.7,
                    "indicators": ["参与度良好"],
                }

        # 默认中性
        return {
            "primary": "neutral",
            "confidence": 0.5,
            "indicators": [],
        }

    def get_session_summary(self, learner_id: str) -> dict:
        """获取会话摘要。"""
        session = self._session_data.get(learner_id, {})

        recent_results = session.get("recent_results", [])
        recent_times = session.get("recent_times", [])

        return {
            "total_questions": len(recent_results),
            "accuracy": sum(recent_results) / len(recent_results) if recent_results else 0,
            "avg_time_per_question": sum(recent_times) / len(recent_times) if recent_times else 0,
            "total_time_seconds": session.get("total_time", 0),
            "consecutive_wrong": session.get("consecutive_wrong", 0),
        }
