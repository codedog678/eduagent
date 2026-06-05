"""
Learner Repository。

封装学习者相关的数据库操作。
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import Learner, KnowledgeState
from models.session import async_session

logger = logging.getLogger(__name__)


class LearnerRepository:
    """学习者数据访问层。"""

    async def get_or_create(self, learner_id: str, name: str = "") -> Learner:
        """获取或创建学习者。"""
        async with async_session() as session:
            learner = await session.get(Learner, learner_id)
            if learner is None:
                learner = Learner(
                    id=learner_id,
                    name=name or f"Learner_{learner_id[:8]}",
                    level="beginner",
                    preferences={},
                )
                session.add(learner)
                await session.commit()
                await session.refresh(learner)
                logger.info("Created learner: %s", learner_id)
            return learner

    async def get(self, learner_id: str) -> Optional[Learner]:
        """获取学习者。"""
        async with async_session() as session:
            return await session.get(Learner, learner_id)

    async def update_level(self, learner_id: str, level: str) -> None:
        """更新学习者等级。"""
        async with async_session() as session:
            learner = await session.get(Learner, learner_id)
            if learner:
                learner.level = level
                await session.commit()

    async def get_knowledge_states(self, learner_id: str) -> list[KnowledgeState]:
        """获取学习者所有知识点状态。"""
        async with async_session() as session:
            result = await session.execute(
                select(KnowledgeState).where(KnowledgeState.learner_id == learner_id)
            )
            return list(result.scalars().all())

    async def get_knowledge_state(
        self, learner_id: str, knowledge_id: str
    ) -> Optional[KnowledgeState]:
        """获取学习者特定知识点状态。"""
        async with async_session() as session:
            result = await session.execute(
                select(KnowledgeState).where(
                    KnowledgeState.learner_id == learner_id,
                    KnowledgeState.knowledge_id == knowledge_id,
                )
            )
            return result.scalar_one_or_none()

    async def upsert_knowledge_state(
        self,
        learner_id: str,
        knowledge_id: str,
        mastery: float = 0.0,
        attempts: int = 0,
        correct_count: int = 0,
        streak: int = 0,
        confidence: float = 0.5,
    ) -> KnowledgeState:
        """更新或插入知识点状态。"""
        async with async_session() as session:
            result = await session.execute(
                select(KnowledgeState).where(
                    KnowledgeState.learner_id == learner_id,
                    KnowledgeState.knowledge_id == knowledge_id,
                )
            )
            state = result.scalar_one_or_none()

            if state is None:
                state = KnowledgeState(
                    learner_id=learner_id,
                    knowledge_id=knowledge_id,
                    mastery=mastery,
                    attempts=attempts,
                    correct_count=correct_count,
                    streak=streak,
                    confidence=confidence,
                )
                session.add(state)
            else:
                state.mastery = mastery
                state.attempts = attempts
                state.correct_count = correct_count
                state.streak = streak
                state.confidence = confidence

            await session.commit()
            await session.refresh(state)
            return state
