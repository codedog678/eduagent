"""
Health API 路由。
"""

from fastapi import APIRouter

from config.settings import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查。"""
    from llm import get_llm

    llm = get_llm()
    llm_info = llm.runtime_info()

    return {
        "status": "ok",
        "service": "multi-agent-education",
        "agents": 4,
        "llm_enabled": llm_info["enabled"],
        "provider": llm_info["provider"],
        "model": llm_info["model"],
        "api_port": settings.api_port,
    }
