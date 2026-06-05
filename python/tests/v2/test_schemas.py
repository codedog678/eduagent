"""测试数据模型。"""

import pytest
from schemas.models import (
    AssessmentInput,
    AssessmentOutput,
    TutorInput,
    TutorOutput,
    CurriculumInput,
    CurriculumOutput,
    EngagementInput,
    EngagementOutput,
    SubmitAnswerRequest,
    AskQuestionRequest,
)


def test_assessment_input():
    """测试评估输入模型。"""
    input_data = AssessmentInput(
        learner_id="test_learner",
        knowledge_id="vocab_basic",
        is_correct=True,
        time_spent_seconds=30.0,
    )
    assert input_data.learner_id == "test_learner"
    assert input_data.knowledge_id == "vocab_basic"
    assert input_data.is_correct is True


def test_assessment_output():
    """测试评估输出模型。"""
    output = AssessmentOutput(
        mastery_update={
            "knowledge_id": "vocab_basic",
            "old_mastery": 0.5,
            "new_mastery": 0.6,
            "delta": 0.1,
            "attempts": 5,
            "correct_count": 3,
            "streak": 2,
            "confidence": 0.7,
        },
        is_weakness=False,
        is_strong_point=False,
    )
    assert output.mastery_update.new_mastery == 0.6
    assert output.is_weakness is False


def test_tutor_input():
    """测试辅导输入模型。"""
    input_data = TutorInput(
        learner_id="test_learner",
        knowledge_id="grammar_tenses",
        question="什么是现在完成时？",
    )
    assert input_data.learner_id == "test_learner"
    assert input_data.question == "什么是现在完成时？"


def test_tutor_output():
    """测试辅导输出模型。"""
    output = TutorOutput(
        response="现在完成时表示过去发生的动作对现在的影响。",
        explanation="现在完成时的结构是 have/has + 过去分词。",
        encouragement="继续努力！",
        next_steps=["复习一般过去时", "做更多练习题"],
    )
    assert "现在完成时" in output.response
    assert len(output.next_steps) == 2


def test_engagement_input():
    """测试参与度输入模型。"""
    input_data = EngagementInput(
        learner_id="test_learner",
        is_correct=True,
        time_spent_seconds=45.0,
    )
    assert input_data.learner_id == "test_learner"
    assert input_data.is_correct is True


def test_engagement_output():
    """测试参与度输出模型。"""
    output = EngagementOutput(
        emotion_state={
            "primary": "engaged",
            "confidence": 0.8,
            "indicators": ["参与度良好"],
        },
        is_engaged=True,
        needs_intervention=False,
    )
    assert output.is_engaged is True
    assert output.needs_intervention is False


def test_submit_answer_request():
    """测试提交答案请求模型。"""
    request = SubmitAnswerRequest(
        learner_id="test_learner",
        knowledge_id="vocab_basic",
        is_correct=True,
        time_spent_seconds=30.0,
    )
    assert request.learner_id == "test_learner"


def test_ask_question_request():
    """测试提问请求模型。"""
    request = AskQuestionRequest(
        learner_id="test_learner",
        knowledge_id="grammar_tenses",
        question="什么是现在完成时？",
    )
    assert request.question == "什么是现在完成时？"
