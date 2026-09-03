"""Hermes chat acceptance tests through the SZYG cloud control plane.

Live model and platform tests are opt-in so normal test runs never consume
credits or start public-platform collection unexpectedly.
"""

from __future__ import annotations

import json
import os

import pytest


def require_live_cloud() -> None:
    if os.environ.get("SZYG_RUN_CLOUD_ACCEPTANCE") != "1":
        pytest.skip("set SZYG_RUN_CLOUD_ACCEPTANCE=1 to run cloud acceptance")


def require_live_platforms() -> None:
    if os.environ.get("SZYG_RUN_PLATFORM_ACCEPTANCE") != "1":
        pytest.skip("set SZYG_RUN_PLATFORM_ACCEPTANCE=1 to run platform acceptance")


async def _stream_collect(client, payload):
    events = []
    async with client.stream("POST", "/api/hermes/chat", json=payload, timeout=180) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if not line.startswith("data: "):
                continue
            raw = line[6:]
            if raw.strip() == "[DONE]":
                break
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
    return events


class TestHermesChatValidation:
    async def test_empty_messages(self, client):
        response = await client.post("/api/hermes/chat", json={"model": "text.fast", "messages": []})
        assert response.status_code == 422

    async def test_missing_messages(self, client):
        response = await client.post("/api/hermes/chat", json={"model": "text.fast"})
        assert response.status_code == 422


class TestHermesCloudAgentLoop:
    async def test_simple_chat(self, client):
        require_live_cloud()
        events = await _stream_collect(client, {
            "model": "text.fast",
            "messages": [{"role": "user", "content": "你好，用中文回复一句话"}],
        })
        types = {event.get("type") for event in events}
        assert "run.started" in types
        assert "run.completed" in types

    async def test_knowledge_tool(self, client):
        require_live_cloud()
        events = await _stream_collect(client, {
            "model": "text.fast",
            "messages": [{"role": "user", "content": "请检索知识库中关于营销的内容并注明来源"}],
        })
        types = {event.get("type") for event in events}
        assert "tool.started" in types
        assert "tool.completed" in types
        assert "run.completed" in types


class TestHermesCaseCards:
    async def test_case_cards_returns_data(self, client):
        require_live_platforms()
        response = await client.post("/api/hermes/case-cards", json={
            "recent_titles": ["测试对话"],
            "limit": 3,
        })
        assert response.status_code == 200
        assert "cards" in response.json()
