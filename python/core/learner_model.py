"""
学习者模型 -- 贝叶斯知识追踪 (BKT)。

每个学习者有一个持久化的知识状态模型，记录其对每个知识点的掌握程度。
使用贝叶斯知识追踪算法，通过学生的答题表现实时更新mastery概率。

面试要点：
- BKT 四个参数：P(L₀)初始掌握, P(T)转移, P(G)猜测, P(S)失误
- 为什么用Beta分布：能表达不确定性，(alpha, beta)参数对直觉友好
- 与 IRT（项目反应理论）的区别：BKT追踪动态变化，IRT是静态模型
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MasteryLevel(str, Enum):
    """掌握度等级（用于前端展示和课程规划）。"""

    NOT_STARTED = "not_started"  # 未学习
    BEGINNER = "beginner"  # 初学 (0 - 0.3)
    DEVELOPING = "developing"  # 发展中 (0.3 - 0.6)
    PROFICIENT = "proficient"  # 熟练 (0.6 - 0.85)
    MASTERED = "mastered"  # 掌握 (0.85 - 1.0)


class KnowledgeState(BaseModel):
    """单个知识点的掌握状态。"""

    knowledge_id: str
    mastery: float = 0.1  # P(L) 当前掌握概率
    alpha: float = 1.0  # Beta分布参数α（成功次数+1）
    beta: float = 9.0  # Beta分布参数β（失败次数+1）
    attempts: int = 0
    correct_count: int = 0
    last_attempt: datetime | None = None
    streak: int = 0  # 连续正确次数

    @property
    def level(self) -> MasteryLevel:
        if self.attempts == 0:
            return MasteryLevel.NOT_STARTED
        if self.mastery < 0.3:
            return MasteryLevel.BEGINNER
        if self.mastery < 0.6:
            return MasteryLevel.DEVELOPING
        if self.mastery < 0.85:
            return MasteryLevel.PROFICIENT
        return MasteryLevel.MASTERED

    @property
    def confidence(self) -> float:
        """置信度：数据越多，置信度越高。"""
        total = self.alpha + self.beta
        return min(1.0, total / 20.0)


class BKTParams(BaseModel):
    """贝叶斯知识追踪参数（可按知识点/学科调整）。"""

    p_init: float = 0.1  # P(L₀) 初始掌握概率
    p_transit: float = 0.15  # P(T) 每次练习后学会的概率
    p_guess: float = 0.2  # P(G) 猜对的概率
    p_slip: float = 0.1  # P(S) 失误的概率


class LearnerModel:
    """
    学习者知识模型，管理一个学生的所有知识点状态。

    核心方法：
    - update_mastery(): 根据答题结果更新mastery（BKT核心算法）
    - get_weak_points(): 获取薄弱知识点
    - get_ready_topics(): 获取可以学习的新知识点
    """

    def __init__(self, learner_id: str, bkt_params: BKTParams | None = None) -> None:
        self.learner_id = learner_id
        self.bkt = bkt_params or BKTParams()
        self.knowledge_states: dict[str, KnowledgeState] = {}
        self.session_start: datetime = datetime.now()
        self.total_interactions: int = 0
        self.metadata: dict[str, Any] = {}

    def get_state(self, knowledge_id: str) -> KnowledgeState:
        """获取某知识点的状态，不存在则创建。"""
        if knowledge_id not in self.knowledge_states:
            self.knowledge_states[knowledge_id] = KnowledgeState(
                knowledge_id=knowledge_id,
                mastery=self.bkt.p_init,
            )
        return self.knowledge_states[knowledge_id]

    def update_mastery(self, knowledge_id: str, is_correct: bool) -> KnowledgeState:
        """
        BKT 核心算法：根据答题结果更新 mastery 概率。

        数学推导：
          P(Lₙ|obs) = P(obs|Lₙ) × P(Lₙ) / P(obs)

          如果答对 (obs = correct):
            P(correct|L) = 1 - P(S)     # 会了且没失误
            P(correct|¬L) = P(G)         # 不会但猜对
            P(Lₙ|correct) = P(L)×(1-P(S)) / [P(L)×(1-P(S)) + (1-P(L))×P(G)]

          如果答错 (obs = wrong):
            P(wrong|L) = P(S)            # 会了但失误
            P(wrong|¬L) = 1 - P(G)      # 不会且没猜对
            P(Lₙ|wrong) = P(L)×P(S) / [P(L)×P(S) + (1-P(L))×(1-P(G))]

          学习转移（每次练习都可能学会）：
            P(Lₙ) = P(Lₙ|obs) + (1 - P(Lₙ|obs)) × P(T)
        """
        state = self.get_state(knowledge_id)
        p_l = state.mastery

        if is_correct:
            p_obs_given_l = 1 - self.bkt.p_slip
            p_obs_given_not_l = self.bkt.p_guess
            state.correct_count += 1
            state.streak += 1
            state.alpha += 1
        else:
            p_obs_given_l = self.bkt.p_slip
            p_obs_given_not_l = 1 - self.bkt.p_guess
            state.streak = 0
            state.beta += 1

        # 贝叶斯更新
        p_obs = p_l * p_obs_given_l + (1 - p_l) * p_obs_given_not_l
        p_l_given_obs = (p_l * p_obs_given_l) / p_obs if p_obs > 0 else p_l

        # 学习转移
        p_l_new = p_l_given_obs + (1 - p_l_given_obs) * self.bkt.p_transit

        state.mastery = max(0.0, min(1.0, p_l_new))
        state.attempts += 1
        state.last_attempt = datetime.now()
        self.total_interactions += 1

        logger.info(
            "[BKT] learner=%s, kp=%s, correct=%s, mastery: %.3f -> %.3f (%s)",
            self.learner_id,
            knowledge_id,
            is_correct,
            p_l,
            state.mastery,
            state.level.value,
        )
        return state

    def get_weak_points(self, threshold: float = 0.4, limit: int = 10) -> list[KnowledgeState]:
        """获取薄弱知识点（mastery低于阈值且已尝试过）。"""
        weak = [
            s for s in self.knowledge_states.values()
            if s.mastery < threshold and s.attempts > 0
        ]
        return sorted(weak, key=lambda s: s.mastery)[:limit]

    def get_strong_points(self, threshold: float = 0.85) -> list[KnowledgeState]:
        """获取已掌握的知识点。"""
        return [s for s in self.knowledge_states.values() if s.mastery >= threshold]

    def get_overall_progress(self) -> dict[str, Any]:
        """获取整体学习进度统计。"""
        states = list(self.knowledge_states.values())
        if not states:
            return {"total": 0, "avg_mastery": 0.0, "level_distribution": {}}

        level_dist = {}
        for s in states:
            level = s.level.value
            level_dist[level] = level_dist.get(level, 0) + 1

        return {
            "total_knowledge_points": len(states),
            "avg_mastery": sum(s.mastery for s in states) / len(states),
            "total_attempts": sum(s.attempts for s in states),
            "total_correct": sum(s.correct_count for s in states),
            "total_wrong": (
                sum(s.attempts for s in states) - sum(s.correct_count for s in states)
            ),
            "accuracy": (
                sum(s.correct_count for s in states) / max(1, sum(s.attempts for s in states))
            ),
            "level_distribution": level_dist,
        }

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（用于持久化）。"""
        return {
            "learner_id": self.learner_id,
            "knowledge_states": {
                kid: state.model_dump() for kid, state in self.knowledge_states.items()
            },
            "total_interactions": self.total_interactions,
            "session_start": self.session_start.isoformat(),
            "metadata": self.metadata,
        }

    async def save_to_db(self, session: Any) -> None:
        """
        将学习者状态保存到PostgreSQL。

        Args:
            session: AsyncSession 数据库会话
        """
        from sqlalchemy import select
        from models.database import Learner as LearnerDB
        from models.database import KnowledgeState as KnowledgeStateDB

        # 获取或创建Learner记录
        result = await session.execute(
            select(LearnerDB).where(LearnerDB.learner_id == self.learner_id)
        )
        learner_db = result.scalar_one_or_none()

        if learner_db is None:
            learner_db = LearnerDB(
                learner_id=self.learner_id,
                name=f"Learner {self.learner_id}",
                metadata_=self.metadata,
            )
            session.add(learner_db)
            await session.flush()

        # 保存所有知识点状态
        for kid, state in self.knowledge_states.items():
            result = await session.execute(
                select(KnowledgeStateDB).where(
                    KnowledgeStateDB.learner_id == self.learner_id,
                    KnowledgeStateDB.knowledge_id == kid,
                )
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                state_db = KnowledgeStateDB(
                    learner_id=self.learner_id,
                    knowledge_id=kid,
                    mastery=state.mastery,
                    alpha=state.alpha,
                    beta=state.beta,
                    attempts=state.attempts,
                    correct_count=state.correct_count,
                    streak=state.streak,
                    last_attempt=state.last_attempt,
                )
                session.add(state_db)
            else:
                existing.mastery = state.mastery
                existing.alpha = state.alpha
                existing.beta = state.beta
                existing.attempts = state.attempts
                existing.correct_count = state.correct_count
                existing.streak = state.streak
                existing.last_attempt = state.last_attempt

        await session.commit()
        logger.info("[LearnerModel] Saved learner %s to database", self.learner_id)

    @classmethod
    async def load_from_db(cls, session: Any, learner_id: str) -> Optional["LearnerModel"]:
        """
        从PostgreSQL加载学习者状态。

        Args:
            session: AsyncSession 数据库会话
            learner_id: 学习者ID

        Returns:
            LearnerModel 实例，如果不存在则返回None
        """
        from sqlalchemy import select
        from models.database import KnowledgeState as KnowledgeStateDB

        result = await session.execute(
            select(KnowledgeStateDB).where(KnowledgeStateDB.learner_id == learner_id)
        )
        rows = result.scalars().all()

        if not rows:
            return None

        model = cls(learner_id=learner_id)

        for row in rows:
            state = KnowledgeState(
                knowledge_id=row.knowledge_id,
                mastery=row.mastery,
                alpha=row.alpha,
                beta=row.beta,
                attempts=row.attempts,
                correct_count=row.correct_count,
                streak=row.streak,
                last_attempt=row.last_attempt,
            )
            model.knowledge_states[row.knowledge_id] = state

        model.total_interactions = sum(s.attempts for s in model.knowledge_states.values())

        logger.info("[LearnerModel] Loaded learner %s from database (%d knowledge points)",
                    learner_id, len(model.knowledge_states))
        return model

    def get_forgetting_curve(self, knowledge_id: str, days_since_last_review: float) -> float:
        """
        计算遗忘曲线状态。

        基于艾宾浩斯遗忘曲线：R = e^(-t/S)
        其中 R 是记忆保持率，t 是时间，S 是记忆强度

        Args:
            knowledge_id: 知识点ID
            days_since_last_review: 距离上次复习的天数

        Returns:
            当前记忆保持率 (0-1)
        """
        state = self.get_state(knowledge_id)

        # 记忆强度S与mastery正相关，与streak正相关
        # mastery越高、连续正确次数越多，记忆越牢固
        memory_strength = state.mastery * (1 + state.streak * 0.1)

        # 防止除零
        memory_strength = max(0.1, memory_strength)

        # 艾宾浩斯遗忘曲线公式
        retention = 2.71828 ** (-days_since_last_review / memory_strength)

        return max(0.0, min(1.0, retention))
