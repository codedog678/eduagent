"""
Event Repository。

封装事件日志相关的数据库操作。
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import EventLog
from models.session import async_session

logger = logging.getLogger(__name__)


class EventRepository:
    """事件日志数据访问层。"""

    async def create(
        self,
        event_id: str,
        event_type: str,
        source: str,
        learner_id: str,
        data: dict,
        correlation_id: Optional[str] = None,
    ) -> EventLog:
        """创建事件日志。"""
        async with async_session() as session:
            event_log = EventLog(
                event_id=event_id,
                event_type=event_type,
                source=source,
                learner_id=learner_id,
                data=data,
                correlation_id=correlation_id,
            )
            session.add(event_log)
            await session.commit()
            await session.refresh(event_log)
            return event_log

    async def get_by_learner(
        self, learner_id: str, limit: int = 50
    ) -> list[EventLog]:
        """获取学习者的事件日志。"""
        async with async_session() as session:
            result = await session.execute(
                select(EventLog)
                .where(EventLog.learner_id == learner_id)
                .order_by(EventLog.created_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())

    async def get_by_correlation(self, correlation_id: str) -> list[EventLog]:
        """获取 correlation_id 相关的事件链。"""
        async with async_session() as session:
            result = await session.execute(
                select(EventLog)
                .where(EventLog.correlation_id == correlation_id)
                .order_by(EventLog.created_at.asc())
            )
            return list(result.scalars().all())

    async def get_by_type(
        self, event_type: str, learner_id: Optional[str] = None, limit: int = 50
    ) -> list[EventLog]:
        """按事件类型查询。"""
        async with async_session() as session:
            query = select(EventLog).where(EventLog.event_type == event_type)
            if learner_id:
                query = query.where(EventLog.learner_id == learner_id)
            query = query.order_by(EventLog.created_at.desc()).limit(limit)
            result = await session.execute(query)
            return list(result.scalars().all())
