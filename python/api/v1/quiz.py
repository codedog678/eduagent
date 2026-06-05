"""
Quiz API 路由。
"""

from fastapi import APIRouter

from schemas.models import GenerateQuizRequest, SubmitQuizAnswerRequest
from core.llm_service import get_llm_service
from services.assessment_service import AssessmentService
from services.session_service import SessionService

router = APIRouter()

assessment_service = AssessmentService()
session_service = SessionService()


@router.post("/generate")
async def generate_quiz(req: GenerateQuizRequest):
    """生成测验题目。"""
    llm_service = get_llm_service()
    quiz = await llm_service.generate_question(req.knowledge_id, req.difficulty)
    return {"status": "ok", "quiz": quiz}


@router.post("/answer")
async def submit_quiz_answer(req: SubmitQuizAnswerRequest):
    """提交测验答案。"""
    llm_service = get_llm_service()

    # 评估答案
    if req.correct_answer:
        is_correct = req.student_answer.strip() == req.correct_answer.strip()
        feedback = llm_service.build_quiz_evaluation_feedback(
            knowledge_id=req.knowledge_id,
            question=req.question,
            student_answer=req.student_answer,
            correct_answer=req.correct_answer,
            explanation=req.explanation,
            is_correct=is_correct,
        )
    else:
        evaluation = await llm_service.evaluate_answer(
            knowledge_id=req.knowledge_id,
            question=req.question,
            student_answer=req.student_answer,
            correct_answer=req.correct_answer,
        )
        is_correct = evaluation.get("is_correct", False)
        feedback = evaluation.get("feedback", "")

    # 提交评估
    assessment = await assessment_service.submit_answer(
        learner_id=req.learner_id,
        knowledge_id=req.knowledge_id,
        is_correct=is_correct,
        time_spent=req.time_spent_seconds,
        submission_context={
            "question": req.question,
            "student_answer": req.student_answer,
            "correct_answer": req.correct_answer,
            "feedback": feedback,
            "explanation": req.explanation,
        },
    )

    # 收集所有事件
    all_events = assessment.get("events", [])

    return {
        "status": "ok",
        "is_correct": is_correct,
        "feedback": feedback,
        "assessment": assessment,
        "events": all_events,
    }
