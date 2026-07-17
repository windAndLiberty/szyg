"""OpenAI-compatible client for the bundled local llama.cpp service."""

from __future__ import annotations

from typing import Any, AsyncGenerator

import httpx

from szyg.integrations.base_llm_client import BaseLLMClient
from szyg.integrations.local_llama_runtime import DEFAULT_BASE_URL


class LocalSmallModelClient(BaseLLMClient):
    """Small local model client for low-risk, short-context tasks."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        default_model: str = "qwen3-4b",
        timeout: float = 30.0,
    ) -> None:
        super().__init__(base_url=base_url, default_model=default_model, timeout=timeout)
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout, proxy=None, trust_env=False)
        return self._client

    async def health(self) -> dict:
        try:
            response = await self.client.get(f"{self.base_url}/models")
            return {"available": response.status_code == 200, "status_code": response.status_code}
        except Exception as exc:
            return {"available": False, "error": str(exc)}

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict:
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "stream": False,
            "temperature": kwargs.get("temperature", 0.3),
            "max_tokens": kwargs.get("max_tokens", 512),
        }
        response = await self.client.post(f"{self.base_url}/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        return self.normalize_chat_response(
            role=message.get("role", "assistant"),
            content=message.get("content", ""),
            model=data.get("model", model or self.default_model),
            usage=data.get("usage"),
        )

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        result = await self.chat(messages, model=model)
        content = result.get("message", {}).get("content", "")
        target = result.get("model", model or self.default_model)
        for char in content:
            yield self.normalize_stream_chunk(char, target, done=False)
        yield self.normalize_stream_chunk("", target, done=True)

    async def list_models(self) -> dict:
        response = await self.client.get(f"{self.base_url}/models")
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
