"""REST API routes for the education workflow."""

from __future__ import annotations

from datetime import datetime

import uuid
import json
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from config.settings import settings

router = APIRouter(tags=["education"])


class SubmitAnswerRequest(BaseModel):
    learner_id: str
    knowledge_id: str
    is_correct: bool
    time_spent_seconds: float = 0
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=128)


class AskQuestionRequest(BaseModel):
    learner_id: str
    knowledge_id: str
    question: str = Field(min_length=1, max_length=6000)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=128)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    thread_id: str | None = Field(default=None, min_length=1, max_length=128)
    quiz_id: str | None = Field(default=None, min_length=1, max_length=128)


class SendMessageRequest(BaseModel):
    learner_id: str
    message: str = Field(min_length=1, max_length=6000)
    knowledge_id: str = "general"
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()), min_length=1, max_length=128)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    thread_id: str | None = Field(default=None, min_length=1, max_length=128)
    quiz_id: str | None = Field(default=None, min_length=1, max_length=128)


class GenerateQuizRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    learner_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    knowledge_id: str
    difficulty: float = Field(default=0.5, ge=0, le=1)
    mode: Literal["practice", "advance"] = "practice"
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    thread_id: str | None = Field(default=None, min_length=1, max_length=128)


class SubmitQuizAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    learner_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    quiz_id: str = Field(min_length=1, max_length=128)
    selected_index: int = Field(ge=0, strict=True)
    time_spent_seconds: float = Field(default=0, ge=0, le=86400, allow_inf_nan=False)
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)


class QuizSupportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    learner_id: str = Field(min_length=1, max_length=128)
    request_id: str = Field(min_length=1, max_length=128)
    quiz_id: str = Field(min_length=1, max_length=128)


async def _execute(orch, req, operation):
    async def wrapped():
        return await operation(), None
    return await orch.harness.run(req.learner_id, req.request_id, req.model_dump(), wrapped)


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
    async def operation():
        orch.seed_demo_data(learner_id)
        return {"status": "ok", "message": f"Demo data seeded for {learner_id}"}, None
    return await orch.harness.run(learner_id, str(uuid.uuid4()), {"kind": "demo"}, operation)


@router.post("/submit")
async def submit_answer(req: SubmitAnswerRequest, request: Request):
    orch = request.app.state.orchestrator
    result = await _execute(orch, req, lambda: orch.submit_answer(
        learner_id=req.learner_id,
        knowledge_id=req.knowledge_id,
        is_correct=req.is_correct,
        time_spent=req.time_spent_seconds,
        evaluation={
            "is_correct": req.is_correct,
            "feedback": "自我报告已记录，仅用于反思，不作为测验掌握度证据。",
        },
        submission_context={"independent": False},
    ))
    return _with_status(result)


@router.post("/question")
async def ask_question(req: AskQuestionRequest, request: Request):
    orch = request.app.state.orchestrator
    result = await orch.harness.converse(
        req.learner_id, req.request_id, req.knowledge_id, req.question,
        req.session_id, req.thread_id, req.quiz_id)
    return _with_status(result)


