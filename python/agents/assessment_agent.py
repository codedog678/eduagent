"""Assessment agent for mastery updates after student submissions."""

from __future__ import annotations

import logging
import json
from typing import Any, Optional

from agents.base import BaseAgent
from config.settings import settings
from core.event_bus import Event, EventBus, EventType
from core.learner_model import LearnerModel
from core.llm_service import get_llm_service

logger = logging.getLogger(__name__)


class AssessmentAgent(BaseAgent):
    """
    评估 Agent。

    职责：
    1. 更新学习者掌握度（BKT 算法）
    2. 分析错误模式（概念性/步骤性/粗心）
    3. 识别薄弱知识点
    4. 生成评估报告

    事件流：
    - 订阅: STUDENT_SUBMISSION
    - 发布: MASTERY_UPDATED, WEAKNESS_DETECTED, ASSESSMENT_COMPLETE
    """

    def __init__(
        self,
        event_bus: EventBus,
        learner_models: dict[str, LearnerModel] | None = None,
        name: str = "AssessmentAgent",
        **_: Any,
    ) -> None:
        super().__init__(
            name=name,
            event_bus=event_bus,
            description="评估学习者掌握度，分析错误模式",
            learner_models=learner_models,
        )
        # 错误模式分析配置
        self._error_patterns: dict[str, list[dict]] = {}  # learner_id -> error patterns
        self.register()

    def get_subscribed_events(self) -> list[EventType]:
        return [EventType.STUDENT_SUBMISSION]

    async def handle_event(self, event: Event) -> Optional[dict[str, Any]]:
        if event.type == EventType.STUDENT_SUBMISSION:
            return await self._handle_submission(event)
        return None

    async def _handle_submission(self, event: Event) -> dict[str, Any]:
        """处理学生提交。"""
        learner_id = event.learner_id
        data = event.data
        knowledge_id = data.get("knowledge_id", "")
        is_correct = data.get("is_correct", False)
        time_spent = data.get("time_spent_seconds", 0)

        # 1. 更新掌握度
        model = self.get_learner_model(learner_id)
        old_mastery = model.get_state(knowledge_id).mastery
        independent = data.get("independent", True)
        state = (model.update_mastery(knowledge_id, is_correct) if independent
                 else model.get_state(knowledge_id))

        # 2. 分析错误模式
        error_patterns = []
        if not is_correct:
            error_patterns = self._analyze_error_patterns(
                learner_id, knowledge_id, data
            )

        # 3. 判断是否为薄弱点
        is_weakness = state.mastery < 0.4 and state.attempts >= 3
        is_strong_point = state.mastery > 0.8 and state.streak >= 3
        strategy = await self._build_assessment_strategy(
            knowledge_id=knowledge_id,
            is_correct=is_correct,
            mastery=state.mastery,
            attempts=state.attempts,
            streak=state.streak,
            error_patterns=error_patterns,
            data=data,
        )

        # 4. 发布事件
        await self._publish_result_event(
            event_type=EventType.MASTERY_UPDATED,
            learner_id=learner_id,
            data={
                "knowledge_id": knowledge_id,
                "mastery": state.mastery,
                "level": state.level.value,
                "attempts": state.attempts,
                "streak": state.streak,
                "confidence": state.confidence,
                "is_weakness": is_weakness,
                "is_strong_point": is_strong_point,
                "assessment_strategy": strategy,
                "independent": independent,
                "is_correct": is_correct,
            },
            correlation_id=event.correlation_id,
        )

        if is_weakness:
            await self._publish_result_event(
                event_type=EventType.WEAKNESS_DETECTED,
                learner_id=learner_id,
                data={
                    "knowledge_id": knowledge_id,
                    "mastery": state.mastery,
                    "attempts": state.attempts,
                    "error_patterns": error_patterns,
                    "assessment_strategy": strategy,
                },
                correlation_id=event.correlation_id,
            )

        await self._publish_result_event(
            event_type=EventType.ASSESSMENT_COMPLETE,
            learner_id=learner_id,
            data={
                "knowledge_id": knowledge_id,
                "is_correct": is_correct,
                "mastery": state.mastery,
                "level": state.level.value,
                "overall_progress": model.get_overall_progress(),
                "error_patterns": error_patterns,
                "question": data.get("question", ""),
                "student_answer": data.get("student_answer", ""),
                "correct_answer": data.get("correct_answer", ""),
                "evaluation_feedback": data.get("evaluation_feedback", ""),
                "assessment_strategy": strategy,
                "protected_quiz": data.get("protected_quiz", False),
                "independent": independent,
            },
            correlation_id=event.correlation_id,
        )

        return {
            "mastery_update": {
                "knowledge_id": knowledge_id,
                "old_mastery": old_mastery,
                "new_mastery": state.mastery,
                "delta": state.mastery - old_mastery,
                "attempts": state.attempts,
                "correct_count": state.correct_count,
                "streak": state.streak,
                "confidence": state.confidence,
            },
            "error_patterns": error_patterns,
            "is_weakness": is_weakness,
            "is_strong_point": is_strong_point,
            "events": [],
        }

    async def _build_assessment_strategy(
        self,
        knowledge_id: str,
        is_correct: bool,
        mastery: float,
        attempts: int,
        streak: int,
        error_patterns: list[dict],
        data: dict,
    ) -> dict[str, Any]:
        """让 Assessment Agent 用 LLM 或本地策略给出诊断和动作建议。"""
        if is_correct and mastery >= 0.75:
            fallback_action = "advance"
            fallback_message = "这个知识点掌握不错，可以尝试更高一级的练习。"
            fallback_diagnosis = "掌握较稳定"
        elif is_correct:
            fallback_action = "practice"
            fallback_message = "这次答对了，但还可以继续练几题来稳固。"
            fallback_diagnosis = "掌握度正在提升"
        elif mastery < 0.3 or attempts >= 3:
            fallback_action = "remediate"
            fallback_message = "建议先回到关键规则和相近例题，补清楚再继续。"
            fallback_diagnosis = "当前知识点存在明显薄弱"
        else:
            fallback_action = "practice"
            fallback_message = "先针对这类题再做一轮相似练习。"
            fallback_diagnosis = "需要更多样本确认错因"

        fallback = {
            "diagnosis": fallback_diagnosis,
            "confidence": round(min(1.0, 0.45 + attempts * 0.08), 2),
            "recommended_action": fallback_action,
            "student_message": fallback_message,
            "generation_mode": "local_policy",
        }

        if not settings.enable_agent_llm_decisions:
            return fallback

        response = await get_llm_service().generate_assessment_strategy(
            {
                "knowledge_id": knowledge_id,
                "is_correct": is_correct,
                "mastery": mastery,
                "attempts": attempts,
                "streak": streak,
                "error_patterns": error_patterns,
                "question": data.get("question", ""),
                "student_answer": data.get("student_answer", ""),
                "correct_answer": data.get("correct_answer", ""),
            }
        )
        if not response.content:
            return fallback
        try:
            parsed = json.loads(response.content)
            if not isinstance(parsed, dict):
                return fallback
            if parsed.get("recommended_action", fallback_action) not in {"advance", "practice", "remediate"}:
                return fallback
            confidence = parsed.get("confidence", fallback["confidence"])
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                return fallback
            if any(not isinstance(parsed.get(k, fallback[k]), str)
                   for k in ("diagnosis", "student_message")):
                return fallback
        except Exception:
            return fallback

        parsed.setdefault("diagnosis", fallback["diagnosis"])
        parsed.setdefault("confidence", fallback["confidence"])
        parsed.setdefault("recommended_action", fallback["recommended_action"])
        parsed.setdefault("student_message", fallback["student_message"])
        parsed["generation_mode"] = "remote_llm"
        return parsed

    def _analyze_error_patterns(
        self, learner_id: str, knowledge_id: str, data: dict
    ) -> list[dict]:
        """分析错误模式。"""
        patterns = []

        question = data.get("question", "")
        student_answer = data.get("student_answer", "")
        correct_answer = data.get("correct_answer", "")

        if not student_answer or not correct_answer:
            return patterns

        # 计算相似度
        similarity = self._calculate_similarity(student_answer, correct_answer)

        # 分类错误类型
        if similarity < 0.3:
            error_type = "conceptual"
            description = "概念理解有误，答案与正确答案差异较大"
        elif similarity < 0.7:
            error_type = "procedural"
            description = "解题步骤有误，部分正确但不够完整"
        else:
            error_type = "careless"
            description = "粗心错误，答案接近正确但有小错误"

        pattern = {
            "knowledge_id": knowledge_id,
            "error_type": error_type,
            "frequency": 1,
            "description": description,
        }

        # 更新错误模式统计
        if learner_id not in self._error_patterns:
            self._error_patterns[learner_id] = []

        # 检查是否已有类似错误
        existing = None
        for p in self._error_patterns[learner_id]:
            if p["knowledge_id"] == knowledge_id and p["error_type"] == error_type:
                existing = p
                break

        if existing:
            existing["frequency"] += 1
        else:
            self._error_patterns[learner_id].append(pattern)

        return [pattern]

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度。"""
        if not text1 or not text2:
            return 0.0

        set1 = set(text1.lower())
        set2 = set(text2.lower())
        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 0.0

    def get_error_patterns(self, learner_id: str) -> list[dict]:
        """获取学习者的错误模式。"""
        return self._error_patterns.get(learner_id, [])
