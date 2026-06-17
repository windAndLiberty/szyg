"""
火山引擎方舟 ARK API 客户端 — OpenAI 兼容接口。

火山方舟是字节跳动旗下的模型服务平台，提供 OpenAI 兼容的 API 格式。
支持豆包系列大模型（Doubao-Lite、Doubao-Pro、Doubao-1.5 等）的推理服务。

用法:
    client = VolcanoEngineClient(api_key="your-api-key")
    resp = await client.chat(messages=[{"role": "user", "content": "Hello"}])
"""

import asyncio
import os
from typing import AsyncGenerator

from openai import AsyncOpenAI, RateLimitError

from szyg.models.common import IntegrationError


class VolcanoEngineClient:
    """火山引擎 ARK API 客户端（OpenAI 兼容格式）。

    使用 AsyncOpenAI SDK 调用火山方舟推理 API。
    支持非流式 chat、流式 chat_stream、列出模型。
    内置指数退避重试处理限流。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        default_model: str = "doubao-lite-4k",
        timeout: float = 120.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key or os.environ.get("VOLCANO_ENGINE_API_KEY", "")
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
                max_retries=0,
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
        raise IntegrationError(
            f"VolcanoEngine request failed after {self.max_retries} retries: {last_error}"
        )

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
                raise IntegrationError("VolcanoEngine returned empty response")
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
            raise IntegrationError(f"VolcanoEngine chat failed: {e}")

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
            raise IntegrationError(f"VolcanoEngine stream failed: {e}")

    async def list_models(self) -> dict:
        """列出火山引擎可用模型。

        Returns:
            dict: {"models": [{"name": "doubao-lite-4k"}, ...]}
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
            raise IntegrationError(f"VolcanoEngine list_models failed: {e}")

    async def close(self) -> None:
        """关闭客户端（安全：可多次调用）。"""
        if self._client is not None:
            try:
                await self._client.close()
            except RuntimeError:
                pass  # event loop already closed
            self._client = None