@router.post("/message")
async def send_message(req: SendMessageRequest, request: Request):
    orch = request.app.state.orchestrator
    result = await orch.harness.converse(
        req.learner_id, req.request_id, req.knowledge_id, req.message,
        req.session_id, req.thread_id, req.quiz_id, kind="message")
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
    orch = request.app.state.orchestrator
    if orch.harness:
        states = [json.loads(row[0]) for row in
                  orch.harness.db.execute("SELECT state FROM checkpoints").fetchall()]
        attempts = sum(item["attempts"] for state in states for item in state["knowledge"].values())
        correct = sum(item["correct_count"] for state in states for item in state["knowledge"].values())
        return {"total_learners": len(states), "total_questions": attempts,
                "total_correct_answers": correct,
                "overall_accuracy": round(correct / attempts, 3) if attempts else 0}
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
    evidence = model.metadata.get("learning_evidence", [])
    if evidence:
        total_time_spent_seconds = sum(item.get("elapsed", 0) for item in evidence)
        last_activity = datetime.fromtimestamp(evidence[-1]["timestamp"]).isoformat()
        learning_curve = [
            {"timestamp": datetime.fromtimestamp(item["timestamp"]).isoformat(),
             "type": "独立作答" if item["independent"] else "辅助练习",
             "knowledge_id": item["knowledge_id"], "is_correct": item["is_correct"]}
            for item in evidence[-20:]]
    return {
        "analytics": {
            "learner_id": learner_id,
            "total_sessions": 1 if total_questions else 0,
            "total_time_spent_minutes": round(total_time_spent_seconds / 60, 1),
            "total_questions": total_questions,
            "correct_answers": progress.get("total_correct", 0),
            "wrong_answers": progress.get("total_wrong", 0),
            "accuracy": progress.get("accuracy", 0.0),
            "hints_used": model.metadata.get("hints_used", 0),
            "guided_attempts": sum(not item["independent"] for item in evidence),
            "answers_revealed": model.metadata.get("answers_revealed", 0),
            "knowledge_points_covered": list(model.knowledge_states.keys()),
            "avg_time_per_question": round(total_time_spent_seconds / max(1, len(evidence)), 1),
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
    await orch.get_learner_model(learner_id)
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
    raise HTTPException(410, "请通过测验作答完成复习，复习计划由服务端统一更新")


@router.post("/quiz/generate")
async def generate_quiz(req: GenerateQuizRequest, request: Request):
    return await request.app.state.orchestrator.harness.generate(
        req.learner_id, req.request_id, req.knowledge_id, req.difficulty, req.mode,
        req.session_id, req.thread_id)


@router.post("/quiz/answer")
async def submit_quiz_answer(req: SubmitQuizAnswerRequest, request: Request):
    result = await request.app.state.orchestrator.harness.answer(
        req.learner_id, req.request_id, req.quiz_id, req.selected_index,
        req.time_spent_seconds, req.confidence)
    return _with_status(result)


@router.post("/quiz/hint")
async def quiz_hint(req: QuizSupportRequest, request: Request):
    return await request.app.state.orchestrator.harness.support(
        req.learner_id, req.request_id, req.quiz_id, "hint")


@router.post("/quiz/reveal")
async def quiz_reveal(req: QuizSupportRequest, request: Request):
    return await request.app.state.orchestrator.harness.support(
        req.learner_id, req.request_id, req.quiz_id, "reveal")


@router.get("/statistics/{learner_id}")
async def get_statistics(learner_id: str, request: Request):
    """Get aggregate statistics from learning_records."""
    orch = request.app.state.orchestrator
    if orch.harness:
        model = await orch.get_learner_model(learner_id)
        progress = model.get_overall_progress()
        evidence = model.metadata.get("learning_evidence", [])
        elapsed = sum(item.get("elapsed", 0) for item in evidence)
        return {
            "total_questions": progress.get("total_attempts", 0),
            "correct_answers": progress.get("total_correct", 0),
            "wrong_answers": progress.get("total_wrong", 0),
            "accuracy": progress.get("accuracy", 0),
            "total_time_minutes": round(elapsed / 60, 1),
            "avg_time_per_question": round(elapsed / max(1, len(evidence)), 1),
            "last_activity": datetime.fromtimestamp(evidence[-1]["timestamp"]).isoformat() if evidence else None,
            "evidence_window": len(evidence),
        }
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


@router.get("/runs/{learner_id}/{request_id}")
async def get_run(learner_id: str, request_id: str, request: Request):
    return request.app.state.orchestrator.harness.run_status(learner_id, request_id)


@router.get("/runs/{learner_id}/{request_id}/trace")
async def get_trace(learner_id: str, request_id: str, request: Request):
    return request.app.state.orchestrator.harness.history.trace(learner_id, request_id)


@router.get("/history/{learner_id}")
async def get_history(learner_id: str, request: Request, thread_id: str | None = None,
                      limit: int = Query(default=20, ge=1, le=20),
                      before: int | None = Query(default=None, ge=1), knowledge_id: str | None = None):
    history = request.app.state.orchestrator.harness.history
    result = history.messages(learner_id, thread_id, limit, before, knowledge_id)
    if thread_id:
        result["pending_question"] = history.pending(learner_id, thread_id)
    return result


@router.get("/history/{learner_id}/source")
async def read_history_source(learner_id: str, source_ref: str, request: Request):
    return request.app.state.orchestrator.harness.history.read(learner_id, source_ref)
