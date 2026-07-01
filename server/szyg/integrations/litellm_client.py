"""
「域灵」数字员工系统 - LiteLLM 客户端

封装 LiteLLM API 调用，提供 OpenAI 兼容的 completion 接口。
"""

from typing import Any, AsyncGenerator, Optional

import httpx

from szyg.integrations.base_llm_client import BaseLLMClient


class LiteLLMClient(BaseLLMClient):
    """LiteLLM API 客户端（OpenAI 兼容格式）。"""

    def __init__(
        self,
        base_url: str = "http://localhost:4000",
        api_key: Optional[str] = None,
        default_model: str = "gpt-4",
        timeout: float = 60.0,
    ):
        super().__init__(base_url=base_url, default_model=default_model, timeout=timeout)
        self.api_key = api_key
        self.available_models: list[str] = []
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """获取或创建 HTTP 客户端。"""
        if self._client is None:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            self._client = httpx.AsyncClient(timeout=self.timeout, headers=headers)
        return self._client

    async def completion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict:
        """发送聊天补全请求。"""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": stream,
            **kwargs,
        }
        response = await self.client.post(
            f"{self.base_url}/v1/chat/completions", json=payload
        )
        response.raise_for_status()
        return response.json()

    async def acompletion(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict:
        """异步聊天补全（别名，与 completion 一致）。"""
        return await self.completion(messages, model=model, stream=stream, **kwargs)

    async def list_models(self) -> dict:
        """获取可用模型列表。"""
        response = await self.client.get(f"{self.base_url}/v1/models")
        response.raise_for_status()
        data = response.json()
        self.available_models = [m.get("id", "") for m in data.get("data", [])]
        return data

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = False,
    ) -> dict:
        """聊天接口（兼容统一接口）。"""
        result = await self.completion(
            messages=messages,
            model=model or self.default_model,
            stream=False,
        )
        choice = result.get("choices", [{}])[0]
        return self.normalize_chat_response(
            role=choice.get("message", {}).get("role", "assistant"),
            content=choice.get("message", {}).get("content", ""),
            model=result.get("model", model or self.default_model),
            usage=result.get("usage"),
        )

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """流式聊天（兼容统一接口）。"""
        target = model or self.default_model
        result = await self.completion(
            messages=messages, model=target, stream=False,
        )
        content = (
            result.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        for char in content:
            yield self.normalize_stream_chunk(char, target, done=False)
        yield self.normalize_stream_chunk("", target, done=True)

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "LiteLLMClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
