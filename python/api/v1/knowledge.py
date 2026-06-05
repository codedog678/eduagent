"""
Knowledge API 路由。
"""

from fastapi import APIRouter

from repositories.knowledge_repo import KnowledgeRepository

router = APIRouter()

knowledge_repo = KnowledgeRepository()


@router.get("/graph")
async def get_knowledge_graph():
    """获取知识图谱。"""
    return knowledge_repo.get_graph_data()


@router.get("/node/{node_id}")
async def get_knowledge_node(node_id: str):
    """获取知识点详情。"""
    node = knowledge_repo.get_node(node_id)
    if node is None:
        return {"error": "Knowledge node not found"}

    return {
        "id": node.id,
        "name": node.name,
        "subject": node.subject,
        "difficulty": node.difficulty,
        "description": node.description,
        "prerequisites": node.prerequisites,
        "tags": node.tags,
    }


@router.get("/ready/{learner_id}")
async def get_ready_nodes(learner_id: str):
    """获取可学习的知识点。"""
    from services.learner_service import LearnerService

    learner_service = LearnerService()
    model = await learner_service.get_learner_model(learner_id)
    mastered_ids = model.get_mastered_knowledge_ids()

    ready_nodes = knowledge_repo.get_ready_nodes(mastered_ids)

    return {
        "ready_nodes": [
            {
                "id": node_id,
                "name": knowledge_repo.get_node(node_id).name,
                "difficulty": knowledge_repo.get_node(node_id).difficulty,
            }
            for node_id in ready_nodes
            if knowledge_repo.get_node(node_id)
        ],
    }
