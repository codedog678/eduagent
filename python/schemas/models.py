"""
数据模型定义。

使用 Pydantic 定义 Agent 输入输出、API 请求响应等数据结构。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ──────────────────────────── Agent I/O 模型 ────────────────────────────


class AssessmentInput(BaseModel):
    """AssessmentAgent 输入。"""

    learner_id: str
    knowledge_id: str
    is_correct: bool
    time_spent_seconds: float = 0
    submission_context: dict[str, Any] = Field(default_factory=dict)


class MasteryUpdate(BaseModel):
    """掌握度更新。"""

    knowledge_id: str
    old_mastery: float
    new_mastery: float
    delta: float
    attempts: int
    correct_count: int
    streak: int
    confidence: float


class ErrorPattern(BaseModel):
    """错误模式。"""

    knowledge_id: str
    error_type: str  # "conceptual" | "procedural" | "careless"
    frequency: int
    description: str


class AssessmentOutput(BaseModel):
    """AssessmentAgent 输出。"""

    mastery_update: MasteryUpdate
    error_patterns: list[ErrorPattern] = Field(default_factory=list)
    is_weakness: bool = False
    is_strong_point: bool = False
    events: list[dict[str, Any]] = Field(default_factory=list)


class TutorInput(BaseModel):
    """TutorAgent 输入。"""

    learner_id: str
    knowledge_id: str
    question: str
    context: dict[str, Any] = Field(default_factory=dict)
    # context 可包含: submission, mastery, error_patterns, session_summary


class TutorOutput(BaseModel):
    """TutorAgent 输出。"""

    response: str
    explanation: str = ""
    encouragement: str = ""
    next_steps: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)
    is_socratic: bool = False  # 是否使用苏格拉底式提问
    events: list[dict[str, Any]] = Field(default_factory=list)


class CurriculumInput(BaseModel):
    """CurriculumAgent 输入。"""

    learner_id: str
    knowledge_id: str
    mastery: float
    is_weakness: bool = False
    context: dict[str, Any] = Field(default_factory=dict)


class ReviewRecommendation(BaseModel):
    """复习推荐。"""

    knowledge_id: str
    knowledge_name: str
    priority: str  # "high" | "medium" | "low"
    reason: str
    days_overdue: int = 0


class CurriculumOutput(BaseModel):
    """CurriculumAgent 输出。"""

    next_topics: list[dict[str, Any]] = Field(default_factory=list)
    review_schedule: list[ReviewRecommendation] = Field(default_factory=list)
    learning_path: list[str] = Field(default_factory=list)
    remedial_path: list[str] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


class EngagementInput(BaseModel):
    """EngagementAgent 输入。"""

    learner_id: str
    is_correct: bool
    time_spent_seconds: float = 0
    session_summary: dict[str, Any] = Field(default_factory=dict)


class EmotionState(BaseModel):
    """情绪状态。"""

    primary: str  # "neutral" | "frustrated" | "bored" | "fatigued" | "idle" | "engaged"
    confidence: float = 0.8
    indicators: list[str] = Field(default_factory=list)


class EngagementOutput(BaseModel):
    """EngagementAgent 输出。"""

    emotion_state: EmotionState
    is_engaged: bool = True
    needs_intervention: bool = False
    intervention_type: str = ""  # "encouragement" | "break_suggestion" | "difficulty_adjustment"
    events: list[dict[str, Any]] = Field(default_factory=list)


class FeedbackInput(BaseModel):
    """FeedbackAgent 输入。"""

    learner_id: str
    knowledge_id: str
    assessment: AssessmentOutput
    tutor: Optional[TutorOutput] = None
    engagement: Optional[EngagementOutput] = None
    context: dict[str, Any] = Field(default_factory=dict)


class FeedbackOutput(BaseModel):
    """FeedbackAgent 输出。"""

    summary: str
    detailed_feedback: str
    encouragement: str
    next_steps: list[str] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


# ──────────────────────────── API 请求模型 ────────────────────────────


class SubmitAnswerRequest(BaseModel):
    """提交答案请求。"""

    learner_id: str
    knowledge_id: str
    is_correct: bool
    time_spent_seconds: float = 0


class AskQuestionRequest(BaseModel):
    """提问请求。"""

    learner_id: str
    knowledge_id: str
    question: str


class SendMessageRequest(BaseModel):
    """发送消息请求。"""

    learner_id: str
    message: str
    knowledge_id: str = "general"


class GenerateQuizRequest(BaseModel):
    """生成题目请求。"""

    knowledge_id: str
    difficulty: float = 0.5


class SubmitQuizAnswerRequest(BaseModel):
    """提交测验答案请求。"""

    learner_id: str
    knowledge_id: str
    question: str
    student_answer: str
    correct_answer: str = ""
    explanation: str = ""
    time_spent_seconds: float = 0


# ──────────────────────────── API 响应模型 ────────────────────────────


class AgentResponse(BaseModel):
    """Agent 响应。"""

    status: str = "ok"
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)


class InteractionResult(BaseModel):
    """一次交互的完整结果。"""

    status: str = "ok"
    assessment: Optional[AssessmentOutput] = None
    tutor: Optional[TutorOutput] = None
    curriculum: Optional[CurriculumOutput] = None
    engagement: Optional[EngagementOutput] = None
    feedback: Optional[FeedbackOutput] = None
    events: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
