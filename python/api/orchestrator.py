"""Agent orchestrator for coordinating one interaction across the mesh."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from agents import AssessmentAgent, CurriculumAgent, EngagementAgent, TutorAgent
from core.event_bus import Event, EventBus, EventType
from core.learner_model import LearnerModel
from core.memory_manager import MemoryManager
from models.session import async_session, close_db, init_db

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Create agents, publish root events, and summarize interaction results."""

    def __init__(self, enable_db_logging: bool = False) -> None:
        self.event_bus = EventBus(enable_db_logging=enable_db_logging)
        self.memory_manager = MemoryManager()
        self.learner_models: dict[str, LearnerModel] = {}
        self._db_initialized = False

        self.assessment = AssessmentAgent(
            name="AssessmentAgent",
            event_bus=self.event_bus,
            learner_models=self.learner_models,
            memory_manager=self.memory_manager,
        )
        self.tutor = TutorAgent(
            name="TutorAgent",
            event_bus=self.event_bus,
            learner_models=self.learner_models,
            memory_manager=self.memory_manager,
        )
        self.curriculum = CurriculumAgent(
            name="CurriculumAgent",
            event_bus=self.event_bus,
            learner_models=self.learner_models,
            memory_manager=self.memory_manager,
        )
        self.engagement = EngagementAgent(
            name="EngagementAgent",
            event_bus=self.event_bus,
            learner_models=self.learner_models,
            memory_manager=self.memory_manager,
        )

    async def init_database(self) -> None:
        try:
            await init_db()
            self._db_initialized = True
            logger.info("Database initialized successfully")
        except Exception as exc:
            logger.error("Failed to initialize database: %s", exc)
            self._db_initialized = False

    async def close_database(self) -> None:
        try:
            await close_db()
            self._db_initialized = False
            logger.info("Database connections closed")
        except Exception as exc:
            logger.error("Failed to close database: %s", exc)

    async def get_learner_model(self, learner_id: str) -> LearnerModel:
        model = await self.memory_manager.get_or_load(learner_id)
        self.learner_models[learner_id] = model
        return model

    def get_learner_model_sync(self, learner_id: str) -> LearnerModel:
        if learner_id not in self.learner_models:
            if learner_id in self.memory_manager._cache:
                self.learner_models[learner_id] = self.memory_manager._cache[learner_id]
            else:
                self.learner_models[learner_id] = LearnerModel(learner_id)
        return self.learner_models[learner_id]

    def seed_demo_data(self, learner_id: str) -> None:
        self.curriculum.seed_demo_data(learner_id)

    async def submit_answer(
        self,
        learner_id: str,
        knowledge_id: str,
        is_correct: bool,
        time_spent: float = 0,
        submission_context: dict[str, Any] | None = None,
        evaluation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        model = await self.get_learner_model(learner_id)
        mastery_before = model.get_state(knowledge_id).mastery
        correlation_id = str(uuid.uuid4())

        payload = {
            "knowledge_id": knowledge_id,
            "is_correct": is_correct,
            "time_spent_seconds": time_spent,
        }
        if submission_context:
            payload.update(submission_context)

        await self.event_bus.publish(
            Event(
                type=EventType.STUDENT_SUBMISSION,
                source="api",
                learner_id=learner_id,
                correlation_id=correlation_id,
                data=payload,
            )
        )

        if self._db_initialized:
            await self._save_learner_state(
                learner_id=learner_id,
                knowledge_id=knowledge_id,
                is_correct=is_correct,
                mastery_before=mastery_before,
                time_spent=time_spent,
            )

        events = await self._get_interaction_events(learner_id, correlation_id)
        return self._build_interaction_result(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            correlation_id=correlation_id,
            events=events,
            evaluation=evaluation
            or {
                "is_correct": is_correct,
                "feedback": submission_context.get("evaluation_feedback", "") if submission_context else "",
            },
        )

    async def ask_question(
        self,
        learner_id: str,
        knowledge_id: str,
        question: str,
    ) -> dict[str, Any]:
        await self.get_learner_model(learner_id)
        correlation_id = str(uuid.uuid4())

        await self.event_bus.publish(
            Event(
                type=EventType.STUDENT_QUESTION,
                source="api",
                learner_id=learner_id,
                correlation_id=correlation_id,
                data={"knowledge_id": knowledge_id, "question": question},
            )
        )

        events = await self._get_interaction_events(learner_id, correlation_id)
        return self._build_interaction_result(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            correlation_id=correlation_id,
            events=events,
            evaluation=None,
        )

    async def send_message(
        self,
        learner_id: str,
        message: str,
        knowledge_id: str = "general",
    ) -> dict[str, Any]:
        await self.get_learner_model(learner_id)
        correlation_id = str(uuid.uuid4())

        await self.event_bus.publish(
            Event(
                type=EventType.STUDENT_MESSAGE,
                source="api",
                learner_id=learner_id,
                correlation_id=correlation_id,
                data={"message": message, "knowledge_id": knowledge_id},
            )
        )

        events = await self._get_interaction_events(learner_id, correlation_id)
        return self._build_interaction_result(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            correlation_id=correlation_id,
            events=events,
            evaluation=None,
        )

    async def _get_interaction_events(
        self,
        learner_id: str,
        correlation_id: str,
        limit: int = 30,
    ) -> list[Event]:
        return await self.event_bus.get_event_history_from_db(
            learner_id=learner_id,
            correlation_id=correlation_id,
            limit=limit,
        )

    def _serialize_event(self, event: Event) -> dict[str, Any]:
        return {
            "event_type": event.type.value,
            "source": event.source,
            "data": event.data,
            "timestamp": event.timestamp.isoformat(),
            "correlation_id": event.correlation_id,
        }

    def _extract_teaching_response(
        self,
        events: list[Event],
        knowledge_id: str,
    ) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.type != EventType.TEACHING_RESPONSE:
                continue
            event_knowledge = event.data.get("knowledge_id")
            if event_knowledge and event_knowledge != knowledge_id:
                continue
            return {
                "response": event.data.get("response", ""),
                "teaching_style": event.data.get("teaching_style", ""),
                "context_type": event.data.get("context_type", ""),
                "knowledge_id": event.data.get("knowledge_id", knowledge_id),
                "hint_level": event.data.get("hint_level"),
                "hint_count": event.data.get("hint_count"),
                "generation_mode": event.data.get("generation_mode"),
                "response_variant": event.data.get("response_variant"),
                "history_scope": event.data.get("history_scope"),
            }
        return None

    def _build_interaction_result(
        self,
        learner_id: str,
        knowledge_id: str,
        correlation_id: str,
        events: list[Event],
        evaluation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "learner_id": learner_id,
            "knowledge_id": knowledge_id,
            "correlation_id": correlation_id,
            "evaluation": evaluation,
            "teaching_response": self._extract_teaching_response(events, knowledge_id),
            "review_snapshot": self.curriculum.get_review_snapshot(learner_id, knowledge_id),
            "interaction_events": [self._serialize_event(event) for event in events],
            "events_triggered": len(events),
        }

    async def _save_learner_state(
        self,
        learner_id: str,
        knowledge_id: str,
        is_correct: bool,
        mastery_before: float,
        time_spent: float = 0,
    ) -> None:
        if not self._db_initialized:
            return

        try:
            async with async_session() as session:
                model = self.learner_models.get(learner_id)
                if model:
                    await self.memory_manager.save(learner_id, session)

                    from models.database import LearningRecord

                    session.add(
                        LearningRecord(
                            learner_id=learner_id,
                            knowledge_id=knowledge_id,
                            is_correct=is_correct,
                            time_spent_seconds=time_spent,
                            mastery_before=mastery_before,
                            mastery_after=model.get_state(knowledge_id).mastery,
                        )
                    )
                    await session.commit()

                await self.curriculum.save_review_items(session, learner_id)
                await self._save_agent_states(learner_id, session)
        except Exception as exc:
            logger.warning("Failed to save learner state: %s", exc)

    async def _save_agent_states(self, learner_id: str, session: Any) -> None:
        try:
            tutor_state = self.tutor.get_state_for_save(learner_id)
            if tutor_state:
                self.memory_manager.set_agent_state("TutorAgent", learner_id, tutor_state)

            engagement_state = self.engagement.get_state_for_save(learner_id)
            if engagement_state:
                self.memory_manager.set_agent_state("EngagementAgent", learner_id, engagement_state)

            curriculum_state = self.curriculum.get_state_for_save(learner_id)
            if curriculum_state:
                self.memory_manager.set_agent_state("CurriculumAgent", learner_id, curriculum_state)

            for agent_name in ["TutorAgent", "EngagementAgent", "CurriculumAgent"]:
                await self.memory_manager.save_agent_state(agent_name, learner_id, session)
        except Exception as exc:
            logger.error("Failed to save agent states: %s", exc)

    async def load_learner_state(self, learner_id: str) -> bool:
        if not self._db_initialized:
            return False

        try:
            async with async_session() as session:
                model = await self.memory_manager.get_or_load(learner_id, session)
                self.learner_models[learner_id] = model
                await self.curriculum.load_review_items(session, learner_id)
                await self._load_agent_states(learner_id, session)
                return True
        except Exception as exc:
            logger.warning("Failed to load learner state: %s", exc)
            return False

    async def _load_agent_states(self, learner_id: str, session: Any) -> None:
        try:
            tutor_state = await self.memory_manager.load_agent_state("TutorAgent", learner_id, session)
            if tutor_state:
                self.tutor.load_state(learner_id, tutor_state)

            engagement_state = await self.memory_manager.load_agent_state(
                "EngagementAgent", learner_id, session
            )
            if engagement_state:
                self.engagement.load_state(learner_id, engagement_state)

            curriculum_state = await self.memory_manager.load_agent_state(
                "CurriculumAgent", learner_id, session
            )
            if curriculum_state:
                self.curriculum.load_state(learner_id, curriculum_state)
        except Exception as exc:
            logger.error("Failed to load agent states: %s", exc)

    async def get_learner_progress(self, learner_id: str) -> dict[str, Any]:
        model = await self.get_learner_model(learner_id)
        if not model.knowledge_states:
            return {"learner_id": learner_id, "status": "no_data"}

        return {
            "learner_id": learner_id,
            "progress": model.get_overall_progress(),
            "weak_points": [
                {"id": state.knowledge_id, "mastery": state.mastery}
                for state in model.get_weak_points()
            ],
            "strong_points": [
                {"id": state.knowledge_id, "mastery": state.mastery}
                for state in model.get_strong_points()
            ],
        }
