"""
分析数据模型。

定义学习分析所需的数据结构。
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class KnowledgeDistribution(BaseModel):
    """知识点掌握度分布。"""
    not_started: int = 0  # 未学习
    beginner: int = 0  # 初学 (0 - 0.3)
    developing: int = 0  # 发展中 (0.3 - 0.6)
    proficient: int = 0  # 熟练 (0.6 - 0.85)
    mastered: int = 0  # 掌握 (0.85 - 1.0)

    @property
    def total(self) -> int:
        return self.not_started + self.beginner + self.developing + self.proficient + self.mastered


class LearningTimeline(BaseModel):
    """学习时间线数据点。"""
    timestamp: str
    event_type: str
    knowledge_id: Optional[str] = None
    mastery: Optional[float] = None
    is_correct: Optional[bool] = None


class LearningAnalytics(BaseModel):
    """学习分析数据。"""
    learner_id: str
    total_sessions: int = 0
    total_time_spent_seconds: float = 0.0
    total_questions: int = 0
    correct_answers: int = 0
    wrong_answers: int = 0
    hints_used: int = 0
    knowledge_points_covered: list[str] = Field(default_factory=list)
    avg_time_per_question: float = 0.0
    accuracy: float = 0.0
    last_activity: Optional[str] = None


class WeakPoint(BaseModel):
    """薄弱知识点。"""
    knowledge_id: str
    mastery: float
    attempts: int
    correct_count: int
    accuracy: float


class ReviewSchedule(BaseModel):
    """复习计划。"""
    knowledge_id: str
    next_review: str
    interval_days: float
    easiness_factor: float
    retention: Optional[float] = None  # 记忆保持率


class AnalyticsDashboard(BaseModel):
    """分析仪表板数据。"""
    analytics: LearningAnalytics
    knowledge_distribution: KnowledgeDistribution
    weak_points: list[WeakPoint]
    review_schedule: list[ReviewSchedule]
    learning_curve: list[LearningTimeline]
    overall_stats: dict[str, Any] = Field(default_factory=dict)
