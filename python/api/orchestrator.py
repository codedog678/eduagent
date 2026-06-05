"""Agent orchestrator for coordinating one interaction across the mesh."""

from __future__ import annotations

import logging
import json
import uuid
from typing import Any

from agents import AssessmentAgent, CurriculumAgent, EngagementAgent, TutorAgent
from config.settings import settings
from core.event_bus import Event, EventBus, EventType
from core.learner_model import LearnerModel
from core.llm_service import get_llm_service
from core.memory_manager import MemoryManager
from models.session import async_session, close_db, init_db

logger = logging.getLogger(__name__)
'''
启动时组装所有 Agent（注入共享依赖）
接收 API 请求，发布种子事件
等 Agent 自主协作完成后，从事件历史中提取结果，组装返回值

'''

class AgentOrchestrator:
    """Create agents, publish root events, and summarize interaction results.
    所有 Agent 共享同一个 EventBus 实例 → 它们才能互相收到事件
    所有 Agent 共享同一个 learner_models 字典 → 状态一致
    每个 Agent 创建时自动调用 register() → 订阅事件
    """

    def __init__(self, enable_db_logging: bool = False) -> None:
        self.event_bus = EventBus(enable_db_logging=enable_db_logging)
        self.memory_manager = MemoryManager()
        self.learner_models: dict[str, LearnerModel] = {}
        self._db_initialized = False

        self.assessment = AssessmentAgent(
            name="AssessmentAgent",
            event_bus=self.event_bus,
            learner_models=self.learner_models,
        )
        self.tutor = TutorAgent(
            name="TutorAgent",
            event_bus=self.event_bus,
            learner_models=self.learner_models,
        )
        self.curriculum = CurriculumAgent(
            name="CurriculumAgent",
            event_bus=self.event_bus,
            learner_models=self.learner_models,
        )
        self.engagement = EngagementAgent(
            name="EngagementAgent",
            event_bus=self.event_bus,
            learner_models=self.learner_models,
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

    #三个种子事件
    #1.学生提交答案
    '''
     Orchestrator 只发了一个 STUDENT_SUBMISSION 事件，然后就"撒手不管"了。
     后续的评估、教学回复、复习安排都是 Agent 自主通过 EventBus 协作完成的。
     Orchestrator 最后只是去"捡结果"。
    '''
    async def submit_answer(
        self,
        learner_id: str,
        knowledge_id: str,
        is_correct: bool,
        time_spent: float = 0,
        submission_context: dict[str, Any] | None = None,
        evaluation: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        #加载学习者模型
        model = await self.get_learner_model(learner_id)
        mastery_before = model.get_state(knowledge_id).mastery
        correlation_id = str(uuid.uuid4())  #生成事件链ID

        payload = {
            "knowledge_id": knowledge_id,
            "is_correct": is_correct,
            "time_spent_seconds": time_spent,
        }
        if submission_context:
            payload.update(submission_context)

        #发布种子事件
        await self.event_bus.publish(
            Event(
                type=EventType.STUDENT_SUBMISSION,
                source="api",
                learner_id=learner_id,
                correlation_id=correlation_id,
                data=payload,
            )
        )

        #保存学习者模型状态
        if self._db_initialized:
            await self._save_learner_state(
                learner_id=learner_id,
                knowledge_id=knowledge_id,
                is_correct=is_correct,
                mastery_before=mastery_before,
                time_spent=time_spent,
            )

        events = await self._get_interaction_events(learner_id, correlation_id)
        return await self._build_interaction_result(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            correlation_id=correlation_id,
            events=events,
            interaction_type="submission",
            evaluation=evaluation
            or {
                "is_correct": is_correct,
                "feedback": submission_context.get("evaluation_feedback", "") if submission_context else "",
            },
        )

    #2.学生提问
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
        return await self._build_interaction_result(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            correlation_id=correlation_id,
            events=events,
            interaction_type="question",
            evaluation=None,
        )

    #3.学生发送消息
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
        return await self._build_interaction_result(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            correlation_id=correlation_id,
            events=events,
            interaction_type="message",
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

    def _extract_next_topic(
        self,
        events: list[Event],
    ) -> dict[str, Any] | None:
        for event in reversed(events):
            if event.type != EventType.NEXT_TOPIC:
                continue
            return {
                "knowledge_id": event.data.get("knowledge_id", ""),
                "name": event.data.get("name", ""),
                "difficulty": event.data.get("difficulty", 0.5),
                "reason": event.data.get("reason", ""),
                "alternatives": event.data.get("alternatives", []),
            }
        return None
    
    '''下面是结果提取+教学决策部分 负责会话的总结
    
    事件链（各 Agent 的发言记录）
        ↓
┌───────────────────────────────┐
│  _extract_agent_insights      │  ← 按 Agent 分类提取
│  _extract_teaching_response   │  ← 提取教学回复
│  _extract_next_topic          │  ← 提取推荐知识点
│  _build_teaching_decision     │  ← 多 Agent 投票决策
│  _build_interaction_result    │  ← 组装最终返回值
└───────────────────────────────┘
        ↓
  返回给前端的 JSON

    _get_interaction_events —— 从数据库捞事件链
    _extract_teaching_response —— 从事件链中提取教学回复:从一堆事件中，找到 TutorAgent 发布的 TEACHING_RESPONSE 事件
    _extract_next_topic —— 提取推荐的下一个知识点:找到 CurriculumAgent 发布的 NEXT_TOPIC 事件
    _extract_agent_insights —— 按 Agent 分类汇总:把事件链按 Agent 职责分成四堆，也就是各个agent的发言记录
    _build_teaching_decision —— 多 Agent 投票决策：基于四个 Agent 的输出，决定"下一步怎么教"
    这里是硬编码实现 ：优先级1：提问就回答 优先级2：沮丧/疲劳 → 先鼓励 优先级3：掌握度低 → 补救 优先级4：需要复习 → 复习
    优先级5：可以推进 → 推进 优先级6：默认继续练习
    可以改为LLM分析决策
    _build_interaction_result —— 组装最终返回值
    '''

    #按照agent分类进行
    #提取遍历整条事件链，按事件类型归类到对应 Agent。 最终得到一个"各 Agent 发言记录"。
    def _extract_agent_insights(self, events: list[Event]) -> dict[str, Any]:
        insights: dict[str, Any] = {
            "assessment": {},
            "tutor": {},
            "curriculum": {},
            "engagement": {},
        }
        for event in events:
            if event.type in {
                EventType.ASSESSMENT_COMPLETE,
                EventType.MASTERY_UPDATED,
                EventType.WEAKNESS_DETECTED,
            }:
                insights["assessment"].update(event.data)
            elif event.type == EventType.TEACHING_RESPONSE:
                insights["tutor"].update(event.data)
            elif event.type in {
                EventType.NEXT_TOPIC,
                EventType.REVIEW_SCHEDULED,
                EventType.REVIEW_REMINDER,
                EventType.LEARNING_PATH_UPDATE,
            }:
                insights["curriculum"].update(event.data)
            elif event.type in {
                EventType.ENGAGEMENT_ALERT,
                EventType.ENCOURAGEMENT,
                EventType.PACE_ADJUSTMENT,
                EventType.EMOTION_DETECTED,
            }:
                insights["engagement"].update(event.data)
        return insights

    async def _build_teaching_decision(
        self,
        learner_id: str,
        knowledge_id: str,
        interaction_type: str,
        insights: dict[str, Any],
    ) -> dict[str, Any]:
        assessment = insights.get("assessment", {})
        tutor = insights.get("tutor", {})
        curriculum = insights.get("curriculum", {})
        engagement = insights.get("engagement", {})

        assessment_strategy = assessment.get("assessment_strategy", {})
        curriculum_strategy = curriculum.get("curriculum_strategy", {})
        engagement_strategy = engagement.get("engagement_strategy", {})

        if interaction_type in {"question", "message"}:
            fallback_strategy = "answer_question"
            fallback_summary = "优先回答学生当前问题，并结合当前知识点上下文。"
            fallback_next = "继续围绕学生追问做针对性解释。"
        elif engagement_strategy.get("state") in {"frustrated", "fatigued"}:
            fallback_strategy = "encourage"
            fallback_summary = "学习状态需要干预，先降低压力并调整节奏。"
            fallback_next = engagement_strategy.get("suggestion", "先给一个更小的学习步骤。")
        elif assessment_strategy.get("recommended_action") == "remediate":
            fallback_strategy = "remediate"
            fallback_summary = "评估显示当前知识点存在薄弱，需要补救。"
            fallback_next = assessment_strategy.get("student_message", "先回到关键规则和相近例题。")
        elif curriculum_strategy.get("next_action") == "review":
            fallback_strategy = "review"
            fallback_summary = "存在复习或遗忘风险，优先安排复习。"
            fallback_next = curriculum_strategy.get("plan", "先处理到期复习项。")
        elif curriculum_strategy.get("next_action") == "advance":
            fallback_strategy = "advance"
            fallback_summary = "当前掌握度支持推进到下一个知识点。"
            fallback_next = curriculum_strategy.get("plan", "进入推荐的下一个知识点。")
        else:
            fallback_strategy = "practice"
            fallback_summary = "继续做相似练习以稳定掌握。"
            fallback_next = "再完成一题相似练习。"

        fallback = {
            "strategy": fallback_strategy,
            "priority": "high" if fallback_strategy in {"remediate", "encourage"} else "normal",
            "summary": fallback_summary,
            "next_action": fallback_next,
            "rationale": "由本地教学策略根据各 Agent 输出汇总生成。",
            "generation_mode": "local_policy",
            "agent_votes": {
                "assessment": assessment_strategy,
                "curriculum": curriculum_strategy,
                "engagement": engagement_strategy,
                "tutor": {
                    "context_type": tutor.get("context_type"),
                    "teaching_style": tutor.get("teaching_style"),
                    "generation_mode": tutor.get("generation_mode"),
                },
            },
        }

        if not settings.enable_agent_llm_decisions:
            return fallback

        response = await get_llm_service().generate_teaching_decision(
            {
                "learner_id": learner_id,
                "knowledge_id": knowledge_id,
                "interaction_type": interaction_type,
                "assessment": assessment,
                "tutor": tutor,
                "curriculum": curriculum,
                "engagement": engagement,
            }
        )
        if not response.content:
            return fallback
        try:
            parsed = json.loads(response.content)
        except Exception:
            return fallback

        parsed.setdefault("strategy", fallback["strategy"])
        parsed.setdefault("priority", fallback["priority"])
        parsed.setdefault("summary", fallback["summary"])
        parsed.setdefault("next_action", fallback["next_action"])
        parsed.setdefault("rationale", fallback["rationale"])
        parsed["generation_mode"] = "remote_llm"
        parsed["agent_votes"] = fallback["agent_votes"]
        return parsed

    async def _build_interaction_result(
        self,
        learner_id: str,
        knowledge_id: str,
        correlation_id: str,
        events: list[Event],
        interaction_type: str,
        evaluation: dict[str, Any] | None,
    ) -> dict[str, Any]:
        agent_insights = self._extract_agent_insights(events)
        teaching_decision = await self._build_teaching_decision(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            interaction_type=interaction_type,
            insights=agent_insights,
        )
        return {
            "learner_id": learner_id,
            "knowledge_id": knowledge_id,
            "correlation_id": correlation_id,
            "evaluation": evaluation,
            "teaching_response": self._extract_teaching_response(events, knowledge_id),
            "next_topic_recommendation": self._extract_next_topic(events),
            "review_snapshot": self.curriculum.get_review_snapshot(learner_id, knowledge_id),
            "agent_insights": agent_insights,
            "teaching_decision": teaching_decision,
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
        except Exception as exc:
            logger.warning("Failed to save learner state: %s", exc)

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
