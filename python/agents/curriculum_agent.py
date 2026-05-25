"""Curriculum agent for study path recommendations and review scheduling."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from .base_agent import BaseAgent
from core.event_bus import Event, EventType
from core.knowledge_graph import KnowledgeGraph, build_english_learning_graph
from core.spaced_repetition import ReviewItem, SpacedRepetition

logger = logging.getLogger(__name__)

MASTERY_THRESHOLD = 0.6


class ReviewReminder:
    """Student-facing review reminder."""

    def __init__(self, knowledge_id: str, retention: float, days_since_review: float):
        self.knowledge_id = knowledge_id
        self.retention = retention
        self.days_since_review = days_since_review
        self.created_at = datetime.now()

    @property
    def urgency(self) -> str:
        if self.retention < 0.3:
            return "urgent"
        if self.retention < 0.5:
            return "high"
        if self.retention < 0.7:
            return "medium"
        return "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "knowledge_id": self.knowledge_id,
            "retention": round(self.retention, 3),
            "days_since_review": round(self.days_since_review, 1),
            "urgency": self.urgency,
            "created_at": self.created_at.isoformat(),
        }


class CurriculumAgent(BaseAgent):
    """Plan next topics and spaced-review reminders."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.knowledge_graph: KnowledgeGraph = build_english_learning_graph()
        self.sr = SpacedRepetition()
        self._review_items: dict[str, dict[str, ReviewItem]] = {}
        self._reminders: dict[str, list[ReviewReminder]] = {}

    @property
    def subscribed_events(self) -> list[EventType]:
        return [
            EventType.MASTERY_UPDATED,
            EventType.WEAKNESS_DETECTED,
            EventType.PACE_ADJUSTMENT,
        ]

    def seed_demo_data(self, learner_id: str) -> None:
        now = datetime.now()
        self._review_items[learner_id] = {
            "vocab_basic": ReviewItem(
                knowledge_id="vocab_basic",
                easiness_factor=2.5,
                interval_days=1,
                repetition=1,
                next_review=now - timedelta(days=2),
                last_review=now - timedelta(days=3),
                total_reviews=2,
            ),
            "vocab_intermediate": ReviewItem(
                knowledge_id="vocab_intermediate",
                easiness_factor=2.2,
                interval_days=3,
                repetition=2,
                next_review=now - timedelta(days=1),
                last_review=now - timedelta(days=4),
                total_reviews=3,
            ),
            "grammar_tenses": ReviewItem(
                knowledge_id="grammar_tenses",
                easiness_factor=1.8,
                interval_days=1,
                repetition=0,
                next_review=now,
                last_review=now - timedelta(days=1),
                total_reviews=1,
            ),
            "reading_skimming": ReviewItem(
                knowledge_id="reading_skimming",
                easiness_factor=2.4,
                interval_days=6,
                repetition=2,
                next_review=now + timedelta(days=3),
                last_review=now - timedelta(days=1),
                total_reviews=3,
            ),
            "writing_paragraph": ReviewItem(
                knowledge_id="writing_paragraph",
                easiness_factor=2.0,
                interval_days=1,
                repetition=0,
                next_review=now + timedelta(days=1),
                last_review=now,
                total_reviews=1,
            ),
        }

        model = self.get_learner_model(learner_id)
        demo_mastery = {
            "vocab_basic": (0.75, 4, 3),
            "vocab_intermediate": (0.55, 3, 2),
            "grammar_tenses": (0.3, 5, 1),
            "reading_skimming": (0.8, 3, 3),
            "writing_paragraph": (0.4, 2, 1),
        }
        for knowledge_id, (mastery, attempts, correct) in demo_mastery.items():
            state = model.get_state(knowledge_id)
            state.mastery = mastery
            state.attempts = attempts
            state.correct_count = correct

    async def handle_event(self, event: Event) -> None:
        if event.type == EventType.MASTERY_UPDATED:
            await self._handle_mastery_update(event)
        elif event.type == EventType.WEAKNESS_DETECTED:
            await self._handle_weakness(event)
        elif event.type == EventType.PACE_ADJUSTMENT:
            await self._handle_pace_adjustment(event)

    async def _handle_mastery_update(self, event: Event) -> None:
        learner_id = event.learner_id
        knowledge_id = event.data.get("knowledge_id", "")
        mastery = float(event.data.get("mastery", 0.0))

        quality = self._mastery_to_quality(mastery)
        review_item = self._get_review_item(learner_id, knowledge_id)
        self.sr.review(review_item, quality)

        if mastery >= MASTERY_THRESHOLD:
            await self._check_and_recommend_next(learner_id, event.correlation_id)

        await self._send_review_schedule(learner_id, event.correlation_id)

    def _mastery_to_quality(self, mastery: float) -> int:
        if mastery >= 0.9:
            return 5
        if mastery >= 0.75:
            return 4
        if mastery >= 0.6:
            return 3
        if mastery >= 0.4:
            return 2
        if mastery >= 0.2:
            return 1
        return 0

    def _get_review_item(self, learner_id: str, knowledge_id: str) -> ReviewItem:
        learner_items = self._review_items.setdefault(learner_id, {})
        if knowledge_id not in learner_items:
            learner_items[knowledge_id] = ReviewItem(knowledge_id=knowledge_id)
        return learner_items[knowledge_id]

    async def _check_and_recommend_next(
        self,
        learner_id: str,
        correlation_id: str | None,
    ) -> None:
        model = self.get_learner_model(learner_id)
        mastered_ids = {
            state.knowledge_id
            for state in model.knowledge_states.values()
            if state.mastery >= MASTERY_THRESHOLD
        }

        ready = self.knowledge_graph.get_ready_nodes(mastered_ids)
        if not ready:
            return

        next_topic = ready[0]
        node = self.knowledge_graph.nodes.get(next_topic)
        await self.emit(
            EventType.NEXT_TOPIC,
            learner_id,
            {
                "knowledge_id": next_topic,
                "name": node.name if node else next_topic,
                "difficulty": node.difficulty if node else 0.5,
                "reason": "前置知识已经达到可推进水平，可以尝试进入下一知识点。",
                "alternatives": ready[1:4],
            },
            correlation_id=correlation_id,
        )

    async def _send_review_schedule(
        self,
        learner_id: str,
        correlation_id: str | None,
    ) -> None:
        items = list(self._review_items.get(learner_id, {}).values())
        due_items = self.sr.get_due_items(items)
        schedule = self.sr.get_study_schedule(items, days_ahead=7)

        model = self.get_learner_model(learner_id)
        forgetting_items: list[dict[str, Any]] = []
        for item in items:
            if not item.last_review:
                continue
            days_since_review = (datetime.now() - item.last_review).total_seconds() / 86400
            retention = model.get_forgetting_curve(item.knowledge_id, days_since_review)
            if retention < 0.5:
                forgetting_items.append(
                    {
                        "knowledge_id": item.knowledge_id,
                        "retention": round(retention, 3),
                        "days_since_review": round(days_since_review, 1),
                    }
                )

        forgetting_items.sort(key=lambda item: item["retention"])
        if not due_items and not forgetting_items:
            return

        await self.emit(
            EventType.REVIEW_SCHEDULED,
            learner_id,
            {
                "due_now": [
                    {
                        "knowledge_id": item.knowledge_id,
                        "overdue_days": round(item.overdue_days, 1),
                    }
                    for item in due_items[:5]
                ],
                "about_to_forget": forgetting_items[:5],
                "weekly_schedule": schedule,
            },
            correlation_id=correlation_id,
        )

        reminders: list[ReviewReminder] = []
        for item in due_items[:5]:
            days_since_review = 0.0
            if item.last_review:
                days_since_review = (datetime.now() - item.last_review).total_seconds() / 86400
            reminders.append(
                ReviewReminder(
                    knowledge_id=item.knowledge_id,
                    retention=0.0,
                    days_since_review=days_since_review,
                )
            )
        for item in forgetting_items[:5]:
            reminders.append(
                ReviewReminder(
                    knowledge_id=item["knowledge_id"],
                    retention=item["retention"],
                    days_since_review=item["days_since_review"],
                )
            )

        self._reminders[learner_id] = reminders
        if reminders:
            await self.emit(
                EventType.REVIEW_REMINDER,
                learner_id,
                {
                    "reminders": [reminder.to_dict() for reminder in reminders],
                    "total_count": len(reminders),
                    "urgent_count": sum(
                        1 for reminder in reminders if reminder.urgency in {"urgent", "high"}
                    ),
                },
                correlation_id=correlation_id,
            )

    async def _handle_weakness(self, event: Event) -> None:
        learner_id = event.learner_id
        knowledge_id = event.data.get("knowledge_id", "")
        model = self.get_learner_model(learner_id)
        mastered_ids = {
            state.knowledge_id
            for state in model.knowledge_states.values()
            if state.mastery >= MASTERY_THRESHOLD
        }
        remedial_path = self.knowledge_graph.get_learning_path(knowledge_id, mastered_ids)
        logger.info(
            "[CurriculumAgent] weakness detected for %s: %s, remedial path=%s",
            learner_id,
            knowledge_id,
            remedial_path,
        )

    async def _handle_pace_adjustment(self, event: Event) -> None:
        action = event.data.get("action", "")
        learner_id = event.learner_id
        items = self._review_items.get(learner_id, {})

        if action == "slow_down":
            for item in items.values():
                item.interval_days *= 1.5
                base_time = item.last_review or datetime.now()
                item.next_review = base_time + timedelta(days=item.interval_days)
            await self.emit(
                EventType.ENCOURAGEMENT,
                learner_id,
                {
                    "message": "我们先把节奏放慢一点，稳住基础，比硬赶进度更重要。",
                    "type": "pace_slow_down",
                },
                correlation_id=event.correlation_id,
            )
        elif action == "speed_up":
            for item in items.values():
                item.interval_days = max(1, item.interval_days * 0.7)
                base_time = item.last_review or datetime.now()
                item.next_review = base_time + timedelta(days=item.interval_days)

    def get_reminders(self, learner_id: str) -> list[dict[str, Any]]:
        reminders = self._reminders.get(learner_id, [])
        urgency_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
        return [item.to_dict() for item in sorted(reminders, key=lambda item: urgency_order[item.urgency])]

    def clear_reminder(self, learner_id: str, knowledge_id: str) -> bool:
        if learner_id not in self._reminders:
            return False
        self._reminders[learner_id] = [
            reminder for reminder in self._reminders[learner_id] if reminder.knowledge_id != knowledge_id
        ]
        return True

    def get_top_due_items(self, learner_id: str, limit: int = 3) -> list[dict[str, Any]]:
        items = list(self._review_items.get(learner_id, {}).values())
        due_items = self.sr.get_due_items(items)
        return [
            {
                "knowledge_id": item.knowledge_id,
                "next_review": item.next_review.isoformat(),
                "overdue_days": round(item.overdue_days, 1),
            }
            for item in due_items[:limit]
        ]

    def get_review_snapshot(self, learner_id: str, knowledge_id: str) -> dict[str, Any]:
        item = self._review_items.get(learner_id, {}).get(knowledge_id)
        if item is None:
            return {
                "knowledge_id": knowledge_id,
                "next_review": None,
                "retention": None,
                "urgency": "low",
                "is_due": False,
                "days_since_review": None,
                "top_due_items": self.get_top_due_items(learner_id),
            }

        days_since_review = 0.0
        retention = 1.0
        if item.last_review:
            days_since_review = (datetime.now() - item.last_review).total_seconds() / 86400
            model = self.get_learner_model(learner_id)
            retention = model.get_forgetting_curve(knowledge_id, days_since_review)

        reminder = ReviewReminder(
            knowledge_id=knowledge_id,
            retention=retention,
            days_since_review=days_since_review,
        )
        return {
            "knowledge_id": knowledge_id,
            "next_review": item.next_review.isoformat(),
            "retention": round(retention, 3),
            "urgency": reminder.urgency,
            "is_due": item.is_due,
            "days_since_review": round(days_since_review, 1),
            "top_due_items": self.get_top_due_items(learner_id),
        }

    def get_state_for_save(self, learner_id: str) -> dict[str, Any] | None:
        reminders = self._reminders.get(learner_id, [])
        if reminders:
            return {"reminders": [reminder.to_dict() for reminder in reminders]}
        return None

    def load_state(self, learner_id: str, state_data: dict[str, Any]) -> None:
        reminders_data = state_data.get("reminders", [])
        if reminders_data:
            self._reminders[learner_id] = [
                ReviewReminder(
                    knowledge_id=item["knowledge_id"],
                    retention=item["retention"],
                    days_since_review=item["days_since_review"],
                )
                for item in reminders_data
            ]

    async def save_review_items(self, session: Any, learner_id: str) -> None:
        from sqlalchemy import select
        from models.database import ReviewItem as ReviewItemDB

        items = self._review_items.get(learner_id, {})
        for knowledge_id, item in items.items():
            result = await session.execute(
                select(ReviewItemDB).where(
                    ReviewItemDB.learner_id == learner_id,
                    ReviewItemDB.knowledge_id == knowledge_id,
                )
            )
            existing = result.scalar_one_or_none()
            if existing is None:
                session.add(
                    ReviewItemDB(
                        learner_id=learner_id,
                        knowledge_id=knowledge_id,
                        easiness_factor=item.easiness_factor,
                        interval_days=item.interval_days,
                        repetition=item.repetition,
                        next_review=item.next_review,
                        last_review=item.last_review,
                        total_reviews=item.total_reviews,
                    )
                )
            else:
                existing.easiness_factor = item.easiness_factor
                existing.interval_days = item.interval_days
                existing.repetition = item.repetition
                existing.next_review = item.next_review
                existing.last_review = item.last_review
                existing.total_reviews = item.total_reviews
        await session.commit()

    async def load_review_items(self, session: Any, learner_id: str) -> None:
        from sqlalchemy import select
        from models.database import ReviewItem as ReviewItemDB

        result = await session.execute(
            select(ReviewItemDB).where(ReviewItemDB.learner_id == learner_id)
        )
        rows = result.scalars().all()
        if not rows:
            return

        self._review_items[learner_id] = {}
        for row in rows:
            self._review_items[learner_id][row.knowledge_id] = ReviewItem(
                knowledge_id=row.knowledge_id,
                easiness_factor=row.easiness_factor,
                interval_days=row.interval_days,
                repetition=row.repetition,
                next_review=row.next_review,
                last_review=row.last_review,
                total_reviews=row.total_reviews,
            )
