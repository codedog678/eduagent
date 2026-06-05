"""
Repository 层。

封装数据库操作，提供类型安全的数据访问接口。
"""

from repositories.learner_repo import LearnerRepository
from repositories.knowledge_repo import KnowledgeRepository
from repositories.learning_record_repo import LearningRecordRepository
from repositories.review_repo import ReviewRepository
from repositories.event_repo import EventRepository

__all__ = [
    "LearnerRepository",
    "KnowledgeRepository",
    "LearningRecordRepository",
    "ReviewRepository",
    "EventRepository",
]
