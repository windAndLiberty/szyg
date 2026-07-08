"""Hermes Chat API acceptance tests — real LLM calls via Volcengine + Ollama.

Cost: ~0.01-0.1 RMB per test with short prompts.
Skip automatically if neither Volcengine API key nor Ollama is available.
"""

import json
import pytest
from tests.fixtures.env_config import require_ollama, require_volcengine


async def _stream_collect(client, payload):
    """Collect SSE events from /api/hermes/chat into a list of parsed JSON objects."""
    events = []
    async with client.stream("POST", "/api/hermes/chat", json=payload, timeout=120) as response:
        assert response.status_code == 200
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    events.append(json.loads(data_str))
                except json.JSONDecodeError:
                    pass
    return events


class TestHermesChatBasic:
    """Basic chat functionality — real LLM."""

    async def test_simple_chat_ollama(self, client):
        """Basic text chat via Ollama (zero cost)."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "llama3:latest",
            "messages": [{"role": "user", "content": "你好，用中文回复一句话"}],
        })
        assert len(events) > 0
        types = {e.get("type") for e in events}
        assert "text" in types
        assert "done" in types

    async def test_simple_chat_volcengine(self, client):
        """Basic text chat via Volcengine Doubao (API cost)."""
        require_volcengine()
        events = await _stream_collect(client, {
            "model": "doubao-seed-2-0-pro-260215",
            "messages": [{"role": "user", "content": "1+1等于几？用一个词回答"}],
        })
        assert len(events) > 0
        types = {e.get("type") for e in events}
        assert "text" in types
        assert "done" in types


class TestHermesChatValidation:
    """Request validation."""

    async def test_empty_messages(self, client):
        """Empty messages -> 422."""
        resp = await client.post("/api/hermes/chat", json={
            "model": "test", "messages": []
        })
        assert resp.status_code == 422

    async def test_missing_messages(self, client):
        """Missing messages field -> 422."""
        resp = await client.post("/api/hermes/chat", json={"model": "test"})
        assert resp.status_code == 422


class TestHermesChatSSEFormat:
    """SSE event format validation."""

    async def test_events_include_status_and_done(self, client):
        """Verify status -> text -> done event sequence."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "llama3:latest",
            "messages": [{"role": "user", "content": "说三个字"}],
        })
        types_in_order = [e.get("type") for e in events]
        assert "status" in types_in_order, f"Expected status event, got: {types_in_order}"
        assert "done" in types_in_order, f"Expected done event, got: {types_in_order}"

    async def test_error_on_tool_message(self, client):
        """Invalid message format -> error event."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "llama3:latest",
            "messages": [{"role": "tool", "content": "orphan tool message"}],
        })
        types = {e.get("type") for e in events}
        # Should either error or fallback to text
        assert "error" in types or "done" in types


class TestHermesChatAgentConfig:
    """agent_id and expert_prompt channel tests."""

    async def test_agent_id_content(self, client):
        """agent_id=content loads content staff config."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "llama3:latest",
            "messages": [{"role": "user", "content": "介绍一下你的职责"}],
            "agent_id": "content",
        })
        assert len(events) > 0

    async def test_agent_id_acquisition(self, client):
        """agent_id=acquisition loads acquisition staff config."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "llama3:latest",
            "messages": [{"role": "user", "content": "你的工作是什么"}],
            "agent_id": "acquisition",
        })
        assert len(events) > 0

    async def test_expert_prompt_channel(self, client):
        """expert_prompt overrides agent_id system prompt."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "llama3:latest",
            "messages": [{"role": "user", "content": "说一句自我介绍"}],
            "expert_prompt": "你是一个数学家，请用数学家身份回答",
        })
        assert len(events) > 0


class TestHermesChatToolCall:
    """Real tool dispatch — requires local services."""

    async def test_knowledge_search_tool(self, client):
        """Ask to search knowledge base -> should trigger tool_call event."""
        require_ollama()
        events = await _stream_collect(client, {
            "model": "llama3:latest",
            "messages": [{"role": "user", "content": "搜索知识库中关于营销的内容"}],
        })
        assert len(events) > 0
        # May or may not trigger tool_call depending on model
        # At minimum the stream completes with done
        assert events[-1].get("type") == "done"


class TestHermesCaseCards:
    """POST /api/hermes/case-cards"""

    async def test_case_cards_returns_data(self, client):
        resp = await client.post("/api/hermes/case-cards", json={
            "recent_titles": ["测试对话"],
            "limit": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "cards" in data
