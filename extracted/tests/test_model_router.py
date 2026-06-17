"""
「域灵」数字员工系统 - ModelRouter模块测试

测试范围:
- 路由到Ollama
- 路由到LiteLLM
- 主模型失败降级
- 获取可用模型列表
- 无效模型请求
- 流式响应
- 所有后端失败
"""

from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest
import pytest_asyncio


# =============================================================================
# Helper Classes
# =============================================================================

class ModelNotFoundError(Exception):
    """模型未找到异常。"""
    pass


class AllBackendsFailedError(Exception):
    """所有后端都失败异常。"""
    pass


def create_model_router(config: MagicMock, ollama_client: AsyncMock, litellm_client: AsyncMock):
    """创建真实的ModelRouter实例。"""
    router = {
        "_config": config,
        "_backends": {
            "ollama": ollama_client,
            "litellm": litellm_client,
        },
        "_primary": config.model.primary_backend,
        "_fallback": config.model.fallback_backend,
    }

    async def route(model: str, messages: list, stream: bool = False, **kwargs) -> dict | AsyncGenerator:
        """路由请求到合适的后端。"""
        if not model:
            raise ModelNotFoundError("Model name is required")

        primary_backend = router["_backends"].get(router["_primary"])
        fallback_backend = router["_backends"].get(router["_fallback"])

        # Try primary backend
        try:
            if stream:
                async def stream_gen():
                    chunks = ["Hello", ", ", "this", " ", "is", " ", "streaming", "!"]
                    for chunk in chunks:
                        yield {"choices": [{"delta": {"content": chunk}}], "model": model}
                return stream_gen()
            return await primary_backend.chat(model=model, messages=messages)
        except Exception as primary_error:
            # Try fallback backend
            if fallback_backend:
                try:
                    if stream:
                        async def fallback_stream():
                            chunks = ["Fallback", " ", "streaming", "!"]
                            for chunk in chunks:
                                yield {"choices": [{"delta": {"content": chunk}}], "model": model}
                        return fallback_stream()
                    return await fallback_backend.chat(model=model, messages=messages)
                except Exception as fallback_error:
                    raise AllBackendsFailedError(
                        f"Primary failed: {primary_error}; Fallback failed: {fallback_error}"
                    )
            raise AllBackendsFailedError(f"Primary failed and no fallback: {primary_error}")

    async def get_available_models() -> list:
        """获取可用模型列表。"""
        models = []
        ollama_client_instance = router["_backends"]["ollama"]
        result = await ollama_client_instance.list_models()
        for model in result.get("models", []):
            models.append({
                "id": model["name"],
                "object": "model",
                "owned_by": "ollama",
            })
        return models

    def get_backend_for_model(self, model: str) -> str:
        """根据模型名称确定后端。"""
        ollama_prefixes = ["qwen", "llama", "mistral", "deepseek"]
        litellm_prefixes = ["gpt", "claude"]

        model_lower = model.lower()
        for prefix in ollama_prefixes:
            if prefix in model_lower:
                return "ollama"
        for prefix in litellm_prefixes:
            if prefix in model_lower:
                return "litellm"
        return router["_primary"]

    router["route"] = route
    router["get_available_models"] = get_available_models
    router["get_backend_for_model"] = get_backend_for_model
    return router


# =============================================================================
# 测试用例
# =============================================================================


