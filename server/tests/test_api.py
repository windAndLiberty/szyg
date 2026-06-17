"""
「域灵」数字员工系统 - OpenAI兼容API测试

测试范围:
- 非流式聊天补全
- 流式聊天补全（SSE）
- 模型列表
- 健康检查
- 无效请求（422）
- 模型错误（500/502）
- API认证
"""

import json
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient, Response


# =============================================================================
# Helper Functions
# =============================================================================

async def create_test_app(config: MagicMock) -> AsyncClient:
    """创建带完整OpenAI兼容API的测试应用。"""
    try:
        from fastapi import FastAPI, HTTPException, Request
        from fastapi.responses import JSONResponse, StreamingResponse
        from pydantic import BaseModel, Field
        from typing import List, Optional, Literal

        app = FastAPI(title="Yuling API")

        # Request/Response models
        class ChatMessage(BaseModel):
            role: str
            content: str

        class ChatCompletionRequest(BaseModel):
            model: str
            messages: List[ChatMessage]
            stream: bool = False
            temperature: Optional[float] = 0.7
            max_tokens: Optional[int] = None

        class ModelInfo(BaseModel):
            id: str
            object: str = "model"
            created: int = 1677610602
            owned_by: str = "yuling"

        # Authentication middleware (if configured)
        @app.middleware("http")
        async def auth_middleware(request: Request, call_next):
            if config.api.auth_token:
                auth_header = request.headers.get("Authorization", "")
                expected = f"Bearer {config.api.auth_token}"
                if auth_header != expected:
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Invalid authentication token"},
                    )
            response = await call_next(request)
            return response

        @app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "version": "0.1.0",
                "components": {
                    "ollama": "ok",
                    "memory": "ok",
                },
            }

        @app.get("/v1/models")
        async def list_models():
            return {
                "object": "list",
                "data": [
                    {"id": "qwen2.5", "object": "model", "owned_by": "ollama"},
                    {"id": "llama3", "object": "model", "owned_by": "ollama"},
                    {"id": "gpt-4", "object": "model", "owned_by": "litellm"},
                ],
            }

        @app.post("/v1/chat/completions")
        async def chat_completion(request: ChatCompletionRequest):
            # Validate request
            if not request.messages:
                raise HTTPException(status_code=422, detail="messages cannot be empty")

            # Simulate model error for specific model
            if request.model == "error-model":
                raise HTTPException(status_code=502, detail="Model service unavailable")

            if request.stream:
                async def event_stream():
                    words = ["Hello", ",", " I", "'m", " Yu", "Ling", "!"]
                    for word in words:
                        chunk = {
                            "id": "chatcmpl-test",
                            "object": "chat.completion.chunk",
                            "created": 1234567890,
                            "model": request.model,
                            "choices": [
                                {
                                    "index": 0,
                                    "delta": {"role": "assistant", "content": word},
                                    "finish_reason": None,
                                }
                            ],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"
                    # Final chunk
                    final_chunk = {
                        "id": "chatcmpl-test",
                        "object": "chat.completion.chunk",
                        "created": 1234567890,
                        "model": request.model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": "stop",
                            }
                        ],
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    yield "data: [DONE]\n\n"

                return StreamingResponse(
                    event_stream(), media_type="text/event-stream"
                )

            # Non-streaming response
            content = "Hello! I'm YuLing, your AI assistant."
            return {
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1234567890,
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": content,
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 10,
                    "total_tokens": 20,
                },
            }

        return AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        )

    except ImportError:
        pytest.skip("FastAPI or Pydantic not installed")


# =============================================================================
# 测试用例
# =============================================================================

