"""
记忆管理器 -- 统一管理学习者状态的加载、缓存和持久化。

核心职责：
1. 管理 LearnerModel 的内存缓存和数据库同步
2. 管理各 Agent 的状态持久化（尝试次数、行为窗口等）
3. 提供统一的状态访问接口

设计原则：
- 缓存优先：优先从内存获取，缓存未命中则查询数据库
- 懒加载：首次访问时才加载
- 统一保存：提供批量保存接口，减少数据库调用
"""

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.learner_model import LearnerModel
from models.database import AgentState as AgentStateDB
from models.database import KnowledgeState as KnowledgeStateDB
from models.database import Learner as LearnerDB

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器：统一管理所有学习者状态。

    使用方法：
        memory = MemoryManager()
        model = await memory.get_or_load("student_001")
        # ... 使用 model ...
        await memory.save("student_001")
    """

    def __init__(self) -> None:
        self._cache: dict[str, LearnerModel] = {}
        self._agent_states: dict[str, dict[str, dict]] = {}  # {agent_name: {learner_id: state_data}}
        self._dirty_learners: set[str] = set()  # 需要保存的学习者
        self._dirty_agents: set[tuple[str, str]] = set()  # (agent_name, learner_id)

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

        # 从数据库加载（如果可用）
        try:
            model = await self._load_learner_from_db(learner_id, session)
            if model is None:
                model = LearnerModel(learner_id)
                logger.info("[MemoryManager] Created new learner model: %s", learner_id)
            else:
                logger.info("[MemoryManager] Loaded learner %s from database (%d knowledge points)",
                            learner_id, len(model.knowledge_states))
        except Exception as e:
            # 数据库不可用时，创建空白模型
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

    def mark_dirty(self, learner_id: str) -> None:
        """标记学习者状态需要保存。"""
        self._dirty_learners.add(learner_id)

    def mark_agent_dirty(self, agent_name: str, learner_id: str) -> None:
        """标记 Agent 状态需要保存。"""
        self._dirty_agents.add((agent_name, learner_id))

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
            # 获取或创建 Learner 记录
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

            # 保存所有知识点状态
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
            self._dirty_learners.discard(learner_id)
            logger.info("[MemoryManager] Saved learner %s to database", learner_id)

        try:
            if session:
                await _save(session)
            else:
                async with session_factory() as sess:
                    await _save(sess)
        except Exception as e:
            logger.warning("[MemoryManager] Failed to save learner %s to database: %s", learner_id, e)

    async def save_all(self) -> None:
        """批量保存所有脏数据。"""
        if not self._dirty_learners and not self._dirty_agents:
            return

        from models.session import async_session as session_factory

        async with session_factory() as session:
            # 保存学习者状态
            for learner_id in list(self._dirty_learners):
                await self.save(learner_id, session)

            # 保存 Agent 状态
            for agent_name, learner_id in list(self._dirty_agents):
                await self.save_agent_state(agent_name, learner_id, session)

        logger.info("[MemoryManager] Saved all dirty data")

    def get_agent_state(self, agent_name: str, learner_id: str) -> dict:
        """
        获取 Agent 的特定状态。

        Args:
            agent_name: Agent 名称
            learner_id: 学习者ID

        Returns:
            Agent 状态字典，不存在则返回空字典
        """
        return self._agent_states.get(agent_name, {}).get(learner_id, {})

    def set_agent_state(self, agent_name: str, learner_id: str, state_data: dict) -> None:
        """
        设置 Agent 的特定状态。

        Args:
            agent_name: Agent 名称
            learner_id: 学习者ID
            state_data: 状态数据
        """
        if agent_name not in self._agent_states:
            self._agent_states[agent_name] = {}
        self._agent_states[agent_name][learner_id] = state_data
        self.mark_agent_dirty(agent_name, learner_id)

    async def load_agent_state(self, agent_name: str, learner_id: str, session: AsyncSession | None = None) -> dict:
        """
        从数据库加载 Agent 状态。

        Args:
            agent_name: Agent 名称
            learner_id: 学习者ID
            session: 可选的数据库会话

        Returns:
            Agent 状态字典
        """
        if agent_name in self._agent_states and learner_id in self._agent_states[agent_name]:
            return self._agent_states[agent_name][learner_id]

        from models.session import async_session as session_factory

        async def _load(sess: AsyncSession) -> dict:
            result = await sess.execute(
                select(AgentStateDB).where(
                    AgentStateDB.agent_name == agent_name,
                    AgentStateDB.learner_id == learner_id,
                )
            )
            row = result.scalar_one_or_none()
            if row:
                return row.state_data or {}
            return {}

        try:
            if session:
                state_data = await _load(session)
            else:
                async with session_factory() as sess:
                    state_data = await _load(sess)
        except Exception as e:
            logger.warning("[MemoryManager] Failed to load agent state %s/%s: %s", agent_name, learner_id, e)
            state_data = {}

        # 更新缓存
        if agent_name not in self._agent_states:
            self._agent_states[agent_name] = {}
        self._agent_states[agent_name][learner_id] = state_data

        return state_data

    async def save_agent_state(
        self, agent_name: str, learner_id: str, session: AsyncSession | None = None
    ) -> None:
        """
        保存 Agent 状态到数据库。

        Args:
            agent_name: Agent 名称
            learner_id: 学习者ID
            session: 可选的数据库会话
        """
        if agent_name not in self._agent_states or learner_id not in self._agent_states[agent_name]:
            return

        state_data = self._agent_states[agent_name][learner_id]

        from models.session import async_session as session_factory

        async def _save(sess: AsyncSession) -> None:
            result = await sess.execute(
                select(AgentStateDB).where(
                    AgentStateDB.agent_name == agent_name,
                    AgentStateDB.learner_id == learner_id,
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                state_db = AgentStateDB(
                    agent_name=agent_name,
                    learner_id=learner_id,
                    state_data=state_data,
                )
                sess.add(state_db)
            else:
                existing.state_data = state_data
                existing.updated_at = datetime.now()

            await sess.commit()
            self._dirty_agents.discard((agent_name, learner_id))
            logger.debug("[MemoryManager] Saved agent state: %s/%s", agent_name, learner_id)

        try:
            if session:
                await _save(session)
            else:
                async with session_factory() as sess:
                    await _save(sess)
        except Exception as e:
            logger.warning("[MemoryManager] Failed to save agent state %s/%s: %s", agent_name, learner_id, e)

    def clear_cache(self, learner_id: str | None = None) -> None:
        """
        清除缓存。

        Args:
            learner_id: 如果指定，只清除该学习者的缓存；否则清除所有缓存
        """
        if learner_id:
            self._cache.pop(learner_id, None)
            for agent_states in self._agent_states.values():
                agent_states.pop(learner_id, None)
        else:
            self._cache.clear()
            self._agent_states.clear()

        logger.info("[MemoryManager] Cache cleared for %s", learner_id or "all learners")

    def get_cache_stats(self) -> dict[str, Any]:
        """获取缓存统计信息。"""
        return {
            "cached_learners": len(self._cache),
            "cached_agent_states": sum(len(states) for states in self._agent_states.values()),
            "dirty_learners": len(self._dirty_learners),
            "dirty_agents": len(self._dirty_agents),
        }
