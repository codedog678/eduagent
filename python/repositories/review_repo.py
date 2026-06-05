"""
Review Repository。

封装复习相关的数据库操作。
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import ReviewItem
from models.session import async_session

logger = logging.getLogger(__name__)


class ReviewRepository:
    """复习数据访问层。"""

    async def get_due_items(
        self, learner_id: str, before: Optional[datetime] = None
    ) -> list[ReviewItem]:
        """获取到期的复习项。"""
        if before is None:
            before = datetime.now()

        async with async_session() as session:
            result = await session.execute(
                select(ReviewItem).where(
                    ReviewItem.learner_id == learner_id,
                    ReviewItem.next_review <= before,
                )
            )
            return list(result.scalars().all())

    async def get_all_items(self, learner_id: str) -> list[ReviewItem]:
        """获取所有复习项。"""
        async with async_session() as session:
            result = await session.execute(
                select(ReviewItem).where(ReviewItem.learner_id == learner_id)
            )
            return list(result.scalars().all())

    async def upsert(
        self,
        learner_id: str,
        knowledge_id: str,
        interval_days: float = 1.0,
        easiness_factor: float = 2.5,
        next_review: Optional[datetime] = None,
    ) -> ReviewItem:
        """更新或插入复习项。"""
        if next_review is None:
            next_review = datetime.now()

        async with async_session() as session:
            result = await session.execute(
                select(ReviewItem).where(
                    ReviewItem.learner_id == learner_id,
                    ReviewItem.knowledge_id == knowledge_id,
                )
            )
            item = result.scalar_one_or_none()

            if item is None:
                item = ReviewItem(
                    learner_id=learner_id,
                    knowledge_id=knowledge_id,
                    interval_days=interval_days,
                    easiness_factor=easiness_factor,
                    next_review=next_review,
                    last_review=None,
                )
                session.add(item)
            else:
                item.interval_days = interval_days
                item.easiness_factor = easiness_factor
                item.next_review = next_review

            await session.commit()
            await session.refresh(item)
            return item

    async def update_after_review(
        self,
        learner_id: str,
        knowledge_id: str,
        quality: int,
        interval_days: float,
        easiness_factor: float,
        next_review: datetime,
    ) -> Optional[ReviewItem]:
        """复习完成后更新复习项。"""
        async with async_session() as session:
            result = await session.execute(
                select(ReviewItem).where(
                    ReviewItem.learner_id == learner_id,
                    ReviewItem.knowledge_id == knowledge_id,
                )
            )
            item = result.scalar_one_or_none()

            if item:
                item.last_review = datetime.now()
                item.interval_days = interval_days
                item.easiness_factor = easiness_factor
                item.next_review = next_review
                await session.commit()
                await session.refresh(item)

            return item

    async def delete(self, learner_id: str, knowledge_id: str) -> bool:
        """删除复习项。"""
        async with async_session() as session:
            result = await session.execute(
                select(ReviewItem).where(
                    ReviewItem.learner_id == learner_id,
                    ReviewItem.knowledge_id == knowledge_id,
                )
            )
            item = result.scalar_one_or_none()
            if item:
                await session.delete(item)
                await session.commit()
                return True
            return False