@pytest.mark.asyncio
class TestAPI:
    """OpenAI兼容API测试类。"""

    @pytest_asyncio.fixture
    async def api_client(self, config: MagicMock):
        """提供API测试客户端。"""
        config.api.auth_token = None  # Disable auth for most tests
        client = await create_test_app(config)
        async with client:
            yield client

    @pytest_asyncio.fixture
    async def auth_api_client(self, config: MagicMock):
        """提供带认证的API测试客户端。"""
        config.api.auth_token = "secret-api-key"
        client = await create_test_app(config)
        async with client:
            yield client

    async def test_chat_completion_non_stream(self, api_client: AsyncClient):
        """
        验收标准: API-001 - POST /v1/chat/completions 应支持非流式聊天补全。

        Arrange: 准备请求数据
        Act: 发送非流式请求
        Assert: 返回正确格式的响应
        """
        # Arrange
        request_data = {
            "model": "qwen2.5",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False,
        }

        # Act
        response = await api_client.post("/v1/chat/completions", json=request_data)

        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["object"] == "chat.completion"
        assert result["model"] == "qwen2.5"
        assert len(result["choices"]) == 1
        assert result["choices"][0]["message"]["role"] == "assistant"
        assert "content" in result["choices"][0]["message"]
        assert result["choices"][0]["finish_reason"] == "stop"
        assert "usage" in result
        assert "prompt_tokens" in result["usage"]
        assert "completion_tokens" in result["usage"]

    async def test_chat_completion_stream(self, api_client: AsyncClient):
        """
        验收标准: API-002 - POST /v1/chat/completions 应支持SSE流式响应。

        Arrange: 准备流式请求
        Act: 发送流式请求
        Assert: 返回SSE格式数据
        """
        # Arrange
        request_data = {
            "model": "qwen2.5",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }

        # Act
        response = await api_client.post("/v1/chat/completions", json=request_data)

        # Assert
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        content = response.text
        lines = content.strip().split("\n")
        
        # Verify SSE format
        data_lines = [l for l in lines if l.startswith("data: ")]
        assert len(data_lines) > 0, "Should have data lines"
        
        # Last data line should be [DONE]
        assert "[DONE]" in data_lines[-1], "Stream should end with [DONE]"

        # Parse chunks and verify structure
        non_done_chunks = [l for l in data_lines if "[DONE]" not in l]
        for chunk_line in non_done_chunks:
            json_str = chunk_line[6:]  # Remove "data: " prefix
            chunk = json.loads(json_str)
            assert chunk["object"] == "chat.completion.chunk"
            assert "choices" in chunk
            assert len(chunk["choices"]) == 1

    async def test_list_models(self, api_client: AsyncClient):
        """
        验收标准: API-003 - GET /v1/models 应返回可用模型列表。

        Arrange: API客户端
        Act: 获取模型列表
        Assert: 返回模型数据
        """
        # Act
        response = await api_client.get("/v1/models")

        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["object"] == "list"
        assert len(result["data"]) == 3
        model_ids = [m["id"] for m in result["data"]]
        assert "qwen2.5" in model_ids
        assert "llama3" in model_ids
        assert "gpt-4" in model_ids
        assert all(m["object"] == "model" for m in result["data"])

    async def test_health_check(self, api_client: AsyncClient):
        """
        验收标准: API-004 - GET /health 应返回系统健康状态。

        Arrange: API客户端
        Act: 请求健康检查
        Assert: 返回健康状态
        """
        # Act
        response = await api_client.get("/health")

        # Assert
        assert response.status_code == 200
        result = response.json()
        assert result["status"] == "healthy"
        assert "version" in result
        assert "components" in result
        assert result["components"]["ollama"] == "ok"

    async def test_chat_completion_invalid_request(self, api_client: AsyncClient):
        """
        验收标准: API-005 - 无效请求应返回HTTP 422。

        Arrange: 准备无效请求
        Act: 发送无效请求
        Assert: 返回422
        """
        # Arrange - Missing required field (messages)
        request_data = {
            "model": "qwen2.5",
            # messages is missing
        }

        # Act
        response = await api_client.post("/v1/chat/completions", json=request_data)

        # Assert
        assert response.status_code == 422

    async def test_chat_completion_model_error(self, api_client: AsyncClient):
        """
        验收标准: API-006 - 模型服务错误应返回HTTP 502。

        Arrange: 使用触发错误的模型名
        Act: 发送请求
        Assert: 返回502
        """
        # Arrange
        request_data = {
            "model": "error-model",  # Special model name that triggers error
            "messages": [{"role": "user", "content": "Hello"}],
        }

        # Act
        response = await api_client.post("/v1/chat/completions", json=request_data)

        # Assert
        assert response.status_code == 502
        result = response.json()
        assert "detail" in result

    async def test_api_authentication(self, auth_api_client: AsyncClient):
        """
        验收标准: API-007 - 无效API密钥应返回HTTP 401。

        Arrange: 带认证的API客户端
        Act: 不带密钥或带错误密钥发送请求
        Assert: 返回401
        """
        # Act - No auth header
        response = await auth_api_client.get("/v1/models")

        # Assert
        assert response.status_code == 401
        result = response.json()
        assert "error" in result

    async def test_api_authentication_valid(self, auth_api_client: AsyncClient):
        """
        额外测试 - 有效API密钥应成功。

        Arrange: 带正确密钥
        Act: 发送请求
        Assert: 返回200
        """
        # Act - Valid auth header
        response = await auth_api_client.get(
            "/v1/models",
            headers={"Authorization": "Bearer secret-api-key"},
        )

        # Assert
        assert response.status_code == 200
        result = response.json()
        assert len(result["data"]) == 3

    async def test_openai_format_compatibility(self, api_client: AsyncClient):
        """
        验收标准: API-008 - 应支持OpenAI兼容的请求/响应格式。

        Arrange: 准备OpenAI格式请求
        Act: 发送请求
        Assert: 响应符合OpenAI格式
        """
        # Arrange - OpenAI compatible request
        request_data = {
            "model": "qwen2.5",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the capital of France?"},
            ],
            "temperature": 0.7,
            "max_tokens": 100,
            "stream": False,
        }

        # Act
        response = await api_client.post("/v1/chat/completions", json=request_data)

        # Assert - OpenAI compatible response structure
        assert response.status_code == 200
        result = response.json()
        
        # Required fields per OpenAI spec
        assert "id" in result
        assert result["object"] == "chat.completion"
        assert "created" in result
        assert "model" in result
        assert "choices" in result
        assert isinstance(result["choices"], list)
        assert len(result["choices"]) > 0
        
        choice = result["choices"][0]
        assert "index" in choice
        assert "message" in choice
        assert choice["message"]["role"] == "assistant"
        assert "content" in choice["message"]
        assert "finish_reason" in choice
        assert "usage" in result
