# tests/test_coder.py
"""Tests for the Coder agent node."""

from unittest.mock import MagicMock, patch
from loop_agent.state import create_initial_state
from loop_agent.agents.coder import (
    coder_node,
    build_coder_prompt,
    _parse_json_output,
    _extract_file_paths,
    _extract_shell_commands,
)


def test_build_coder_prompt_includes_task():
    state = create_initial_state("Fix typo", "Change Helo to Hello")
    state["plan"] = {"summary": "Edit README", "steps": []}
    state["acceptance_criteria"] = [{"id": "AC-1", "passes": False, "description": "README shows Hello"}]
    prompt = build_coder_prompt(state)
    assert "Fix typo" in prompt
    assert "Change Helo to Hello" in prompt
    assert "Edit README" in prompt
    assert "AC-1" in prompt


def test_build_coder_prompt_includes_previous_errors():
    state = create_initial_state("Task", "Desc")
    state["errors"] = [
        {"stage": "testing", "message": "Test failed: exit code 1"},
        {"stage": "planning", "message": "Some other error"},
    ]
    prompt = build_coder_prompt(state)
    assert "Test failed" in prompt
    assert "Some other" not in prompt  # only testing/reviewing errors


def test_parse_json_output_code_block():
    text = 'Here is my result:\n```json\n{"key": "value"}\n```'
    result = _parse_json_output(text)
    assert result == {"key": "value"}


def test_parse_json_output_inline_json():
    text = 'Some text {"answer": 42} more text'
    result = _parse_json_output(text)
    assert result == {"answer": 42}


def test_parse_json_output_no_json():
    text = "No JSON here, just text."
    result = _parse_json_output(text)
    assert result is None


def test_extract_file_paths():
    text = "Read `src/main.py` and `tests/test.py`"
    paths = _extract_file_paths(text)
    assert "src/main.py" in paths


def test_extract_shell_commands():
    text = "Run this:\n```bash\npytest tests/\ngrep hello file.txt\n```"
    commands = _extract_shell_commands(text)
    assert "pytest tests/" in commands


@patch("loop_agent.agents.coder.create_model")
def test_coder_node_produces_code_artifacts(mock_create):
    """Simulate the LLM returning a JSON code_artifacts block."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        '```json\n'
        '{"code_artifacts": [{"path": "x.py", "action": "modified", "diff": "fix"}]}\n'
        '```'
    )
    mock_llm.invoke.return_value = mock_response
    mock_create.return_value = mock_llm

    state = create_initial_state("Fix bug", "Fix the bug in x.py")
    state["plan"] = {"summary": "Edit x.py", "steps": []}
    result = coder_node(state, working_dir=".")
    assert len(result["code_artifacts"]) == 1
    assert result["code_artifacts"][0]["path"] == "x.py"


@patch("loop_agent.agents.coder.create_model")
def test_coder_node_handles_max_turns(mock_create):
    """When the LLM never produces JSON, return error after max turns."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Let me think about this..."  # no JSON, no tool calls
    mock_llm.invoke.return_value = mock_response
    mock_create.return_value = mock_llm

    state = create_initial_state("Task", "Desc")
    result = coder_node(state, working_dir=".")
    assert result["code_artifacts"] == []
    assert any(e["stage"] == "coding" for e in result.get("errors", []))
