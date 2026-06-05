"""
Learner API 路由。
"""

from fastapi import APIRouter

from schemas.models import SubmitAnswerRequest, AskQuestionRequest, SendMessageRequest
from services.learner_service import LearnerService
from services.assessment_service import AssessmentService
from services.tutor_service import TutorService
from services.engagement_service import EngagementService
from services.feedback_service import FeedbackService
from services.session_service import SessionService

router = APIRouter()

# 服务实例
learner_service = LearnerService()
assessment_service = AssessmentService()
tutor_service = TutorService()
engagement_service = EngagementService()
feedback_service = FeedbackService()
session_service = SessionService()


@router.post("/init")
async def init_demo_data(learner_id: str):
    """初始化演示数据。"""
    await learner_service.get_or_create_learner(learner_id)
    return {"status": "ok", "message": f"Demo data seeded for {learner_id}"}


@router.get("/progress/{learner_id}")
async def get_progress(learner_id: str):
    """获取学习进度。"""
    return await learner_service.get_progress(learner_id)


@router.post("/submit")
async def submit_answer(req: SubmitAnswerRequest):
    """提交答案。"""
    # 开始会话（如果没有）
    session_service.start_session(req.learner_id)

    # 评估
    assessment = await assessment_service.submit_answer(
        learner_id=req.learner_id,
        knowledge_id=req.knowledge_id,
        is_correct=req.is_correct,
        time_spent=req.time_spent_seconds,
    )

    # 参与度分析
    engagement = await engagement_service.analyze_engagement(
        learner_id=req.learner_id,
        is_correct=req.is_correct,
        time_spent=req.time_spent_seconds,
    )

    # 生成反馈
    feedback = await feedback_service.generate_feedback(
        learner_id=req.learner_id,
        knowledge_id=req.knowledge_id,
        assessment=assessment,
        engagement=engagement,
    )

    # 收集所有事件
    all_events = []
    all_events.extend(assessment.get("events", []))
    all_events.extend(engagement.get("events", []))
    all_events.extend(feedback.get("events", []))

    return {
        "status": "ok",
        "assessment": assessment,
        "engagement": engagement,
        "feedback": feedback,
        "events": all_events,
    }


@router.post("/question")
async def ask_question(req: AskQuestionRequest):
    """提问。"""
    result = await tutor_service.ask_question(
        learner_id=req.learner_id,
        knowledge_id=req.knowledge_id,
        question=req.question,
    )
    return {"status": "ok", **result}


@router.post("/message")
async def send_message(req: SendMessageRequest):
    """发送消息。"""
    result = await tutor_service.ask_question(
        learner_id=req.learner_id,
        knowledge_id=req.knowledge_id,
        question=req.message,
    )
    return {"status": "ok", **result}
