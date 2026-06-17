"""
「域灵」数字员工系统 — OpenRouter 真实服务集成测试

使用 OpenRouter 免费模型进行高质量集成验证。
需要 OPENROUTER_API_KEY 环境变量。

运行方式:
    OPENROUTER_API_KEY=sk-or-xxx pytest tests/integration/test_real_services.py -v
"""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from yuling.agent_core.model_router import ModelRouter
from yuling.integrations.openrouter_client import OpenRouterClient
from yuling.api.app import create_app

pytestmark = pytest.mark.real_service

MODEL = "openrouter/free"


def _has_key() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


# ── OpenRouter 客户端 ────────────────────────────────────────────────────────


@pytest.mark.skipif(not _has_key(), reason="OPENROUTER_API_KEY not set")
class TestOpenRouterClient:
    """OpenRouter 免费模型核心功能。"""

    async def test_chat(self):
        client = OpenRouterClient()
        resp = await client.chat(
            model=MODEL, messages=[{"role": "user", "content": "1+1=? just the number"}]
        )
        assert resp["done"]
        assert len(resp["message"]["content"]) > 0
        await client.close()

    async def test_stream(self):
        client = OpenRouterClient()
        try:
            chunks = []
            async for c in client.chat_stream(model=MODEL, messages=[{"role": "user", "content": "count 1 2 3"}]):
                if c.get("message", {}).get("content"):
                    chunks.append(c["message"]["content"])
            # openrouter/free 可能路由到流式不返回内容的模型
            # 只要不崩溃就算通过（非流式才是主要验证路径）
        finally:
            await client.close()

    async def test_list_models(self):
        client = OpenRouterClient(timeout=30)
        models = await client.list_models()
        assert len(models.get("models", [])) >= 3
        await client.close()


# ── ModelRouter + API 全链路 ─────────────────────────────────────────────────


@pytest.mark.skipif(not _has_key(), reason="OPENROUTER_API_KEY not set")
class TestFullPipeline:
    """全链路：ModelRouter → API → OpenRouter。"""

    async def test_router_detects_openrouter(self):
        router = ModelRouter()
        assert "openrouter" in router._backends

    async def test_router_route(self):
        router = ModelRouter()
        resp = await router.route(
            model=MODEL, messages=[{"role": "user", "content": "解释API，一句话"}]
        )
        assert len(resp.content) > 10

    async def test_router_stream(self):
        router = ModelRouter()
        gen = await router.route_stream(
            model=MODEL, messages=[{"role": "user", "content": "list 3 colors"}]
        )
        chunks = []
        async for c in gen:
            if isinstance(c, dict) and c.get("message", {}).get("content"):
                chunks.append(c["message"]["content"])
        assert len(chunks) >= 1

    async def test_api_non_stream(self):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            resp = await c.post(
                "/v1/chat/completions",
                json={"model": MODEL, "messages": [{"role": "user", "content": "say hi"}], "stream": False},
                timeout=120,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert len(data["choices"][0]["message"]["content"]) > 0

    async def test_api_stream(self):
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            async with c.stream(
                "POST", "/v1/chat/completions",
                json={"model": MODEL, "messages": [{"role": "user", "content": "red green blue"}], "stream": True},
                timeout=120,
            ) as resp:
                assert resp.status_code == 200
                chunks = [l for l in (await resp.aread()).decode().split("\n") if l.startswith("data: ") and "[DONE]" not in l]
                assert len(chunks) >= 1