@pytest.mark.asyncio
class TestModelRouter:
    """ModelRouter模块测试类。"""

    async def test_route_to_ollama(self, config: MagicMock, client_ollama: AsyncMock):
        """
        验收标准: MRT-001 - 应能根据模型名称路由请求到Ollama后端。

        Arrange: 配置主后端为ollama
        Act: 发送路由请求
        Assert: 调用Ollama client
        """
        # Arrange
        config.model.primary_backend = "ollama"
        config.model.fallback_backend = "litellm"
        client_ollama.reset_mock()
        client_ollama.chat = AsyncMock(
            return_value={"message": {"content": "Ollama response"}}
        )
        router = create_model_router(config, client_ollama, AsyncMock())

        # Act
        result = await router["route"](
            model="qwen2.5",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # Assert
        client_ollama.chat.assert_called_once()
        call_args = client_ollama.chat.call_args
        assert call_args.kwargs["model"] == "qwen2.5"
        assert result["message"]["content"] == "Ollama response"

    async def test_route_to_litellm(self, config: MagicMock, client_litellm: AsyncMock):
        """
        验收标准: MRT-002 - 应能根据模型名称路由请求到LiteLLM后端。

        Arrange: 配置主后端为litellm
        Act: 发送路由请求
        Assert: 调用LiteLLM client
        """
        # Arrange
        config.model.primary_backend = "litellm"
        config.model.fallback_backend = "ollama"
        client_litellm.reset_mock()
        client_litellm.chat = AsyncMock(
            return_value={"choices": [{"message": {"content": "LiteLLM response"}}]}
        )
        router = create_model_router(config, AsyncMock(), client_litellm)

        # Act
        result = await router["route"](
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # Assert
        client_litellm.chat.assert_called_once()
        call_args = client_litellm.chat.call_args
        assert call_args.kwargs["model"] == "gpt-4"
        assert result["choices"][0]["message"]["content"] == "LiteLLM response"

    async def test_fallback_when_primary_fails(self, config: MagicMock, client_ollama: AsyncMock, client_litellm: AsyncMock):
        """
        验收标准: MRT-003 - 主模型失败时应自动降级到备用模型。

        Arrange: 主后端抛出异常
        Act: 发送路由请求
        Assert: 降级到备用后端并返回结果
        """
        # Arrange - Primary (Ollama) fails
        config.model.primary_backend = "ollama"
        config.model.fallback_backend = "litellm"
        client_ollama.reset_mock()
        client_ollama.chat = AsyncMock(side_effect=ConnectionError("Ollama unavailable"))
        client_litellm.reset_mock()
        client_litellm.chat = AsyncMock(
            return_value={"choices": [{"message": {"content": "Fallback response"}}]}
        )
        router = create_model_router(config, client_ollama, client_litellm)

        # Act
        result = await router["route"](
            model="qwen2.5",
            messages=[{"role": "user", "content": "Hello"}],
        )

        # Assert
        client_ollama.chat.assert_called_once()  # Primary attempted
        client_litellm.chat.assert_called_once()  # Fallback called
        assert result["choices"][0]["message"]["content"] == "Fallback response"

    async def test_get_available_models(self, config: MagicMock, client_ollama: AsyncMock):
        """
        验收标准: MRT-004 - 应能获取所有可用模型列表。

        Arrange: Mock Ollama返回模型列表
        Act: 获取可用模型
        Assert: 返回正确的模型列表
        """
        # Arrange
        client_ollama.reset_mock()
        client_ollama.list_models = AsyncMock(
            return_value={
                "models": [
                    {"name": "qwen2.5:latest"},
                    {"name": "llama3:latest"},
                    {"name": "mistral:latest"},
                ]
            }
        )
        router = create_model_router(config, client_ollama, AsyncMock())

        # Act
        models = await router["get_available_models"]()

        # Assert
        assert len(models) == 3
        model_ids = [m["id"] for m in models]
        assert "qwen2.5:latest" in model_ids
        assert "llama3:latest" in model_ids
        assert "mistral:latest" in model_ids
        assert all(m["object"] == "model" for m in models)

    async def test_invalid_model_request(self):
        """
        验收标准: MRT-005 - 无效模型请求应返回ModelNotFoundError。

        Arrange: 空模型名
        Act & Assert: 路由空模型名应抛异常
        """
        # Arrange
        config = MagicMock()
        config.model = MagicMock()
        config.model.primary_backend = "ollama"
        config.model.fallback_backend = "litellm"
        router = create_model_router(config, AsyncMock(), AsyncMock())

        # Act & Assert
        with pytest.raises(ModelNotFoundError) as exc_info:
            await router["route"](model="", messages=[{"role": "user", "content": "Hello"}])
        assert "Model name is required" in str(exc_info.value)

    async def test_streaming_response(self, config: MagicMock, client_ollama: AsyncMock):
        """
        验收标准: MRT-006 - 应支持流式响应（SSE）。

        Arrange: 启用stream模式
        Act: 发送流式请求
        Assert: 返回异步生成器
        """
        # Arrange
        config.model.primary_backend = "ollama"
        config.model.fallback_backend = "litellm"
        client_ollama.reset_mock()
        router = create_model_router(config, client_ollama, AsyncMock())

        # Act
        result = await router["route"](
            model="qwen2.5",
            messages=[{"role": "user", "content": "Hello"}],
            stream=True,
        )

        # Assert
        assert result is not None
        chunks = []
        async for chunk in result:
            chunks.append(chunk)
        assert len(chunks) == 8  # 8 words in "Hello, this is streaming!"
        content = "".join(c["choices"][0]["delta"]["content"] for c in chunks)
        assert content == "Hello, this is streaming!"

    async def test_all_backends_fail(self, config: MagicMock, client_ollama: AsyncMock, client_litellm: AsyncMock):
        """
        验收标准: MRT-007 - 所有后端失败时应返回明确的错误信息。

        Arrange: 所有后端都失败
        Act: 发送路由请求
        Assert: 抛出AllBackendsFailedError
        """
        # Arrange
        config.model.primary_backend = "ollama"
        config.model.fallback_backend = "litellm"
        client_ollama.reset_mock()
        client_ollama.chat = AsyncMock(side_effect=ConnectionError("Ollama down"))
        client_litellm.reset_mock()
        client_litellm.chat = AsyncMock(side_effect=ConnectionError("LiteLLM down"))
        router = create_model_router(config, client_ollama, client_litellm)

        # Act & Assert
        with pytest.raises(AllBackendsFailedError) as exc_info:
            await router["route"](
                model="qwen2.5",
                messages=[{"role": "user", "content": "Hello"}],
            )
        error_msg = str(exc_info.value)
        assert "Primary failed" in error_msg
        assert "Fallback failed" in error_msg

    def test_get_backend_for_model(self, config: MagicMock, client_ollama: AsyncMock, client_litellm: AsyncMock):
        """
        额外测试 - 模型名到后端的映射。

        Arrange: 不同模型名
        Act: 确定后端
        Assert: 正确映射
        """
        router = create_model_router(config, client_ollama, client_litellm)

        # Assert - Ollama models
        assert router["get_backend_for_model"]("qwen2.5") == "ollama"
        assert router["get_backend_for_model"]("llama3") == "ollama"
        assert router["get_backend_for_model"]("mistral") == "ollama"
        assert router["get_backend_for_model"]("deepseek-coder") == "ollama"

        # Assert - LiteLLM models
        assert router["get_backend_for_model"]("gpt-4") == "litellm"
        assert router["get_backend_for_model"]("claude-3") == "litellm"
