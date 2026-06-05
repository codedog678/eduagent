"""
API v1 路由模块。
"""

from fastapi import APIRouter

from api.v1 import learner, knowledge, learning, quiz, analytics, review, health

api_router = APIRouter(prefix="/api")

api_router.include_router(health.router, tags=["health"])
api_router.include_router(learner.router, prefix="/learner", tags=["learner"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(learning.router, prefix="/learning", tags=["learning"])
api_router.include_router(quiz.router, prefix="/quiz", tags=["quiz"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(review.router, prefix="/review", tags=["review"])
