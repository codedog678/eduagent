"""
WebSocket 实时通信端点。

支持前端与Agent系统的双向实时通信：
- 学生发送消息/答题 → Agent处理 → 实时推送结果

"""

import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket连接管理器。"""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, learner_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[learner_id] = websocket
        logger.info("WebSocket connected: %s", learner_id)

    def disconnect(self, learner_id: str):
        self.active_connections.pop(learner_id, None)
        logger.info("WebSocket disconnected: %s", learner_id)

    async def send_to_learner(self, learner_id: str, data: dict):
        ws = self.active_connections.get(learner_id)
        if ws:
            await ws.send_json(data)


manager = ConnectionManager()


@ws_router.websocket("/ws/{learner_id}")
async def websocket_endpoint(websocket: WebSocket, learner_id: str):
    await manager.connect(learner_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            action = data.get("action", "")

            orch = websocket.app.state.orchestrator
            if action not in {"submit", "question", "message"}:
                await manager.send_to_learner(learner_id, {"error": f"Unknown action: {action}"})
                continue
            async def operation():
                if action == "submit":
                    result = await orch.submit_answer(
                        learner_id, data.get("knowledge_id", ""), data.get("is_correct", False),
                        data.get("time_spent_seconds", 0),
                        submission_context={"independent": False})
                elif action == "question":
                    result = await orch.ask_question(
                        learner_id, data.get("knowledge_id", ""), data.get("question", ""))
                else:
                    result = await orch.send_message(
                        learner_id, data.get("message", ""), data.get("knowledge_id", "general"))
                return result, None
            from fastapi import HTTPException
            try:
                result = await orch.harness.run(
                    learner_id, data.get("request_id") or str(uuid.uuid4()), data, operation)
            except HTTPException as exc:
                await websocket.send_json({"error": exc.detail, "status": exc.status_code})
                continue

            for event in result.get("interaction_events", []):
                await manager.send_to_learner(learner_id, event)

    except WebSocketDisconnect:
        manager.disconnect(learner_id)
    except Exception:
        logger.exception("WebSocket error for learner %s", learner_id)
        manager.disconnect(learner_id)
