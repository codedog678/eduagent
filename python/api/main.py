"""
FastAPI 应用入口。

启动方式：
    cd python/
    python -m api.main
    或
    uvicorn api.main:app --reload --port 8000
"""

import logging
import sys
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from api.websocket import ws_router
from api.orchestrator import AgentOrchestrator
from config.settings import settings
from core.llm_service import get_llm_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)

orchestrator: AgentOrchestrator | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global orchestrator

    # 创建编排器，启用数据库日志
    orchestrator = AgentOrchestrator(enable_db_logging=settings.enable_db_logging)
    app.state.orchestrator = orchestrator

    # 初始化数据库
    try:
        await orchestrator.init_database()
        logging.getLogger(__name__).info("Database initialized successfully")
    except Exception as e:
        logging.getLogger(__name__).error("Failed to initialize database: %s", e)

    llm_info = get_llm_service().runtime_info()
    logging.getLogger(__name__).info(
        "LLM status: enabled=%s provider=%s model=%s source=%s",
        llm_info["llm_enabled"],
        llm_info["provider"],
        llm_info["model"],
        llm_info["config_source"],
    )
    logging.getLogger(__name__).info("Agent orchestrator started with 4 agents")
    yield

    # 关闭数据库连接
    if orchestrator:
        await orchestrator.close_database()
    logging.getLogger(__name__).info("Shutting down")


app = FastAPI(
    title="英语学习智能教育系统",
    description=(
        "4-Agent Mesh+事件驱动架构的个性化英语学习系统。\n\n"
        "**Agent列表：**\n"
        "- Assessment Agent：知识点评估（BKT算法）\n"
        "- Tutor Agent：苏格拉底式教学 + 分级提示（LLM集成）\n"
        "- Curriculum Agent：学习路径规划 + 复习提醒（SM-2 + 遗忘曲线）\n"
        "- Engagement Agent：互动监测"
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(ws_router)

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="0.0.0.0", port=8888, reload=True)
