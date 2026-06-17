"""Ollama本地LLM客户端."""

import json
from typing import AsyncGenerator, Any

import httpx

from yuling.models.integration import ChatResponse, GenerateResponse
from yuling.models.common import IntegrationError


class OllamaClient:
    """Ollama本地LLM客户端"""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        default_model: str = "qwen3:0.6B",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def chat(
        self,
        messages: list[dict],
        model: str = None,
        stream: bool = False,
    ) -> dict:
        """Ollama聊天API

        Ollama 返回 NDJSON（每行一个 JSON 对象），取最后一行作为最终结果。
        """
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
            # Ollama 返回 NDJSON，解析最后一行
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
        self, prompt: str, model: str = None, stream: bool = False
    ) -> dict:
        """Ollama生成API

        Ollama 返回 NDJSON，取最后一行作为最终结果。
        """
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
        lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
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
        self, messages: list[dict], model: str = None
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
