"""
记忆管理器 -- 管理学习者模型的加载、缓存和持久化。

核心职责：
1. 管理 LearnerModel 的内存缓存和数据库同步
2. 提供统一的状态访问接口

设计原则：
- 缓存优先：优先从内存获取，缓存未命中则查询数据库
- 懒加载：首次访问时才加载
"""

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.learner_model import LearnerModel
from models.database import KnowledgeState as KnowledgeStateDB
from models.database import Learner as LearnerDB

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器：管理学习者模型的缓存与持久化。

    使用方法：
        memory = MemoryManager()
        model = await memory.get_or_load("student_001")
        # ... 使用 model ...
        await memory.save("student_001")
    """

    def __init__(self) -> None:
        self._cache: dict[str, LearnerModel] = {}

    async def get_or_load(self, learner_id: str, session: AsyncSession | None = None) -> LearnerModel:
        """
        获取学习者模型，优先从缓存获取，缓存未命中则从数据库加载。

        Args:
            learner_id: 学习者ID
            session: 可选的数据库会话，如果不提供则创建新会话

        Returns:
            LearnerModel 实例
        """
        if learner_id in self._cache:
            return self._cache[learner_id]

        try:
            model = await self._load_learner_from_db(learner_id, session)
            if model is None:
                model = LearnerModel(learner_id)
                logger.info("[MemoryManager] Created new learner model: %s", learner_id)
            else:
                logger.info("[MemoryManager] Loaded learner %s from database (%d knowledge points)",
                            learner_id, len(model.knowledge_states))
        except Exception as e:
            model = LearnerModel(learner_id)
            logger.warning("[MemoryManager] Database unavailable, created new model for %s: %s", learner_id, e)

        self._cache[learner_id] = model
        return model

    async def _load_learner_from_db(
        self, learner_id: str, session: AsyncSession | None = None
    ) -> Optional[LearnerModel]:
        """从数据库加载学习者状态。"""
        from models.session import async_session as session_factory

        async def _load(sess: AsyncSession) -> Optional[LearnerModel]:
            result = await sess.execute(
                select(KnowledgeStateDB).where(KnowledgeStateDB.learner_id == learner_id)
            )
            rows = result.scalars().all()

            if not rows:
                return None

            model = LearnerModel(learner_id=learner_id)
            for row in rows:
                state = model.get_state(row.knowledge_id)
                state.mastery = row.mastery
                state.alpha = row.alpha
                state.beta = row.beta
                state.attempts = row.attempts
                state.correct_count = row.correct_count
                state.streak = row.streak
                state.last_attempt = row.last_attempt

            return model

        if session:
            return await _load(session)

        async with session_factory() as sess:
            return await _load(sess)

    async def save(self, learner_id: str, session: AsyncSession | None = None) -> None:
        """
        保存学习者状态到数据库。

        Args:
            learner_id: 学习者ID
            session: 可选的数据库会话
        """
        if learner_id not in self._cache:
            return

        model = self._cache[learner_id]

        from models.session import async_session as session_factory

        async def _save(sess: AsyncSession) -> None:
            result = await sess.execute(
                select(LearnerDB).where(LearnerDB.learner_id == learner_id)
            )
            learner_db = result.scalar_one_or_none()

            if learner_db is None:
                learner_db = LearnerDB(
                    learner_id=learner_id,
                    name=f"Learner {learner_id}",
                    metadata_=model.metadata,
                )
                sess.add(learner_db)
                await sess.flush()

            for kid, state in model.knowledge_states.items():
                result = await sess.execute(
                    select(KnowledgeStateDB).where(
                        KnowledgeStateDB.learner_id == learner_id,
                        KnowledgeStateDB.knowledge_id == kid,
                    )
                )
                existing = result.scalar_one_or_none()

                if existing is None:
                    state_db = KnowledgeStateDB(
                        learner_id=learner_id,
                        knowledge_id=kid,
                        mastery=state.mastery,
                        alpha=state.alpha,
                        beta=state.beta,
                        attempts=state.attempts,
                        correct_count=state.correct_count,
                        streak=state.streak,
                        last_attempt=state.last_attempt,
                    )
                    sess.add(state_db)
                else:
                    existing.mastery = state.mastery
                    existing.alpha = state.alpha
                    existing.beta = state.beta
                    existing.attempts = state.attempts
                    existing.correct_count = state.correct_count
                    existing.streak = state.streak
                    existing.last_attempt = state.last_attempt

            await sess.commit()
            logger.info("[MemoryManager] Saved learner %s to database", learner_id)

        try:
            if session:
                await _save(session)
            else:
                async with session_factory() as sess:
                    await _save(sess)
        except Exception as e:
            logger.warning("[MemoryManager] Failed to save learner %s to database: %s", learner_id, e)
