"""
Learner Service。

封装学习者相关的业务逻辑。
"""

import logging
from typing import Optional

from core.learner_model import LearnerModel
from repositories.learner_repo import LearnerRepository
from repositories.knowledge_repo import KnowledgeRepository

logger = logging.getLogger(__name__)


class LearnerService:
    """学习者业务逻辑层。"""

    def __init__(self) -> None:
        self.learner_repo = LearnerRepository()
        self.knowledge_repo = KnowledgeRepository()
        self._learner_models: dict[str, LearnerModel] = {}

    async def get_or_create_learner(
        self, learner_id: str, name: str = ""
    ) -> dict:
        """获取或创建学习者。"""
        learner = await self.learner_repo.get_or_create(learner_id, name)
        return {
            "id": learner.id,
            "name": learner.name,
            "level": learner.level,
        }

    async def get_learner_model(self, learner_id: str) -> LearnerModel:
        """获取学习者模型（带缓存）。"""
        if learner_id not in self._learner_models:
            model = LearnerModel(learner_id=learner_id)

            # 从数据库恢复状态
            states = await self.learner_repo.get_knowledge_states(learner_id)
            for state in states:
                model.update_knowledge_state(
                    state.knowledge_id,
                    mastery=state.mastery,
                    attempts=state.attempts,
                    correct_count=state.correct_count,
                    streak=state.streak,
                    confidence=state.confidence,
                )

            self._learner_models[learner_id] = model

        return self._learner_models[learner_id]

    async def update_mastery(
        self,
        learner_id: str,
        knowledge_id: str,
        is_correct: bool,
        time_spent: float = 0,
    ) -> dict:
        """更新掌握度。"""
        model = await self.get_learner_model(learner_id)
        old_mastery = model.get_mastery(knowledge_id)
        model.update(knowledge_id, is_correct, time_spent)
        new_mastery = model.get_mastery(knowledge_id)

        # 持久化到数据库
        state = model.knowledge_states.get(knowledge_id)
        if state:
            await self.learner_repo.upsert_knowledge_state(
                learner_id=learner_id,
                knowledge_id=knowledge_id,
                mastery=state.mastery,
                attempts=state.attempts,
                correct_count=state.correct_count,
                streak=state.streak,
                confidence=state.confidence,
            )

        return {
            "knowledge_id": knowledge_id,
            "old_mastery": old_mastery,
            "new_mastery": new_mastery,
            "delta": new_mastery - old_mastery,
            "attempts": state.attempts if state else 0,
            "correct_count": state.correct_count if state else 0,
            "streak": state.streak if state else 0,
            "confidence": state.confidence if state else 0.5,
        }

    async def get_progress(self, learner_id: str) -> dict:
        """获取学习进度。"""
        model = await self.get_learner_model(learner_id)
        return model.get_overall_progress()

    async def get_weak_points(
        self, learner_id: str, threshold: float = 0.4, limit: int = 5
    ) -> list[dict]:
        """获取薄弱知识点。"""
        model = await self.get_learner_model(learner_id)
        weak_points = model.get_weak_points(threshold, limit)
        return [
            {
                "knowledge_id": state.knowledge_id,
                "mastery": state.mastery,
                "attempts": state.attempts,
                "correct_count": state.correct_count,
            }
            for state in weak_points
        ]

    async def get_strong_points(
        self, learner_id: str, threshold: float = 0.8, limit: int = 5
    ) -> list[dict]:
        """获取强项知识点。"""
        model = await self.get_learner_model(learner_id)
        strong_points = model.get_strong_points(threshold, limit)
        return [
            {
                "knowledge_id": state.knowledge_id,
                "mastery": state.mastery,
                "attempts": state.attempts,
                "correct_count": state.correct_count,
            }
            for state in strong_points
        ]
