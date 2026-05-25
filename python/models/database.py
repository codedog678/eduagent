"""
SQLAlchemy ORM 模型定义。

定义所有数据库表结构，用于持久化学习者状态、知识掌握度、学习记录等数据。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
    Boolean,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """声明式基类。"""
    pass


class Learner(Base):
    """学习者模型。"""
    __tablename__ = "learners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(200), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    metadata_ = Column("metadata", JSON, default=dict)

    # 关系
    knowledge_states = relationship("KnowledgeState", back_populates="learner", cascade="all, delete-orphan")
    learning_records = relationship("LearningRecord", back_populates="learner", cascade="all, delete-orphan")
    review_items = relationship("ReviewItem", back_populates="learner", cascade="all, delete-orphan")
    event_logs = relationship("EventLog", back_populates="learner", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Learner(learner_id='{self.learner_id}', name='{self.name}')>"


class KnowledgeState(Base):
    """知识点掌握状态模型。"""
    __tablename__ = "knowledge_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(String(100), ForeignKey("learners.learner_id"), nullable=False)
    knowledge_id = Column(String(100), nullable=False)
    mastery = Column(Float, default=0.1)  # BKT: P(L) 当前掌握概率
    alpha = Column(Float, default=1.0)  # Beta分布参数α
    beta = Column(Float, default=9.0)  # Beta分布参数β
    attempts = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    streak = Column(Integer, default=0)  # 连续正确次数
    last_attempt = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    learner = relationship("Learner", back_populates="knowledge_states")

    # 复合索引
    __table_args__ = (
        Index("idx_learner_knowledge", "learner_id", "knowledge_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeState(learner_id='{self.learner_id}', knowledge_id='{self.knowledge_id}', mastery={self.mastery:.3f})>"


class LearningRecord(Base):
    """学习记录模型。"""
    __tablename__ = "learning_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(String(100), ForeignKey("learners.learner_id"), nullable=False)
    knowledge_id = Column(String(100), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    time_spent_seconds = Column(Float, default=0)
    mastery_before = Column(Float, nullable=True)  # 答题前mastery
    mastery_after = Column(Float, nullable=True)  # 答题后mastery
    created_at = Column(DateTime, default=datetime.now)

    # 关系
    learner = relationship("Learner", back_populates="learning_records")

    # 索引
    __table_args__ = (
        Index("idx_learner_created", "learner_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<LearningRecord(learner_id='{self.learner_id}', knowledge_id='{self.knowledge_id}', correct={self.is_correct})>"


class ReviewItem(Base):
    """复习计划模型（SM-2间隔重复）。"""
    __tablename__ = "review_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    learner_id = Column(String(100), ForeignKey("learners.learner_id"), nullable=False)
    knowledge_id = Column(String(100), nullable=False)
    easiness_factor = Column(Float, default=2.5)  # EF因子
    interval_days = Column(Float, default=0)  # 复习间隔（天）
    repetition = Column(Integer, default=0)  # 成功复习次数
    next_review = Column(DateTime, nullable=False)
    last_review = Column(DateTime, nullable=True)
    total_reviews = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    learner = relationship("Learner", back_populates="review_items")

    # 复合索引
    __table_args__ = (
        Index("idx_learner_review_knowledge", "learner_id", "knowledge_id", unique=True),
        Index("idx_next_review", "next_review"),
    )

    def __repr__(self) -> str:
        return f"<ReviewItem(learner_id='{self.learner_id}', knowledge_id='{self.knowledge_id}', next_review='{self.next_review}')>"


class EventLog(Base):
    """事件日志模型（事件溯源）。"""
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(100), unique=True, nullable=False)
    event_type = Column(String(100), nullable=False)
    source = Column(String(100), nullable=False)  # 发布事件的Agent名称
    learner_id = Column(String(100), ForeignKey("learners.learner_id"), nullable=False)
    data = Column(JSON, default=dict)
    correlation_id = Column(String(100), nullable=True)  # 事件链追踪
    created_at = Column(DateTime, default=datetime.now)

    # 关系
    learner = relationship("Learner", back_populates="event_logs")

    # 索引
    __table_args__ = (
        Index("idx_event_type", "event_type"),
        Index("idx_event_learner", "learner_id"),
        Index("idx_event_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EventLog(event_id='{self.event_id}', type='{self.event_type}', source='{self.source}')>"


class AgentState(Base):
    """Agent状态模型 -- 持久化各Agent的运行时状态。"""
    __tablename__ = "agent_states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False)  # Agent名称
    learner_id = Column(String(100), ForeignKey("learners.learner_id"), nullable=False)
    state_data = Column(JSON, default=dict)  # Agent状态数据
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    learner = relationship("Learner")

    # 复合索引
    __table_args__ = (
        Index("idx_agent_learner", "agent_name", "learner_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<AgentState(agent='{self.agent_name}', learner='{self.learner_id}')>"
