"""
OpenRouter API 客户端 — openrouter/free 自动路由。

使用 openrouter/free 模型 ID，OpenRouter 自动分配到当前可用的免费模型。
内置限流重试，自动处理空响应。

用法:
    client = OpenRouterClient()
    resp = await client.chat(messages=[{"role": "user", "content": "Hello"}])
"""

import os
from typing import AsyncGenerator

from openai import AsyncOpenAI

from szyg.integrations.base_llm_client import BaseLLMClient, retry_with_backoff
from szyg.models.common import IntegrationError


class OpenRouterClient(BaseLLMClient):
    """OpenRouter API 客户端。

    自动从 OPENROUTER_API_KEY 读取密钥。
    使用 openrouter/free 自动路由到可用免费模型。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://openrouter.ai/api/v1",
        default_model: str = "openrouter/free",
        timeout: float = 60.0,
    ):
        super().__init__(base_url=base_url, default_model=default_model, timeout=timeout)
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._client = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0,
            )
        return self._client

    async def chat(
        self, messages: list[dict], model: str | None = None, **kwargs
    ) -> dict:
        """非流式聊天。"""
        target = model or self.default_model
        try:
            resp = await retry_with_backoff(
                self.client.chat.completions.create,
                model=target,
                messages=messages,
                stream=False,
                max_tokens=4096,
                on_rate_limit="OpenRouter",
            )
            choice = resp.choices[0] if resp and resp.choices else None
            return self.normalize_chat_response(
                role=choice.message.role if choice and choice.message else "assistant",
                content=(
                    choice.message.content
                    if choice and choice.message and choice.message.content
                    else ""
                ),
                model=resp.model if resp else target,
            )
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"OpenRouter chat failed: {e}")

    async def chat_stream(
        self, messages: list[dict], model: str | None = None
    ) -> AsyncGenerator[dict, None]:
        """流式聊天。"""
        target = model or self.default_model
        try:
            stream = await self.client.chat.completions.create(
                model=target,
                messages=messages,
                stream=True,
                max_tokens=4096,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        yield self.normalize_stream_chunk(content, chunk.model, done=False)
            yield self.normalize_stream_chunk("", target, done=True)
        except Exception as e:
            raise IntegrationError(f"OpenRouter stream failed: {e}")

    async def list_models(self) -> dict:
        """列出可用模型。"""
        try:
            models = await self.client.models.list()
            return {"models": [{"name": m.id} for m in models.data]}
        except Exception as e:
            raise IntegrationError(f"OpenRouter list_models failed: {e}")

    async def close(self) -> None:
        if self._client is not None:
            try:
                await self._client.close()
            except RuntimeError:
                pass
            self._client = None
