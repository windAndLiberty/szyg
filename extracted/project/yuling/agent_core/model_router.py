"""
「域灵」数字员工系统 - 模型路由器模块

多模型后端调度与故障转移，支持 Ollama 和 LiteLLM 后端。
"""

from typing import Any, AsyncGenerator

from yuling.integrations.litellm_client import LiteLLMClient
from yuling.integrations.ollama_client import OllamaClient
from yuling.integrations.modelscope_client import ModelScopeClient
from yuling.integrations.openrouter_client import OpenRouterClient
from yuling.models.common import AllBackendsFailedError
from yuling.models.model import ModelResponse, StreamingChunk


class ModelRouter:
    """模型路由器 - 多模型后端调度与故障转移。

    根据配置自动管理多个模型后端，支持按优先级路由请求，
    在主后端失败时自动切换到备用后端。
    """

    def __init__(self, config: Any = None) -> None:
        """初始化模型路由器。

        Args:
            config: 模型配置对象，可以为 None（使用默认配置）
        """
        self.config = config
        self._backends: dict[str, Any] = {}
        self._setup_backends()

    def _setup_backends(self) -> None:
        """根据配置初始化后端。"""
        if self.config is None:
            # 自动检测可用后端：OpenRouter > ModelScope > Ollama > LiteLLM
            try:
                import os
                or_key = os.environ.get("OPENROUTER_API_KEY")
                ms_key = os.environ.get("MODELSCOPE_API_KEY")
            except Exception:
                or_key = ms_key = None
            if or_key:
                self._backends["openrouter"] = OpenRouterClient(api_key=or_key)
            if ms_key:
                self._backends["modelscope"] = ModelScopeClient(api_key=ms_key)
            self._backends["ollama"] = OllamaClient()
            self._backends["litellm"] = LiteLLMClient()
        else:
            models_config = self.config
            if hasattr(models_config, "backends"):
                for backend in models_config.backends:
                    backend_type = getattr(backend, "backend_type", "")
                    if backend_type == "openrouter":
                        self._backends[backend.name] = OpenRouterClient(
                            api_key=backend.api_key,
                            base_url=backend.base_url,
                            default_model=backend.default_model,
                        )
                    elif backend_type == "modelscope":
                        self._backends[backend.name] = ModelScopeClient(
                            api_key=backend.api_key,
                            base_url=backend.base_url,
                            default_model=backend.default_model,
                        )
                    elif backend_type == "ollama":
                        self._backends[backend.name] = OllamaClient(
                            base_url=backend.base_url,
                            default_model=backend.default_model,
                        )
                    elif backend_type == "litellm":
                        self._backends[backend.name] = LiteLLMClient(
                            base_url=backend.base_url,
                            api_key=backend.api_key,
                            default_model=backend.default_model,
                        )

    async def route(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = False,
        backend: str | None = None,
    ) -> ModelResponse | AsyncGenerator[StreamingChunk, None]:
        """路由请求到合适的后端。

        如果指定了 backend，优先使用该后端；否则按配置顺序尝试所有后端。
        当主后端失败时，自动切换到下一个可用后端。

        Args:
            messages: 消息列表
            model: 模型名称
            stream: 是否使用流式响应
            backend: 指定后端名称

        Returns:
            ModelResponse 或流式生成器

        Raises:
            AllBackendsFailedError: 所有后端都失败时抛出
        """
        # 确定后端
        if backend and backend in self._backends:
            backends_to_try = [backend]
        else:
            backends_to_try = list(self._backends.keys())

        last_error: Exception | None = None
        for be_name in backends_to_try:
            try:
                be = self._backends[be_name]
                if stream:
                    return be.chat_stream(messages, model=model or be.default_model)
                else:
                    result = await be.chat(messages, model=model or be.default_model)
                    return ModelResponse(
                        content=result.get("message", {}).get("content", ""),
                        model=model or "",
                    )
            except Exception as e:
                last_error = e
                continue

        raise AllBackendsFailedError(f"All backends failed. Last error: {last_error}")

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = False,
    ) -> ModelResponse:
        """兼容接口 - 非流式聊天。

        如果 stream=True，聚合流式结果为单个响应。

        Args:
            messages: 消息列表
            model: 模型名称
            stream: 是否使用流式响应

        Returns:
            模型响应对象
        """
        result = await self.route(messages, model=model, stream=stream)
        if stream:
            # 聚合流式结果（chunk 是 Ollama dict 格式）
            content_parts = []
            async for chunk in result:
                msg = chunk.get("message", {}) if isinstance(chunk, dict) else {}
                content_parts.append(msg.get("content", ""))
            return ModelResponse(
                content="".join(content_parts), model=model or ""
            )
        return result

    async def route_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        backend: str | None = None,
    ):
        """流式路由请求，返回原始 async generator。

        不聚合流式结果，直接返回后端的流式生成器，
        供 SSE 端点直接使用。
        """
        if backend and backend in self._backends:
            backends_to_try = [backend]
        else:
            backends_to_try = list(self._backends.keys())

        last_error = None
        for be_name in backends_to_try:
            try:
                be = self._backends[be_name]
                return be.chat_stream(messages, model=model or be.default_model)
            except Exception as e:
                last_error = e
                continue

        raise AllBackendsFailedError(f"All backends failed. Last error: {last_error}")

    async def get_available_models(self) -> list[str]:
        """获取所有可用模型列表。

        Returns:
            模型名称列表
        """
        models: list[str] = []
        for name, backend in self._backends.items():
            try:
                if hasattr(backend, "list_models"):
                    result = await backend.list_models()
                    if isinstance(result, dict) and "models" in result:
                        models.extend([m.get("name", "") for m in result["models"]])
                    else:
                        models.append(backend.default_model)
                else:
                    models.append(backend.default_model)
            except Exception:
                models.append(backend.default_model)
        return models

    async def get_backend_for_model(self, model: str) -> str | None:
        """获取支持指定模型的后端名称。

        Args:
            model: 模型名称

        Returns:
            后端名称，未找到则返回 None
        """
        for name, backend in self._backends.items():
            if model == backend.default_model or model in getattr(
                backend, "available_models", []
            ):
                return name
        return None

    def get_backends(self) -> dict[str, Any]:
        """获取所有后端。

        Returns:
            后端名称到实例的映射
        """
        return dict(self._backends)

    def add_backend(self, name: str, backend: Any) -> None:
        """添加后端。

        Args:
            name: 后端名称
            backend: 后端客户端实例
        """
        self._backends[name] = backend

    def remove_backend(self, name: str) -> bool:
        """移除后端。

        Args:
            name: 后端名称

        Returns:
            是否成功移除
        """
        if name not in self._backends:
            return False
        del self._backends[name]
        return True
