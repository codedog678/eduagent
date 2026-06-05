"""
Review API 路由。
"""

from fastapi import APIRouter

from services.curriculum_service import CurriculumService

router = APIRouter()

curriculum_service = CurriculumService()


@router.get("/schedule/{learner_id}")
async def get_review_schedule(learner_id: str):
    """获取复习计划。"""
    return await curriculum_service.get_review_schedule(learner_id)


@router.post("/complete")
async def complete_review(learner_id: str, knowledge_id: str, quality: int):
    """完成复习。"""
    return await curriculum_service.complete_review(
        learner_id=learner_id,
        knowledge_id=knowledge_id,
        quality=quality,
    )
