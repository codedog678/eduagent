"""
Assessment Service。

封装评估相关的业务逻辑。
"""

import logging
from typing import Optional

from core.event_bus import Event, EventType, EventPriority
from services.learner_service import LearnerService
from repositories.learning_record_repo import LearningRecordRepository

logger = logging.getLogger(__name__)


class AssessmentService:
    """评估业务逻辑层。"""

    def __init__(self) -> None:
        self.learner_service = LearnerService()
        self.record_repo = LearningRecordRepository()

    async def submit_answer(
        self,
        learner_id: str,
        knowledge_id: str,
        is_correct: bool,
        time_spent: float = 0,
        submission_context: Optional[dict] = None,
    ) -> dict:
        """提交答案并评估。"""
        # 1. 更新掌握度
        mastery_update = await self.learner_service.update_mastery(
            learner_id, knowledge_id, is_correct, time_spent
        )

        # 2. 创建学习记录
        await self.record_repo.create(
            learner_id=learner_id,
            knowledge_id=knowledge_id,
            is_correct=is_correct,
            time_spent_seconds=time_spent,
            question=submission_context.get("question", "") if submission_context else "",
            student_answer=submission_context.get("student_answer", "") if submission_context else "",
            correct_answer=submission_context.get("correct_answer", "") if submission_context else "",
            feedback=submission_context.get("feedback", "") if submission_context else "",
        )

        # 3. 分析错误模式
        error_patterns = self._analyze_error_patterns(
            learner_id, knowledge_id, is_correct, submission_context
        )

        # 4. 判断是否为薄弱点
        is_weakness = mastery_update["new_mastery"] < 0.4
        is_strong_point = mastery_update["new_mastery"] > 0.8

        # 5. 构建事件
        events = []
        events.append({
            "type": EventType.MASTERY_UPDATED.value,
            "data": mastery_update,
        })

        if is_weakness:
            events.append({
                "type": EventType.WEAKNESS_DETECTED.value,
                "data": {
                    "knowledge_id": knowledge_id,
                    "mastery": mastery_update["new_mastery"],
                },
            })

        return {
            "mastery_update": mastery_update,
            "error_patterns": error_patterns,
            "is_weakness": is_weakness,
            "is_strong_point": is_strong_point,
            "events": events,
        }

    def _analyze_error_patterns(
        self,
        learner_id: str,
        knowledge_id: str,
        is_correct: bool,
        submission_context: Optional[dict],
    ) -> list[dict]:
        """分析错误模式。"""
        if is_correct:
            return []

        # 简单的错误模式分析
        patterns = []

        if submission_context:
            question = submission_context.get("question", "")
            student_answer = submission_context.get("student_answer", "")
            correct_answer = submission_context.get("correct_answer", "")

            # 概念性错误：完全答错
            if student_answer and correct_answer:
                similarity = self._calculate_similarity(student_answer, correct_answer)
                if similarity < 0.3:
                    patterns.append({
                        "knowledge_id": knowledge_id,
                        "error_type": "conceptual",
                        "frequency": 1,
                        "description": "概念理解有误，答案与正确答案差异较大",
                    })
                elif similarity < 0.7:
                    patterns.append({
                        "knowledge_id": knowledge_id,
                        "error_type": "procedural",
                        "frequency": 1,
                        "description": "解题步骤有误，部分正确但不够完整",
                    })
                else:
                    patterns.append({
                        "knowledge_id": knowledge_id,
                        "error_type": "careless",
                        "frequency": 1,
                        "description": "粗心错误，答案接近正确但有小错误",
                    })

        return patterns

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的相似度（简单实现）。"""
        if not text1 or not text2:
            return 0.0

        # 简单的字符级相似度
        set1 = set(text1.lower())
        set2 = set(text2.lower())
        intersection = set1 & set2
        union = set1 | set2

        return len(intersection) / len(union) if union else 0.0
