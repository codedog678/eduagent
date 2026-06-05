"""
数据模型定义。

使用 Pydantic 定义 Agent 输入输出、API 请求响应等数据结构。
"""

from schemas.models import (
    # Agent I/O
    AssessmentInput,
    AssessmentOutput,
    TutorInput,
    TutorOutput,
    CurriculumInput,
    CurriculumOutput,
    EngagementInput,
    EngagementOutput,
    FeedbackInput,
    FeedbackOutput,
    # API
    SubmitAnswerRequest,
    AskQuestionRequest,
    SendMessageRequest,
    GenerateQuizRequest,
    SubmitQuizAnswerRequest,
    # Responses
    AgentResponse,
    InteractionResult,
)

__all__ = [
    "AssessmentInput",
    "AssessmentOutput",
    "TutorInput",
    "TutorOutput",
    "CurriculumInput",
    "CurriculumOutput",
    "EngagementInput",
    "EngagementOutput",
    "FeedbackInput",
    "FeedbackOutput",
    "SubmitAnswerRequest",
    "AskQuestionRequest",
    "SendMessageRequest",
    "GenerateQuizRequest",
    "SubmitQuizAnswerRequest",
    "AgentResponse",
    "InteractionResult",
]
