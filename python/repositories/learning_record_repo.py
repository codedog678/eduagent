"""
Learning Record Repository。

封装学习记录相关的数据库操作。
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import LearningRecord
from models.session import async_session

logger = logging.getLogger(__name__)


class LearningRecordRepository:
    """学习记录数据访问层。"""

    async def create(
        self,
        learner_id: str,
        knowledge_id: str,
        is_correct: bool,
        time_spent_seconds: float = 0,
        question: str = "",
        student_answer: str = "",
        correct_answer: str = "",
        feedback: str = "",
    ) -> LearningRecord:
        """创建学习记录。"""
        async with async_session() as session:
            record = LearningRecord(
                learner_id=learner_id,
                knowledge_id=knowledge_id,
                is_correct=is_correct,
                time_spent_seconds=time_spent_seconds,
                question=question,
                student_answer=student_answer,
                correct_answer=correct_answer,
                feedback=feedback,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
            return record

    async def get_recent(
        self, learner_id: str, limit: int = 20
    ) -> list[LearningRecord]:
        """获取最近的学习记录。"""
        async with async_session() as session:
            result = await session.execute(
                select(LearningRecord)
                .where(LearningRecord.learner_id == learner_id)
                .order_by(LearningRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_by_knowledge(
        self, learner_id: str, knowledge_id: str, limit: int = 50
    ) -> list[LearningRecord]:
        """获取特定知识点的学习记录。"""
        async with async_session() as session:
            result = await session.execute(
                select(LearningRecord)
                .where(
                    LearningRecord.learner_id == learner_id,
                    LearningRecord.knowledge_id == knowledge_id,
                )
                .order_by(LearningRecord.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_stats(self, learner_id: str) -> dict:
        """获取学习统计。"""
        async with async_session() as session:
            total = await session.scalar(
                select(func.count(LearningRecord.id)).where(
                    LearningRecord.learner_id == learner_id
                )
            )
            correct = await session.scalar(
                select(func.count(LearningRecord.id)).where(
                    LearningRecord.learner_id == learner_id,
                    LearningRecord.is_correct == True,
                )
            )
            total_time = await session.scalar(
                select(func.sum(LearningRecord.time_spent_seconds)).where(
                    LearningRecord.learner_id == learner_id
                )
            )

            return {
                "total_questions": total or 0,
                "correct_answers": correct or 0,
                "accuracy": (correct / total) if total else 0.0,
                "total_time_seconds": total_time or 0,
            }

    async def get_learning_curve(self, learner_id: str, limit: int = 20) -> list[dict]:
        """获取学习曲线数据。"""
        records = await self.get_recent(learner_id, limit)
        return [
            {
                "timestamp": record.created_at.isoformat(),
                "type": "assessment",
                "knowledge_id": record.knowledge_id,
                "is_correct": record.is_correct,
            }
            for record in reversed(records)
        ]
