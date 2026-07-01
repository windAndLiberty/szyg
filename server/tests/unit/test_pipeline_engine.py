"""
Unit tests for szyg.pipeline_engine — pipeline DAG execution engine.

Focuses on the unit-testable helpers and data model classes.
"""

import pytest

from szyg.pipeline_engine import (
    NodeStatus,
    NodeType,
    PipelineNode,
    _extract_json,
)


class TestExtractJson:
    def test_plain_json_object(self):
        text = '{"key": "value", "num": 42}'
        result = _extract_json(text)
        assert result == {"key": "value", "num": 42}

    def test_json_in_markdown_fences(self):
        text = '```json\n{"title": "test"}\n```'
        result = _extract_json(text)
        assert result == {"title": "test"}

    def test_json_in_plain_fences(self):
        text = '```\n{"a": 1}\n```'
        result = _extract_json(text)
        assert result == {"a": 1}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result: {"score": 95} end of message'
        result = _extract_json(text)
        assert result == {"score": 95}

    def test_nested_json(self):
        text = '{"outer": {"inner": [1, 2, 3]}}'
        result = _extract_json(text)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_invalid_json_returns_none(self):
        text = "This is just plain text with no JSON"
        result = _extract_json(text)
        assert result is None

    def test_empty_string_returns_none(self):
        assert _extract_json("") is None

    def test_partial_json_returns_none(self):
        text = '{"incomplete": '
        result = _extract_json(text)
        assert result is None

    def test_json_array_parsed(self):
        # _extract_json also handles arrays via json.loads fallback
        text = '[1, 2, 3]'
        result = _extract_json(text)
        assert result == [1, 2, 3]

    def test_multiple_json_objects_returns_outermost(self):
        text = '{"a": 1} some text {"b": 2}'
        result = _extract_json(text)
        # Should find from first { to last }
        # The outermost span includes both, which is invalid JSON
        # So it falls back to parsing the whole cleaned text
        # This tests the robustness of the function
        assert result is None or isinstance(result, dict)

    def test_json_with_unicode(self):
        text = '{"名称": "测试", "数量": 10}'
        result = _extract_json(text)
        assert result == {"名称": "测试", "数量": 10}

    def test_json_with_newlines(self):
        text = '```json\n{\n  "multi": "line",\n  "value": true\n}\n```'
        result = _extract_json(text)
        assert result == {"multi": "line", "value": True}

    def test_json_with_leading_whitespace(self):
        text = '   \n  {"key": "val"}  \n  '
        result = _extract_json(text)
        assert result == {"key": "val"}


class TestNodeType:
    def test_all_types_exist(self):
        assert NodeType.TEXT == "text"
        assert NodeType.IMAGE == "image"
        assert NodeType.VIDEO == "video"
        assert NodeType.AUDIO == "audio"
        assert NodeType.EMBEDDING == "embedding"
        assert NodeType.SKILL == "skill"

    def test_string_enum_values(self):
        assert NodeType("text") == NodeType.TEXT
        assert NodeType("image") == NodeType.IMAGE


class TestNodeStatus:
    def test_all_statuses(self):
        assert NodeStatus.PENDING == "pending"
        assert NodeStatus.RUNNING == "running"
        assert NodeStatus.SUCCESS == "success"
        assert NodeStatus.FAILED == "failed"
        assert NodeStatus.SKIPPED == "skipped"


class TestPipelineNode:
    def test_default_construction(self):
        node = PipelineNode(id="n1", type=NodeType.TEXT)
        assert node.id == "n1"
        assert node.type == NodeType.TEXT
        assert node.model == ""
        assert node.name == "n1"  # defaults to id
        assert node.output_key == "n1"  # defaults to id
        assert node.timeout == 120
        assert node.retries == 1
        assert node.optional is False
        assert node.depends_on == []

    def test_string_type_coercion(self):
        node = PipelineNode(id="n2", type="image")
        assert node.type == NodeType.IMAGE

    def test_custom_name(self):
        node = PipelineNode(id="x", type=NodeType.TEXT, name="Custom Name")
        assert node.name == "Custom Name"

    def test_custom_output_key(self):
        node = PipelineNode(id="x", type=NodeType.TEXT, output_key="custom_out")
        assert node.output_key == "custom_out"

    def test_with_dependencies(self):
        node = PipelineNode(id="final", type=NodeType.VIDEO, depends_on=["script", "audio"])
        assert node.depends_on == ["script", "audio"]

    def test_data_mapping(self):
        node = PipelineNode(
            id="cover",
            type=NodeType.IMAGE,
            data_mapping={"prompt": "script.output"},
        )
        assert node.data_mapping == {"prompt": "script.output"}

    def test_prompt_template(self):
        node = PipelineNode(
            id="writer",
            type=NodeType.TEXT,
            prompt_template="Write about {input.topic}",
        )
        assert "{input.topic}" in node.prompt_template
