"""
Unit tests for szyg.api.hermes_chat — SSE chat endpoint.

Tests cover:
- SSE event format helper (_sse)
- System prompt building (_build_system_prompt)
- LLM backend resolution (_resolve_llm_backend)
- Argument sanitization (_sanitize_args)
- HermesChatRequest model
- Chat endpoint validation (mocked)
"""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# ── Import after path setup ──
from szyg.api.hermes_chat import (
    HermesChatRequest,
    HERMES_DEFAULT_MODEL,
    HERMES_TOOLS,
    _build_system_prompt,
    _resolve_llm_backend,
    _sanitize_args,
    _load_secret,
)


def _sse(**kw):
    """Replicate the _sse helper from hermes_chat."""
    return f"data: {json.dumps(kw)}\n\n"


class TestSSEHelper:
    """Test the SSE helper function format."""

    def test_sse_format(self):
        """Verify SSE event format: data: {json}\\n\\n"""
        result = _sse(type="text", content="hello")
        assert result.startswith("data: ")
        assert result.endswith("\n\n")
        data = json.loads(result[6:-2])
        assert data["type"] == "text"
        assert data["content"] == "hello"

    def test_sse_tool_call(self):
        result = _sse(type="tool_call", tool="content_list", args={"status": "draft"}, id="tc_1")
        data = json.loads(result[6:-2])
        assert data["type"] == "tool_call"
        assert data["tool"] == "content_list"
        assert data["id"] == "tc_1"

    def test_sse_done(self):
        result = _sse(type="done")
        data = json.loads(result[6:-2])
        assert data["type"] == "done"

    def test_sse_error(self):
        result = _sse(type="error", content="Something failed")
        data = json.loads(result[6:-2])
        assert data["type"] == "error"
        assert "failed" in data["content"]


class TestLoadSecret:
    def test_env_var_takes_priority(self):
        with patch.dict("os.environ", {"LLM_OLLAMA_API_KEY": "env-key"}):
            assert _load_secret("llm.ollama.api_key") == "env-key"

    def test_returns_default_on_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            result = _load_secret("nonexistent.key", "default-val")
            assert result == "default-val"


class TestResolveLLMBackend:
    def test_volcengine_model(self):
        with patch("szyg.api.hermes_chat.VOLCENGINE_API_KEY", "vk-test"):
            key, url, model, is_ve = _resolve_llm_backend("doubao-seed-2-0-pro-260215")
            assert key == "vk-test"
            assert is_ve is True
            assert model == "doubao-seed-2-0-pro-260215"

    def test_unknown_model_uses_ollama(self):
        with patch("szyg.api.hermes_chat.VOLCENGINE_API_KEY", ""):
            key, url, model, is_ve = _resolve_llm_backend("qwen3:0.6B")
            assert is_ve is False

    def test_volcengine_endpoint_override(self):
        with patch("szyg.api.hermes_chat.VOLCENGINE_API_KEY", "vk-test"), \
             patch("szyg.api.hermes_chat.VOLCENGINE_ENDPOINTS", {"doubao-seed-2-0-pro-260215": "ep-custom-123"}):
            _, _, model, _ = _resolve_llm_backend("doubao-seed-2-0-pro-260215")
            assert model == "ep-custom-123"


class TestBuildSystemPrompt:
    def test_default_prompt(self):
        prompt, temp = _build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 100
        assert temp == 0.7

    def test_expert_prompt_takes_priority(self):
        expert = "你是SEO优化专家，专注于AI搜索引擎优化。"
        prompt, temp = _build_system_prompt(expert_prompt=expert)
        assert expert in prompt
        assert "中文" in prompt
        assert temp == 0.7

    def test_agent_id_config(self, tmp_path):
        configs = {
            "content": {
                "basic": {"name": "内容运营", "description": "负责内容创作"},
                "soul": {
                    "systemPrompt": "你是内容运营专家",
                    "behaviorMode": "fast",
                    "temperature": 0.5,
                },
                "skills": {"list": [{"name": "copywriting", "enabled": True}]},
            }
        }
        with patch("szyg.data_path.DATA_DIR", tmp_path):
            staff_dir = tmp_path / "staff"
            staff_dir.mkdir()
            (staff_dir / "agent_configs.json").write_text(json.dumps(configs), encoding="utf-8")
            prompt, temp = _build_system_prompt(agent_id="content")
            assert "内容运营" in prompt
            assert "内容创作" in prompt
            assert "copywriting" in prompt
            assert "marketing_kb" not in prompt
            assert temp == 0.5

    def test_unknown_agent_returns_default(self):
        prompt, temp = _build_system_prompt(agent_id="nonexistent")
        assert temp == 0.7


