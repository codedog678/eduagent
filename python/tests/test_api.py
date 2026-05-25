"""
API 端点测试。

测试所有REST API端点的功能。
"""

import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.fixture
async def client():
    """创建测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_health_check(client):
    """测试健康检查端点。"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "multi-agent-education"
    assert data["agents"] == 4  # 现在有4个Agent


@pytest.mark.asyncio
async def test_submit_answer(client):
    """测试提交答案端点。"""
    response = await client.post(
        "/submit",
        json={
            "learner_id": "test_api_user_001",
            "knowledge_id": "vocab_basic",
            "is_correct": True,
            "time_spent_seconds": 30,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["events_triggered"] > 0


@pytest.mark.asyncio
async def test_submit_wrong_answer(client):
    """测试提交错误答案端点。"""
    response = await client.post(
        "/submit",
        json={
            "learner_id": "test_api_user_002",
            "knowledge_id": "grammar_tenses",
            "is_correct": False,
            "time_spent_seconds": 45,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"


@pytest.mark.asyncio
async def test_ask_question(client):
    """测试提问端点。"""
    response = await client.post(
        "/question",
        json={
            "learner_id": "test_api_user_003",
            "knowledge_id": "vocab_intermediate",
            "question": "What is the difference between 'affect' and 'effect'?",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"
    assert data["events_triggered"] > 0


@pytest.mark.asyncio
async def test_send_message(client):
    """测试发送消息端点。"""
    response = await client.post(
        "/message",
        json={
            "learner_id": "test_api_user_004",
            "message": "Can you explain the present perfect tense?",
            "knowledge_id": "grammar_tenses",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "processed"


@pytest.mark.asyncio
async def test_get_progress(client):
    """测试获取学习进度端点。"""
    # 先提交一些答案
    for i in range(3):
        await client.post(
            "/submit",
            json={
                "learner_id": "test_api_user_005",
                "knowledge_id": f"vocab_{i}",
                "is_correct": True,
                "time_spent_seconds": 20,
            },
        )

    # 获取进度
    response = await client.get("/progress/test_api_user_005")
    assert response.status_code == 200
    data = response.json()
    assert data["learner_id"] == "test_api_user_005"
    assert "progress" in data


@pytest.mark.asyncio
async def test_get_knowledge_graph(client):
    """测试获取知识图谱端点。"""
    response = await client.get("/knowledge-graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "learning_order" in data
    assert len(data["nodes"]) > 0


@pytest.mark.asyncio
async def test_get_analytics(client):
    """测试获取分析数据端点。"""
    # 先提交一些答案
    for i in range(5):
        await client.post(
            "/submit",
            json={
                "learner_id": "test_api_user_006",
                "knowledge_id": f"vocab_{i % 3}",
                "is_correct": i % 2 == 0,
                "time_spent_seconds": 25,
            },
        )

    # 获取分析数据
    response = await client.get("/analytics/test_api_user_006")
    assert response.status_code == 200
    data = response.json()
    assert "analytics" in data
    assert "weak_points" in data
    assert "learning_curve" in data


@pytest.mark.asyncio
async def test_get_analytics_overview(client):
    """测试获取整体统计端点。"""
    response = await client.get("/analytics/overview")
    assert response.status_code == 200
    data = response.json()
    assert "total_learners" in data
    assert "total_questions" in data
    assert "overall_accuracy" in data
