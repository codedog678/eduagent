"""
Feedback Service。

封装反馈相关的业务逻辑。
"""

import logging
from typing import Optional

from core.event_bus import Event, EventType

logger = logging.getLogger(__name__)


class FeedbackService:
    """反馈业务逻辑层。"""

    async def generate_feedback(
        self,
        learner_id: str,
        knowledge_id: str,
        assessment: dict,
        tutor: Optional[dict] = None,
        engagement: Optional[dict] = None,
        context: Optional[dict] = None,
    ) -> dict:
        """生成综合反馈。"""
        # 构建反馈摘要
        summary = self._build_summary(assessment, tutor, engagement)

        # 构建详细反馈
        detailed_feedback = self._build_detailed_feedback(assessment, tutor, engagement)

        # 构建鼓励
        encouragement = self._build_encouragement(assessment, engagement)

        # 构建下一步建议
        next_steps = self._build_next_steps(assessment, tutor)

        # 构建事件
        events = [{
            "type": EventType.FEEDBACK_GENERATED.value,
            "data": {
                "summary": summary,
                "knowledge_id": knowledge_id,
            },
        }]

        return {
            "summary": summary,
            "detailed_feedback": detailed_feedback,
            "encouragement": encouragement,
            "next_steps": next_steps,
            "events": events,
        }

    def _build_summary(
        self,
        assessment: dict,
        tutor: Optional[dict],
        engagement: Optional[dict],
    ) -> str:
        """构建反馈摘要。"""
        mastery_update = assessment.get("mastery_update", {})
        new_mastery = mastery_update.get("new_mastery", 0)
        is_weakness = assessment.get("is_weakness", False)

        if is_weakness:
            return f"掌握度 {new_mastery:.0%}，需要加强练习"
        elif new_mastery > 0.8:
            return f"掌握度 {new_mastery:.0%}，表现优秀！"
        else:
            return f"掌握度 {new_mastery:.0%}，继续努力！"

    def _build_detailed_feedback(
        self,
        assessment: dict,
        tutor: Optional[dict],
        engagement: Optional[dict],
    ) -> str:
        """构建详细反馈。"""
        parts = []

        # 评估反馈
        mastery_update = assessment.get("mastery_update", {})
        parts.append(f"掌握度从 {mastery_update.get('old_mastery', 0):.0%} "
                    f"提升到 {mastery_update.get('new_mastery', 0):.0%}")

        # 错误模式
        error_patterns = assessment.get("error_patterns", [])
        if error_patterns:
            pattern = error_patterns[0]
            parts.append(f"错误类型：{pattern.get('description', '')}")

        # 辅导反馈
        if tutor:
            if tutor.get("explanation"):
                parts.append(f"解释：{tutor['explanation']}")

        return "。".join(parts)

    def _build_encouragement(
        self,
        assessment: dict,
        engagement: Optional[dict],
    ) -> str:
        """构建鼓励。"""
        if engagement:
            emotion = engagement.get("emotion_state", {})
            if emotion.get("primary") == "frustrated":
                return "不要灰心，每个人都会犯错，重要的是从中学习！"
            elif emotion.get("primary") == "bored":
                return "试着挑战更难的题目，保持学习兴趣！"
            elif emotion.get("primary") == "fatigued":
                return "休息一下也很重要，回来后效率会更高！"

        mastery_update = assessment.get("mastery_update", {})
        delta = mastery_update.get("delta", 0)
        if delta > 0:
            return "有进步！继续保持！"
        elif delta == 0:
            return "保持稳定，继续练习会更好！"
        else:
            return "每次练习都是学习的机会，加油！"

    def _build_next_steps(
        self,
        assessment: dict,
        tutor: Optional[dict],
    ) -> list[str]:
        """构建下一步建议。"""
        steps = []

        is_weakness = assessment.get("is_weakness", False)
        if is_weakness:
            steps.append("复习相关知识点")
            steps.append("做更多练习题")

        if tutor and tutor.get("next_steps"):
            steps.extend(tutor["next_steps"])

        if not steps:
            steps.append("继续学习下一个知识点")

        return steps
