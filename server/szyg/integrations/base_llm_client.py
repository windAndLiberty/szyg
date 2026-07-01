"""LLM 客户端基类 — 统一 httpx/OpenAI 客户端管理、聊天响应规范化、重试机制。

所有 LLM 集成客户端(Ollama / LiteLLM / OpenRouter / VolcEngine)继承此类，
避免重复实现:
  - 惰性客户端创建 & close()
  - chat() → 统一 {"message": ..., "model": ..., "done": True} 格式
  - chat_stream() → 统一逐 token yield
  - 指数退避重试 (限流 / 429 自动恢复)
"""

import asyncio
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from szyg.models.common import IntegrationError


class BaseLLMClient(ABC):
    """LLM 客户端基类。"""

    def __init__(
        self,
        base_url: str,
        default_model: str,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self.timeout = timeout

    # ── Lifecycle (子类可覆盖) ─────────────────────────────────────

    @abstractmethod
    async def close(self) -> None:
        """关闭底层 HTTP 客户端。"""

    # ── 统一接口 ──────────────────────────────────────────────────

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = False,
    ) -> dict:
        """非流式聊天。

        Returns:
            {"message": {"role": "assistant", "content": "..."}, "model": "...", "done": True}
        """

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
    ) -> AsyncGenerator[dict, None]:
        """流式聊天，逐 token yield。

        Yields:
            {"message": {"role": "assistant", "content": "<token>"}, "model": "...", "done": False}
            最后一条: done=True, content=""
        """

    @abstractmethod
    async def list_models(self) -> dict:
        """列出可用模型。"""

    # ── 响应规范化工具 ────────────────────────────────────────────

    @staticmethod
    def normalize_chat_response(
        role: str,
        content: str,
        model: str,
        usage: dict | None = None,
        tool_calls: list | None = None,
    ) -> dict:
        """将任意后端响应转换为统一格式。"""
        result: dict = {
            "message": {"role": role or "assistant", "content": content or ""},
            "model": model,
            "done": True,
        }
        if usage:
            result["usage"] = usage
        if tool_calls:
            result["message"]["tool_calls"] = tool_calls
        return result

    @staticmethod
    def normalize_stream_chunk(content: str, model: str, done: bool = False) -> dict:
        return {
            "message": {"role": "assistant", "content": content},
            "model": model,
            "done": done,
        }


async def retry_with_backoff(
    fn,
    *args,
    max_retries: int = 3,
    on_rate_limit: str = "VolcEngine",
    **kwargs,
):
    """指数退避重试 — 自动识别限流错误 (429 / rate / limit)。

    可直接用于 OpenRouter._call_with_retry 和 VolcEngine._retry 的替代。
    """
    last_error: Exception | str | None = None
    for attempt in range(max_retries):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate" in err_str or "limit" in err_str:
                wait = 2 ** attempt + 1
                await asyncio.sleep(wait)
                last_error = e
            else:
                raise
    raise IntegrationError(
        f"{on_rate_limit} rate-limited after {max_retries} retries: {last_error}"
    )