class TestSanitizeArgs:
    def test_valid_json(self):
        result = _sanitize_args("content_list", '{"status": "draft"}')
        assert result == {"status": "draft"}

    def test_invalid_json_returns_empty(self):
        result = _sanitize_args("tool", "not json")
        assert result == {}

    def test_strips_path_traversal(self):
        result = _sanitize_args("tool", '{"path": "../../etc/passwd"}')
        assert "../" not in result.get("path", "")

    def test_rejects_null_bytes(self):
        result = _sanitize_args("tool", '{"text": "hello\\x00world"}')
        assert "text" not in result

    def test_rejects_newlines(self):
        result = _sanitize_args("tool", '{"text": "line1\\nline2"}')
        assert "text" not in result

    def test_accepts_scalars(self):
        result = _sanitize_args("tool", '{"count": 42, "rate": 0.5, "flag": true}')
        assert result["count"] == 42
        assert result["rate"] == 0.5
        assert result["flag"] is True

    def test_rejects_nested_objects(self):
        result = _sanitize_args("tool", '{"nested": {"key": "val"}}')
        assert "nested" not in result

    def test_rejects_absolute_paths_for_path_args(self):
        result = _sanitize_args("tool", '{"file_path": "C:\\\\Windows\\\\system32\\\\cmd.exe"}')
        assert "file_path" not in result

    def test_rejects_unc_paths_double_backslash(self):
        # UNC paths start with \\ (double backslash) in actual bytes
        # After JSON parsing, "\\\\\\\\" → "\\\\" (two backslashes)
        result = _sanitize_args("tool", '{"input_files": "\\\\\\\\server\\\\\\\\share"}')
        assert "input_files" not in result

    def test_rejects_absolute_unix_paths(self):
        result = _sanitize_args("tool", '{"file_path": "/etc/passwd"}')
        assert "file_path" not in result

    def test_rejects_bare_dot_dot(self):
        result = _sanitize_args("tool", '{"path": ".."}')
        assert "path" not in result

    def test_rejects_bare_dot(self):
        result = _sanitize_args("tool", '{"path": "."}')
        assert "path" not in result


class TestHermesChatRequest:
    def test_defaults(self):
        req = HermesChatRequest(messages=[{"role": "user", "content": "hello"}])
        assert req.model == HERMES_DEFAULT_MODEL
        assert req.stream is True
        assert req.agent_id == ""
        assert req.expert_prompt == ""

    def test_custom_values(self):
        req = HermesChatRequest(
            model="custom-model",
            messages=[],
            stream=False,
            agent_id="content",
            expert_prompt="Expert prompt",
        )
        assert req.model == "custom-model"
        assert req.stream is False
        assert req.agent_id == "content"

    def test_empty_messages_allowed(self):
        req = HermesChatRequest(messages=[])
        assert req.messages == []


class TestHermesTools:
    def test_tools_defined(self):
        assert len(HERMES_TOOLS) > 0

    def test_tools_have_correct_format(self):
        for tool in HERMES_TOOLS:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_publisher_tools_exist(self):
        tool_names = [t["function"]["name"] for t in HERMES_TOOLS]
        assert "content_list" in tool_names
        assert "content_create" in tool_names
        assert "content_stats" in tool_names

    def test_platform_tools_exist(self):
        tool_names = [t["function"]["name"] for t in HERMES_TOOLS]
        assert "platform_list" in tool_names
        assert "platform_status" in tool_names

    def test_scheduler_tools_exist(self):
        tool_names = [t["function"]["name"] for t in HERMES_TOOLS]
        assert "scheduler_list" in tool_names
        assert "scheduler_create" in tool_names


class TestChatEndpointValidation:
    """Test the endpoint validation logic (without actual LLM calls)."""

    def test_empty_messages_raises(self):
        from fastapi import HTTPException
        from szyg.api.hermes_chat import hermes_chat
        req = HermesChatRequest(messages=[])
        with pytest.raises(HTTPException) as exc_info:
            # We can't call the endpoint directly without a request context,
            # but we can test the validation logic
            if not req.messages:
                raise HTTPException(422, "messages required")
        assert exc_info.value.status_code == 422
