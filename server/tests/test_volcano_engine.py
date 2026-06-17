"""Volcano Engine ARK API — 单元测试。

测试火山引擎客户端的基础功能：chat、模型列表、错误处理。
使用真实 API key（开发环境）验证功能正确性，同时记录 token 消耗。
"""

import os
import pytest

from szyg.integrations.volcano_engine_client import VolcanoEngineClient


# ── Fixtures ─────────────────────────────────────────────

@pytest.fixture
def client():
    """创建 VolcanoEngineClient，从环境变量读取 API key。"""
    key = os.environ.get("VOLCANO_ENGINE_API_KEY", "")
    if not key:
        pytest.skip("VOLCANO_ENGINE_API_KEY not set")
    return VolcanoEngineClient(api_key=key)


@pytest.fixture
def usage_tracker():
    """跨测试收集 token 消耗数据。"""
    return {"records": []}


# ── Model Listing ────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_models(client):
    """列出可用模型 — 验证 API 连通性。"""
    models = await client.list_models()
    model_list = models.get("models", [])
    assert len(model_list) > 0, "Should return at least 1 model"
    model_ids = [m["name"] for m in model_list]
    assert any("deepseek" in mid.lower() for mid in model_ids), f"Should include DeepSeek, got: {model_ids[:5]}"
    print(f"  Models available: {len(model_list)}")


# ── Basic Chat ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_basic(client, usage_tracker):
    """基本对话 — 验证 LLM 调用正常。"""
    resp = await client.chat(
        messages=[{"role": "user", "content": "回复 OK 即可"}],
        model="deepseek-v4-flash-260425",
    )
    assert resp["done"] is True
    assert resp["message"]["role"] == "assistant"
    assert len(resp["message"]["content"]) > 0
    tokens = resp.get("usage", {}).get("total_tokens", 0)
    usage_tracker["records"].append({"test": "test_chat_basic", "model": "deepseek-v4-flash", "tokens": tokens})
    print(f"  Tokens used: {tokens}")


@pytest.mark.asyncio
async def test_chat_pro_model(client, usage_tracker):
    """DeepSeek V4 Pro — 测试主力推理模型。"""
    resp = await client.chat(
        messages=[{"role": "user", "content": "1+1等于几？只回答数字"}],
        model="deepseek-v4-pro-260425",
    )
    assert resp["done"] is True
    assert "2" in resp["message"]["content"]
    tokens = resp.get("usage", {}).get("total_tokens", 0)
    usage_tracker["records"].append({"test": "test_chat_pro_model", "model": "deepseek-v4-pro", "tokens": tokens})
    print(f"  Tokens used: {tokens}")


@pytest.mark.asyncio
async def test_chat_chinese(client, usage_tracker):
    """中文对话 — 测试中文能力。"""
    resp = await client.chat(
        messages=[{"role": "user", "content": "请用一句中文介绍你自己"}],
        model="deepseek-v4-flash-260425",
    )
    assert resp["done"] is True
    content = resp["message"]["content"]
    assert any("一" <= c <= "鿿" for c in content), "Response should contain Chinese"
    tokens = resp.get("usage", {}).get("total_tokens", 0)
    usage_tracker["records"].append({"test": "test_chat_chinese", "model": "deepseek-v4-flash", "tokens": tokens})
    print(f"  Tokens used: {tokens}")


# ── Error Handling ───────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_model(client):
    """无效模型名 — 应抛出 IntegrationError。"""
    from szyg.models.common import IntegrationError
    with pytest.raises(IntegrationError):
        await client.chat(
            messages=[{"role": "user", "content": "test"}],
            model="nonexistent-model-xyz",
        )


@pytest.mark.asyncio
async def test_empty_messages(client):
    """空消息 — 应抛出错误。"""
    with pytest.raises(Exception):
        await client.chat(
            messages=[],
            model="deepseek-v4-flash-260425",
        )


# ── Vision Model ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_vision_model_available(client):
    """验证视觉模型可用。"""
    models = await client.list_models()
    model_list = models.get("models", [])
    vision_models = [m["name"] for m in model_list if "vision" in m["name"].lower()]
    print(f"  Vision models: {vision_models}")
    assert len(vision_models) > 0, f"Should have vision models, got: {vision_models}"
