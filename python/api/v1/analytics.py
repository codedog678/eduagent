"""
Analytics API 路由。
"""

from fastapi import APIRouter

from services.learner_service import LearnerService
from services.engagement_service import EngagementService
from repositories.learning_record_repo import LearningRecordRepository

router = APIRouter()

learner_service = LearnerService()
engagement_service = EngagementService()
record_repo = LearningRecordRepository()


@router.get("/overview")
async def get_analytics_overview():
    """获取总览统计。"""
    try:
        from models.database import Learner, LearningRecord
        from models.session import async_session
        from sqlalchemy import func, select

        async with async_session() as session:
            total_learners = await session.scalar(select(func.count(Learner.id)))
            total_questions = await session.scalar(select(func.count(LearningRecord.id)))
            total_correct = await session.scalar(
                select(func.count(LearningRecord.id)).where(LearningRecord.is_correct == True)
            )

            accuracy = 0.0
            if total_questions:
                accuracy = total_correct / total_questions

            return {
                "total_learners": total_learners or 0,
                "total_questions": total_questions or 0,
                "total_correct_answers": total_correct or 0,
                "overall_accuracy": round(accuracy, 3),
            }
    except Exception as exc:
        return {
            "total_learners": 0,
            "total_questions": 0,
            "total_correct_answers": 0,
            "overall_accuracy": 0.0,
            "error": str(exc),
        }


@router.get("/{learner_id}")
async def get_analytics(learner_id: str):
    """获取学习者分析。"""
    # 获取进度
    progress = await learner_service.get_progress(learner_id)

    # 获取薄弱点
    weak_points = await learner_service.get_weak_points(learner_id)

    # 获取学习曲线
    learning_curve = await record_repo.get_learning_curve(learner_id)

    # 获取会话摘要
    session_summary = engagement_service.get_session_summary(learner_id)

    # 获取提示使用次数
    from services.tutor_service import TutorService
    tutor_service = TutorService()
    hints_used = tutor_service.get_hint_usage(learner_id)

    # 计算统计
    total_questions = progress.get("total_attempts", 0)
    total_time = session_summary.get("total_time_seconds", 0)

    return {
        "analytics": {
            "learner_id": learner_id,
            "total_sessions": 1 if total_questions else 0,
            "total_time_spent_minutes": round(total_time / 60, 1),
            "total_questions": total_questions,
            "correct_answers": progress.get("total_correct", 0),
            "wrong_answers": progress.get("total_wrong", 0),
            "accuracy": progress.get("accuracy", 0.0),
            "hints_used": hints_used,
            "avg_time_per_question": round(total_time / total_questions, 1) if total_questions else 0.0,
        },
        "knowledge_distribution": progress.get("level_distribution", {}),
        "weak_points": weak_points,
        "learning_curve": learning_curve,
    }
