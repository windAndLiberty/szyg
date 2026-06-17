"""
ModelScope API 客户端 — OpenAI 兼容接口。

使用 ModelScope 提供的 OpenAI 兼容 API，支持 chat / chat_stream / list_models。
ModelScope 提供多种高质量模型（DeepSeek-V4, DeepSeek-R1, Qwen3 等）。

用法:
    client = ModelScopeClient(api_key="ms-xxx")
    resp = await client.chat(messages=[{"role": "user", "content": "Hello"}])
"""

import asyncio
import os
from typing import AsyncGenerator

from openai import AsyncOpenAI, RateLimitError

from yuling.models.common import IntegrationError


class ModelScopeClient:
    """ModelScope API 客户端（OpenAI 兼容格式）。

    使用 AsyncOpenAI SDK 调用 ModelScope 推理 API。
    支持非流式 chat、流式 chat_stream、列出模型。
    内置指数退避重试处理限流。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api-inference.modelscope.cn/v1",
        default_model: str = "deepseek-ai/DeepSeek-V4-Flash",
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("MODELSCOPE_API_KEY", "")
        self.base_url = base_url
        self.default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                timeout=self.timeout,
                max_retries=0,  # 我们自己处理重试
            )
        return self._client

    async def _retry_on_rate_limit(self, fn, *args, **kwargs):
        """指数退避重试，处理 429 限流。"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return await fn(*args, **kwargs)
            except RateLimitError:
                wait = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(wait)
                last_error = RateLimitError("rate limited")
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "insufficient_quota" in err_str:
                    wait = 2 ** attempt
                    await asyncio.sleep(wait)
                    last_error = e
                else:
                    raise
        raise IntegrationError(f"ModelScope request failed after {self.max_retries} retries: {last_error}")

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = False,
    ) -> dict:
        """非流式聊天补全。

        Returns:
            dict: {"message": {"role": "assistant", "content": "..."}, "model": "...", "done": True}
        """
        try:
            response = await self._retry_on_rate_limit(
                self.client.chat.completions.create,
                model=model or self.default_model,
                messages=messages,
                stream=False,
                max_tokens=4096,
            )
            if response is None or response.choices is None:
                raise IntegrationError("ModelScope returned empty response")
            choice = response.choices[0]
            return {
                "message": {
                    "role": choice.message.role if choice.message else "assistant",
                    "content": choice.message.content if choice.message else "",
                },
                "model": response.model or (model or self.default_model),
                "done": True,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
            }
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(f"ModelScope chat failed: {e}")

    async def generate(
        self, prompt: str, model: str | None = None
    ) -> dict:
        """生成文本（兼容 Ollama generate 接口）。"""
        resp = await self.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
        )
        return {
            "response": resp["message"]["content"],
            "model": resp.get("model", ""),
            "done": True,
        }

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """流式聊天补全。

        Yields:
            dict: {"message": {"role": "assistant", "content": "token"}, "done": False}
        """
        try:
            stream = await self.client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                stream=True,
                max_tokens=4096,
            )
            async for chunk in stream:
                if chunk.choices:
                    delta = chunk.choices[0].delta
                    content = delta.content or ""
                    yield {
                        "message": {
                            "role": delta.role or "assistant",
                            "content": content,
                        },
                        "model": chunk.model,
                        "done": False,
                    }
            # 最终 done chunk
            yield {
                "message": {"role": "assistant", "content": ""},
                "model": model or self.default_model,
                "done": True,
            }
        except Exception as e:
            raise IntegrationError(f"ModelScope stream failed: {e}")

    async def list_models(self) -> dict:
        """列出 ModelScope 可用模型。

        Returns:
            dict: {"models": [{"name": "deepseek-ai/DeepSeek-V4-Flash"}, ...]}
        """
        try:
            models = await self.client.models.list()
            return {
                "models": [
                    {"name": m.id}
                    for m in models.data
                ]
            }
        except Exception as e:
            raise IntegrationError(f"ModelScope list_models failed: {e}")

    async def close(self) -> None:
        """关闭客户端（安全：可多次调用）。"""
        if self._client is not None:
            try:
                await self._client.close()
            except RuntimeError:
                pass  # event loop already closed
            self._client = None
