"""
Learning API 路由。
"""

from fastapi import APIRouter

from services.curriculum_service import CurriculumService
from services.learner_service import LearnerService

router = APIRouter()

curriculum_service = CurriculumService()
learner_service = LearnerService()


@router.get("/path/{learner_id}/{knowledge_id}")
async def get_learning_path(learner_id: str, knowledge_id: str):
    """获取学习路径。"""
    model = await learner_service.get_learner_model(learner_id)
    mastered_ids = model.get_mastered_knowledge_ids()

    from repositories.knowledge_repo import KnowledgeRepository
    knowledge_repo = KnowledgeRepository()

    path = knowledge_repo.get_learning_path(knowledge_id, mastered_ids)

    return {
        "target": knowledge_id,
        "path": path,
        "mastered": list(mastered_ids),
    }


@router.post("/recommend/{learner_id}")
async def recommend_next(learner_id: str, knowledge_id: str):
    """推荐下一个学习主题。"""
    model = await learner_service.get_learner_model(learner_id)
    mastery = model.get_mastery(knowledge_id)
    is_weakness = mastery < 0.4

    result = await curriculum_service.get_next_topics(
        learner_id=learner_id,
        knowledge_id=knowledge_id,
        mastery=mastery,
        is_weakness=is_weakness,
    )

    return result
