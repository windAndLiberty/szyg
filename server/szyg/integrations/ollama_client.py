"""Ollama本地LLM客户端."""

import json
from typing import AsyncGenerator

import httpx

from szyg.integrations.base_llm_client import BaseLLMClient
from szyg.models.common import IntegrationError


class OllamaClient(BaseLLMClient):
    """Ollama本地LLM客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "qwen3:0.6B",
        timeout: float = 120.0,
    ):
        super().__init__(base_url=base_url, default_model=default_model, timeout=timeout)
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = False,
    ) -> dict:
        """Ollama聊天API — 返回统一格式。"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": model or self.default_model,
                    "messages": messages,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return self._parse_ndjson(response.text)
        except httpx.HTTPStatusError as e:
            raise IntegrationError(
                f"Ollama HTTP error: {e.response.status_code}"
            )
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Ollama chat failed: {e}")

    async def generate(
        self, prompt: str, model: str | None = None, stream: bool = False
    ) -> dict:
        """Ollama生成API"""
        try:
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model or self.default_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return self._parse_ndjson(response.text)
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"Ollama generate failed: {e}")

    @staticmethod
    def _parse_ndjson(text: str) -> dict:
        """解析 Ollama NDJSON 响应，取最后一个完整 JSON 对象。"""
        lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
        if not lines:
            raise IntegrationError("Empty response from Ollama")
        return json.loads(lines[-1])

    async def list_models(self) -> dict:
        """列出可用模型"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise IntegrationError(f"Failed to list models: {e}")

    async def chat_stream(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncGenerator[dict, None]:
        """流式聊天"""
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": model or self.default_model,
                    "messages": messages,
                    "stream": True,
                },
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            yield data
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            raise IntegrationError(f"Ollama stream failed: {e}")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
