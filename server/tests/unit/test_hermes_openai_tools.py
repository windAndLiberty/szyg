"""
「域灵」数字员工系统 - 云网关 tools schema 归一化测试

云网关只接受 OpenAI 嵌套格式 ``{"type": "function", "function": {...}}``。
Hermes 运行时传入扁平格式 ``{"type": "function", "name": ...}`` 时网关 502。
_openai_proxy 必须在转发前把 tools 统一为嵌套格式。
"""

import json

import pytest

from szyg.api.hermes_native_routes import _normalize_tools


class TestNormalizeTools:
    """tools 必须统一为云网关可解析的嵌套格式。"""

    def test_flat_tools_are_wrapped(self):
        tools = [
            {
                "type": "function",
                "name": "web_search",
                "description": "search the web",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                },
            },
            {
                "type": "function",
                "name": "read_file",
                "description": "read a file",
                "parameters": {"type": "object", "properties": {"path": {"type": "string"}}},
            },
        ]
        out = _normalize_tools(tools)
        assert len(out) == 2
        for item in out:
            assert item["type"] == "function"
            assert "function" in item
            assert isinstance(item["function"]["name"], str)
            assert isinstance(item["function"]["parameters"], dict)
        assert out[0]["function"]["name"] == "web_search"
        assert out[0]["function"]["description"] == "search the web"
        assert out[0]["function"]["parameters"]["properties"]["query"]["type"] == "string"
        assert out[1]["function"]["name"] == "read_file"

    def test_nested_tools_passthrough(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "calc",
                    "description": "calculate",
                    "parameters": {"type": "object", "properties": {"expr": {"type": "string"}}},
                },
            }
        ]
        out = _normalize_tools(tools)
        assert out == tools

    def test_empty_and_none(self):
        assert _normalize_tools([]) == []
        assert _normalize_tools(None) == []

    def test_invalid_items_dropped(self):
        out = _normalize_tools([{"type": "function"}, "garbage", None])
        assert out == []

    def test_missing_parameters_gets_default(self):
        out = _normalize_tools([{"type": "function", "name": "no_params"}])
        assert out[0]["function"]["parameters"] == {"type": "object", "properties": {}}

    def test_round_trip_json(self):
        tools = [{"type": "function", "name": "web_search", "description": "d",
                  "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}}]
        out = _normalize_tools(json.loads(json.dumps(tools)))
        assert out[0]["function"]["name"] == "web_search"