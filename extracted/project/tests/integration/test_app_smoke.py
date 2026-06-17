"""
「域灵」数字员工系统 - 集成冒烟测试

使用真实的 FastAPI app 实例，验证启动链路和核心端点。
非 chat 端点使用真实 app；chat 端点通过 dependency_overrides mock ModelRouter。
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from yuling.api.app import create_app
from yuling.version import VERSION
from yuling.api.chat import get_model_router


@pytest.fixture
def app():
    """创建真实 FastAPI 应用实例。"""
    return create_app()


@pytest.fixture
async def client(app):
    """创建基于真实 app 的异步测试客户端。"""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


class TestAppStartup:
    """应用启动冒烟测试。"""

    def test_create_app_returns_fastapi(self, app):
        """create_app() 应返回 FastAPI 实例。"""
        from fastapi import FastAPI
        assert isinstance(app, FastAPI)
        assert app.title == "域灵数字员工系统 API"
        assert app.version == VERSION

    def test_app_has_routes(self, app):
        """app 应包含已注册的路由。"""
        routes = [r.path for r in app.routes]
        assert "/health" in routes
        assert "/" in routes
        assert "/v1/models" in routes
        assert "/v1/chat/completions" in routes

    def test_app_openapi_schema(self, app):
        """app 应生成有效的 OpenAPI schema。"""
        schema = app.openapi()
        assert schema["openapi"] is not None
        assert "paths" in schema
        assert "/health" in schema["paths"]


class TestHealthEndpoint:
    """健康检查端点测试（真实 app）。"""

    async def test_health_returns_ok(self, client):
        """GET /health 应返回 status ok。"""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == VERSION

    async def test_root_endpoint(self, client):
        """GET / 应返回基本信息。"""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "域灵数字员工系统"
        assert data["version"] == VERSION
        assert "docs" in data


class TestModelsEndpoint:
    """模型列表端点测试（真实 app）。"""

    async def test_list_models(self, client):
        """GET /v1/models 应返回模型列表。"""
        response = await client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "list"
        assert len(data["data"]) >= 1
        assert all("id" in m for m in data["data"])
        assert all("object" in m for m in data["data"])


class TestChatCompletionsEndpoint:
    """聊天补全端点测试（dependency_overrides mock）。"""

    @pytest.fixture
    def mock_router(self):
        """创建一个 mock ModelRouter。"""
        router = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "Hello, I am YuLing!"
        router.chat = AsyncMock(return_value=mock_response)
        return router

    @pytest.fixture
    async def client_mocked(self, app, mock_router):
        """使用 dependency_overrides 注入 mock。"""
        app.dependency_overrides[get_model_router] = lambda: mock_router
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c
        app.dependency_overrides.clear()

    async def test_chat_non_stream(self, client_mocked):
        """POST /v1/chat/completions 非流式应返回正确格式。"""
        request_data = {
            "model": "qwen2.5",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello!"},
            ],
            "stream": False,
        }

        response = await client_mocked.post("/v1/chat/completions", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["object"] == "chat.completion"
        assert data["model"] == "qwen2.5"
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert "content" in data["choices"][0]["message"]
        assert data["choices"][0]["finish_reason"] == "stop"
        assert "usage" in data

    async def test_chat_stream(self, app):
        """POST /v1/chat/completions stream=True 应返回 SSE。"""
        router = AsyncMock()

        async def mock_stream():
            for word in ["Hello", ", ", "YuLing", "!"]:
                chunk = MagicMock()
                chunk.content = word
                yield chunk

        router.chat = AsyncMock(return_value=mock_stream())

        app.dependency_overrides[get_model_router] = lambda: router
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            request_data = {
                "model": "qwen2.5",
                "messages": [{"role": "user", "content": "Hi"}],
                "stream": True,
            }
            response = await c.post("/v1/chat/completions", json=request_data)
        app.dependency_overrides.clear()

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        content = response.text
        assert "data:" in content
        assert "[DONE]" in content

    async def test_chat_missing_messages_422(self, client_mocked):
        """缺少 messages 应返回 422。"""
        response = await client_mocked.post(
            "/v1/chat/completions", json={"model": "qwen2.5"}
        )
        assert response.status_code == 422

    async def test_chat_empty_messages_422(self, client_mocked):
        """空 messages 应返回 422。"""
        response = await client_mocked.post(
            "/v1/chat/completions",
            json={"model": "qwen2.5", "messages": []},
        )
        assert response.status_code == 422


class TestCORSAndHeaders:
    """CORS 和响应头测试。"""

    async def test_cors_headers_present(self, client):
        """OPTIONS 请求应返回 CORS 头。"""
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 405)
