"""
Curriculum Service。

封装课程相关的业务逻辑。
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from core.event_bus import Event, EventType
from core.spaced_repetition import SpacedRepetition, ReviewItem
from services.learner_service import LearnerService
from repositories.knowledge_repo import KnowledgeRepository
from repositories.review_repo import ReviewRepository

logger = logging.getLogger(__name__)


class CurriculumService:
    """课程业务逻辑层。"""

    def __init__(self) -> None:
        self.learner_service = LearnerService()
        self.knowledge_repo = KnowledgeRepository()
        self.review_repo = ReviewRepository()
        self.sr = SpacedRepetition()
        self._review_items: dict[str, dict[str, ReviewItem]] = {}  # learner_id -> {knowledge_id: ReviewItem}

    async def get_next_topics(
        self,
        learner_id: str,
        knowledge_id: str,
        mastery: float,
        is_weakness: bool = False,
    ) -> dict:
        """获取下一个推荐主题。"""
        model = await self.learner_service.get_learner_model(learner_id)
        mastered_ids = model.get_mastered_knowledge_ids()

        # 获取可学习的知识点
        ready_nodes = self.knowledge_repo.get_ready_nodes(mastered_ids)

        # 获取学习路径
        learning_path = []
        for node_id in ready_nodes[:3]:  # 推荐前3个
            path = self.knowledge_repo.get_learning_path(node_id, mastered_ids)
            learning_path.extend(path)

        # 去重并保持顺序
        seen = set()
        unique_path = []
        for node_id in learning_path:
            if node_id not in seen:
                seen.add(node_id)
                unique_path.append(node_id)

        # 构建推荐列表
        next_topics = []
        for node_id in unique_path[:5]:  # 最多推荐5个
            node = self.knowledge_repo.get_node(node_id)
            if node:
                next_topics.append({
                    "id": node.id,
                    "name": node.name,
                    "difficulty": node.difficulty,
                    "tags": node.tags,
                })

        events = [{
            "type": EventType.NEXT_TOPIC.value,
            "data": {
                "next_topics": next_topics,
                "learning_path": unique_path,
            },
        }]

        return {
            "next_topics": next_topics,
            "learning_path": unique_path,
            "events": events,
        }

    async def schedule_review(
        self,
        learner_id: str,
        knowledge_id: str,
        mastery: float,
    ) -> dict:
        """安排复习。"""
        # 创建或获取复习项
        if learner_id not in self._review_items:
            self._review_items[learner_id] = {}

        if knowledge_id not in self._review_items[learner_id]:
            review_item = ReviewItem(
                learner_id=learner_id,
                knowledge_id=knowledge_id,
            )
            self._review_items[learner_id][knowledge_id] = review_item

        review_item = self._review_items[learner_id][knowledge_id]

        # 根据掌握度调整复习间隔
        if mastery < 0.3:
            interval_days = 1
        elif mastery < 0.6:
            interval_days = 3
        elif mastery < 0.8:
            interval_days = 7
        else:
            interval_days = 14

        # 设置下次复习时间
        review_item.next_review = datetime.now() + timedelta(days=interval_days)
        review_item.interval_days = interval_days

        # 持久化
        await self.review_repo.upsert(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            interval_days=interval_days,
            next_review=review_item.next_review,
        )

        events = [{
            "type": EventType.REVIEW_SCHEDULED.value,
            "data": {
                "knowledge_id": knowledge_id,
                "next_review": review_item.next_review.isoformat(),
                "interval_days": interval_days,
            },
        }]

        return {
            "next_review": review_item.next_review.isoformat(),
            "interval_days": interval_days,
            "events": events,
        }

    async def get_review_schedule(self, learner_id: str) -> dict:
        """获取复习计划。"""
        items = list(self._review_items.get(learner_id, {}).values())
        weekly_schedule = self.sr.get_study_schedule(items, days_ahead=7)

        # 获取到期项目
        due_items = [
            item for item in items
            if item.next_review and item.next_review <= datetime.now()
        ]

        # 获取提醒
        reminders = self._get_reminders(learner_id)

        return {
            "reminders": reminders,
            "due_items": [
                {
                    "knowledge_id": item.knowledge_id,
                    "next_review": item.next_review.isoformat() if item.next_review else "",
                    "interval_days": item.interval_days,
                }
                for item in due_items
            ],
            "weekly_schedule": weekly_schedule,
            "total_items": len(items),
        }

    async def complete_review(
        self,
        learner_id: str,
        knowledge_id: str,
        quality: int,
    ) -> dict:
        """完成复习。"""
        items = self._review_items.get(learner_id, {})
        item = items.get(knowledge_id)

        if item is None:
            return {"status": "error", "message": "Review item not found"}

        # 使用 SM-2 算法更新
        self.sr.review(item, quality)

        # 清除提醒
        self._clear_reminder(learner_id, knowledge_id)

        # 持久化
        await self.review_repo.update_after_review(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            quality=quality,
            interval_days=item.interval_days,
            easiness_factor=item.easiness_factor,
            next_review=item.next_review,
        )

        return {
            "status": "ok",
            "next_review": item.next_review.isoformat(),
            "interval_days": item.interval_days,
            "easiness_factor": item.easiness_factor,
        }

    def _get_reminders(self, learner_id: str) -> list[dict]:
        """获取复习提醒。"""
        items = self._review_items.get(learner_id, {})
        reminders = []

        for item in items.values():
            if item.next_review and item.next_review <= datetime.now():
                reminders.append({
                    "knowledge_id": item.knowledge_id,
                    "message": f"该复习 {item.knowledge_id} 了",
                    "next_review": item.next_review.isoformat(),
                })

        return reminders

    def _clear_reminder(self, learner_id: str, knowledge_id: str) -> None:
        """清除复习提醒。"""
        items = self._review_items.get(learner_id, {})
        if knowledge_id in items:
            item = items[knowledge_id]
            # 设置为未来的日期，这样就不会触发提醒
            item.next_review = datetime.now() + timedelta(days=item.interval_days)
