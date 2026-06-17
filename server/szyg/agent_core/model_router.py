"""
szyg 模型路由器 — 仅使用火山引擎 ARK API。

清理了 Ollama/LiteLLM/OpenRouter/ModelScope 等残留后端，
统一使用火山引擎的 DeepSeek + 豆包系列模型。
"""

import os
from typing import Any

from szyg.integrations.volcano_engine_client import VolcanoEngineClient
from szyg.models.common import AllBackendsFailedError
from szyg.models.model import ModelResponse


class ModelRouter:
    """模型路由器 — 火山引擎专用。

    单一后端，无故障转移延迟。
    """

    def __init__(self, config: Any = None) -> None:
        self._client = VolcanoEngineClient(
            api_key=os.environ.get("VOLCANO_ENGINE_API_KEY", ""),
            default_model="deepseek-v4-flash-260425",
        )

    @property
    def default_model(self) -> str:
        return self._client.default_model

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = False,
    ) -> ModelResponse:
        """非流式聊天。"""
        model = model or self._client.default_model
        try:
            if stream:
                gen = self._client.chat_stream(messages, model=model)
                parts = []
                async for chunk in gen:
                    msg = chunk.get("message", {}) if isinstance(chunk, dict) else {}
                    parts.append(msg.get("content", ""))
                return ModelResponse(content="".join(parts), model=model)
            result = await self._client.chat(messages, model=model)
            return ModelResponse(
                content=result.get("message", {}).get("content", ""),
                model=model,
            )
        except Exception as e:
            raise AllBackendsFailedError(f"VolcanoEngine failed: {e}")

    async def route_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        backend: str | None = None,
    ):
        """流式路由 — 直接返回异步生成器。"""
        model = model or self._client.default_model
        try:
            return self._client.chat_stream(messages, model=model)
        except Exception as e:
            raise AllBackendsFailedError(f"VolcanoEngine stream failed: {e}")

    async def get_available_models(self) -> list[str]:
        """获取可用模型列表。"""
        try:
            result = await self._client.list_models()
            return [m["name"] for m in result.get("models", [])]
        except Exception:
            return [self._client.default_model]
