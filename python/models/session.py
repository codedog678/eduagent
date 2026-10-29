"""
数据库会话管理。

提供异步数据库引擎、会话工厂和依赖注入。
"""

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import settings
from .database import Base

logger = logging.getLogger(__name__)

# 全局异步引擎和会话工厂
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def _normalize_async_database_url(url: str) -> str:
    """Accept common PostgreSQL URLs and force the asyncpg driver for async SQLAlchemy."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def get_engine() -> AsyncEngine:
    """获取或创建异步数据库引擎。"""
    global _async_engine
    if _async_engine is None:
        database_url = _normalize_async_database_url(settings.database_url)
        _async_engine = create_async_engine(
            database_url,
            echo=False,  # 生产环境关闭SQL日志
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # 连接健康检查
        )
        logger.info("Database engine created: %s", database_url.split("@")[-1])
    return _async_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取或创建异步会话工厂。"""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 依赖注入：获取数据库会话。

    使用方法：
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    初始化数据库：创建所有表。

    在应用启动时调用。
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


async def close_db() -> None:
    """
    关闭数据库连接。

    在应用关闭时调用。
    """
    global _async_engine, _async_session_factory
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
        logger.info("Database connections closed")


async def reset_db_for_tests() -> None:
    """Dispose cached global engine/factory; tests only."""
    await close_db()


def async_session() -> AsyncSession:
    """
    获取数据库会话（非依赖注入方式）。

    用于脚本或独立程序中。
    """
    session_factory = get_session_factory()
    return session_factory()
