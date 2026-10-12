"""REST API routes for the education workflow."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel

from config.settings import settings

router = APIRouter(tags=["education"])


class SubmitAnswerRequest(BaseModel):
    learner_id: str
    knowledge_id: str
    is_correct: bool
    time_spent_seconds: float = 0


class AskQuestionRequest(BaseModel):
    learner_id: str
    knowledge_id: str
    question: str


class SendMessageRequest(BaseModel):
    learner_id: str
    message: str
    knowledge_id: str = "general"


class GenerateQuizRequest(BaseModel):
    knowledge_id: str
    difficulty: float = 0.5


class SubmitQuizAnswerRequest(BaseModel):
    learner_id: str
    knowledge_id: str
    question: str
    student_answer: str
    correct_answer: str = ""
    explanation: str = ""
    time_spent_seconds: float = 0


def _with_status(result: dict, status: str = "processed") -> dict:
    return {"status": status, **result}


@router.get("/health")
async def health_check():
    from core.llm_service import get_llm_service

    llm_info = get_llm_service().runtime_info()
    return {
        "status": "ok",
        "service": "multi-agent-education",
        "agents": 4,
        "llm_enabled": llm_info["llm_enabled"],
        "provider": llm_info["provider"],
        "model": llm_info["model"],
        "config_source": llm_info["config_source"],
        "api_port": settings.api_port,
    }


@router.post("/demo/init")
async def init_demo_data(learner_id: str, request: Request):
    orch = request.app.state.orchestrator
    orch.seed_demo_data(learner_id)
    return {"status": "ok", "message": f"Demo data seeded for {learner_id}"}


@router.post("/submit")
async def submit_answer(req: SubmitAnswerRequest, request: Request):
    orch = request.app.state.orchestrator
    result = await orch.submit_answer(
        learner_id=req.learner_id,
        knowledge_id=req.knowledge_id,
        is_correct=req.is_correct,
        time_spent=req.time_spent_seconds,
        evaluation={
            "is_correct": req.is_correct,
            "feedback": "Your answer has been recorded. The tutor will guide you based on this result.",
        },
    )
    return _with_status(result)


@router.post("/question")
async def ask_question(req: AskQuestionRequest, request: Request):
    orch = request.app.state.orchestrator
    result = await orch.ask_question(req.learner_id, req.knowledge_id, req.question)
    return _with_status(result)


@router.post("/message")
async def send_message(req: SendMessageRequest, request: Request):
    orch = request.app.state.orchestrator
    result = await orch.send_message(req.learner_id, req.message, req.knowledge_id)
    return _with_status(result)


@router.get("/progress/{learner_id}")
async def get_progress(learner_id: str, request: Request):
    orch = request.app.state.orchestrator
    return await orch.get_learner_progress(learner_id)


@router.get("/knowledge-graph")
async def get_knowledge_graph(request: Request):
    orch = request.app.state.orchestrator
    graph = orch.curriculum.knowledge_graph
    return {
        "nodes": [
            {
                "id": node.id,
                "name": node.name,
                "difficulty": node.difficulty,
                "prerequisites": node.prerequisites,
                "tags": node.tags,
            }
            for node in graph.nodes.values()
        ],
        "learning_order": graph.topological_sort(),
    }


@router.get("/analytics/overview")
async def get_analytics_overview(request: Request):
    try:
        from models.database import Learner, LearningRecord
        from models.session import async_session
        from sqlalchemy import func, select

        async with async_session() as session:
            total_learners = await session.scalar(select(func.count(Learner.id)))
            total_questions = await session.scalar(select(func.count(LearningRecord.id)))
            total_correct = await session.scalar(
                select(func.count(LearningRecord.id)).where(LearningRecord.is_correct == True)
            )

            accuracy = 0.0
            if total_questions:
                accuracy = total_correct / total_questions

            return {
                "total_learners": total_learners or 0,
                "total_questions": total_questions or 0,
                "total_correct_answers": total_correct or 0,
                "overall_accuracy": round(accuracy, 3),
            }
    except Exception as exc:
        return {
            "total_learners": 0,
            "total_questions": 0,
            "total_correct_answers": 0,
            "overall_accuracy": 0.0,
            "error": str(exc),
        }


@router.get("/analytics/{learner_id}")
async def get_analytics(learner_id: str, request: Request):
    orch = request.app.state.orchestrator
    model = await orch.get_learner_model(learner_id)
    progress = model.get_overall_progress()

    weak_points = [
        {
            "knowledge_id": state.knowledge_id,
            "mastery": state.mastery,
            "attempts": state.attempts,
            "correct_count": state.correct_count,
            "accuracy": round(state.correct_count / state.attempts, 3) if state.attempts else 0.0,
        }
        for state in model.get_weak_points(threshold=0.4, limit=5)
    ]

    total_time_spent_seconds = 0.0
    last_activity = None
    learning_curve = []
    try:
        from models.database import LearningRecord
        from models.session import async_session
        from sqlalchemy import select

        async with async_session() as session:
            result = await session.execute(
                select(LearningRecord)
                .where(LearningRecord.learner_id == learner_id)
                .order_by(LearningRecord.created_at.desc())
                .limit(20)
            )
            records = result.scalars().all()
            if records:
                total_time_spent_seconds = sum((record.time_spent_seconds or 0) for record in records)
                last_activity = records[0].created_at.isoformat()
                learning_curve = [
                    {
                        "timestamp": record.created_at.isoformat(),
                        "type": "assessment",
                        "knowledge_id": record.knowledge_id,
                        "is_correct": record.is_correct,
                    }
                    for record in reversed(records)
                ]
    except Exception:
        learning_curve = []

    total_questions = progress.get("total_attempts", 0)
    level_distribution = progress.get("level_distribution", {})
    return {
        "analytics": {
            "learner_id": learner_id,
            "total_sessions": 1 if total_questions else 0,
            "total_time_spent_minutes": round(total_time_spent_seconds / 60, 1),
            "total_questions": total_questions,
            "correct_answers": progress.get("total_correct", 0),
            "wrong_answers": progress.get("total_wrong", 0),
            "accuracy": progress.get("accuracy", 0.0),
            "hints_used": orch.tutor.get_hint_usage(learner_id),
            "knowledge_points_covered": list(model.knowledge_states.keys()),
            "avg_time_per_question": round(total_time_spent_seconds / total_questions, 1)
            if total_questions
            else 0.0,
            "last_activity": last_activity,
        },
        "knowledge_distribution": {
            "not_started": level_distribution.get("not_started", 0),
            "beginner": level_distribution.get("beginner", 0),
            "developing": level_distribution.get("developing", 0),
            "proficient": level_distribution.get("proficient", 0),
            "mastered": level_distribution.get("mastered", 0),
        },
        "weak_points": weak_points,
        "learning_curve": learning_curve,
    }


@router.get("/review-schedule/{learner_id}")
async def get_review_schedule(learner_id: str, request: Request):
    orch = request.app.state.orchestrator
    items = list(orch.curriculum._review_items.get(learner_id, {}).values())
    weekly_schedule = orch.curriculum.sr.get_study_schedule(items, days_ahead=7)

    forgetting_status = []
    model = orch.get_learner_model_sync(learner_id)
    for item in items:
        if not item.last_review:
            continue
        days_since_review = (datetime.now() - item.last_review).total_seconds() / 86400
        forgetting_status.append(
            {
                "knowledge_id": item.knowledge_id,
                "retention": round(
                    model.get_forgetting_curve(item.knowledge_id, days_since_review), 3
                ),
                "days_since_review": round(days_since_review, 1),
                "is_due": item.is_due,
                "next_review": item.next_review.isoformat(),
            }
        )

    return {
        "reminders": orch.curriculum.get_reminders(learner_id),
        "due_items": orch.curriculum.get_top_due_items(learner_id, limit=10),
        "weekly_schedule": weekly_schedule,
        "forgetting_status": sorted(forgetting_status, key=lambda item: item["retention"])[:10],
        "total_items": len(items),
    }


@router.post("/review/complete")
async def complete_review(learner_id: str, knowledge_id: str, quality: int, request: Request):
    orch = request.app.state.orchestrator
    items = orch.curriculum._review_items.get(learner_id, {})
    item = items.get(knowledge_id)
    if item is None:
        return {"status": "error", "message": "Review item not found"}

    orch.curriculum.sr.review(item, quality)
    orch.curriculum.clear_reminder(learner_id, knowledge_id)
    return {
        "status": "ok",
        "next_review": item.next_review.isoformat(),
        "interval_days": item.interval_days,
        "easiness_factor": item.easiness_factor,
    }


@router.post("/quiz/generate")
async def generate_quiz(req: GenerateQuizRequest, request: Request):
    from core.llm_service import get_llm_service

    quiz = await get_llm_service().generate_question(req.knowledge_id, req.difficulty)
    return {"status": "ok", "quiz": quiz}


@router.post("/quiz/answer")
async def submit_quiz_answer(req: SubmitQuizAnswerRequest, request: Request):
    orch = request.app.state.orchestrator
    from core.llm_service import get_llm_service

    llm_service = get_llm_service()

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

    result = await orch.submit_answer(
        learner_id=req.learner_id,
        knowledge_id=req.knowledge_id,
        is_correct=is_correct,
        time_spent=req.time_spent_seconds,
        submission_context={
            "question": req.question,
            "student_answer": req.student_answer,
            "correct_answer": req.correct_answer,
            "evaluation_feedback": feedback,
            "explanation": req.explanation,
        },
        evaluation={
            "is_correct": is_correct,
            "feedback": feedback,
            "student_answer": req.student_answer,
            "correct_answer": req.correct_answer,
        },
    )
    return _with_status(result)


@router.get("/statistics/{learner_id}")
async def get_statistics(learner_id: str, request: Request):
    """Get aggregate statistics from learning_records."""
    from models.database import LearningRecord
    from models.session import async_session
    from sqlalchemy import func, select

    async with async_session() as session:
        total_questions = await session.scalar(
            select(func.count(LearningRecord.id)).where(LearningRecord.learner_id == learner_id)
        )
        correct_answers = await session.scalar(
            select(func.count(LearningRecord.id))
            .where(LearningRecord.learner_id == learner_id)
            .where(LearningRecord.is_correct == True)
        )
        total_time = await session.scalar(
            select(func.sum(LearningRecord.time_spent_seconds)).where(
                LearningRecord.learner_id == learner_id
            )
        )
        avg_time = await session.scalar(
            select(func.avg(LearningRecord.time_spent_seconds)).where(
                LearningRecord.learner_id == learner_id
            )
        )
        last_record = await session.execute(
            select(LearningRecord.created_at)
            .where(LearningRecord.learner_id == learner_id)
            .order_by(LearningRecord.created_at.desc())
            .limit(1)
        )
        last_activity = last_record.scalar_one_or_none()

    total_q = total_questions or 0
    correct_a = correct_answers or 0
    total_t = total_time or 0
    avg_t = avg_time or 0

    return {
        "total_questions": total_q,
        "correct_answers": correct_a,
        "wrong_answers": total_q - correct_a,
        "accuracy": round(correct_a / total_q, 3) if total_q > 0 else 0.0,
        "total_time_minutes": round(total_t / 60, 1),
        "avg_time_per_question": round(avg_t, 1),
        "last_activity": last_activity.isoformat() if last_activity else None,
    }
