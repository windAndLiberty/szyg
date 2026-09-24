# tests/test_tester.py
"""Tests for the Tester agent node."""

from unittest.mock import MagicMock, patch
from loop_agent.state import create_initial_state
from loop_agent.agents.tester import tester_node, build_tester_prompt, _extract_shell_commands


def test_build_tester_prompt_includes_artifacts():
    state = create_initial_state("Task", "Desc")
    state["code_artifacts"] = [{"path": "x.py", "action": "modified", "diff": "fix bug"}]
    prompt = build_tester_prompt(state)
    assert "x.py" in prompt
    assert "modified" in prompt


def test_extract_shell_commands_code_block():
    text = "Run this:\n```bash\npytest tests/\ngrep hello file.txt\n```"
    commands = _extract_shell_commands(text)
    assert "pytest tests/" in commands


def test_extract_shell_commands_inline():
    text = "Try `pytest` or `grep pattern file` to check"
    commands = _extract_shell_commands(text)
    assert any("pytest" in c for c in commands)


@patch("loop_agent.agents.tester.create_model")
def test_tester_node_returns_test_results(mock_create):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = (
        '```json\n'
        '{"test_results": [{"command": "pytest", "exit_code": 0, "passed": true, "stdout": "ok"}]}\n'
        '```'
    )
    mock_llm.invoke.return_value = mock_response
    mock_create.return_value = mock_llm

    state = create_initial_state("Task", "Desc")
    result = tester_node(state, working_dir=".")
    assert len(result["test_results"]) == 1
    assert result["test_results"][0]["passed"] is True


@patch("loop_agent.agents.tester.create_model")
def test_tester_node_max_turns(mock_create):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Let me think about tests..."  # no JSON
    mock_llm.invoke.return_value = mock_response
    mock_create.return_value = mock_llm

    state = create_initial_state("Task", "Desc")
    result = tester_node(state, working_dir=".")
    assert result["test_results"] == []
    assert any(e["stage"] == "testing" for e in result.get("errors", []))
