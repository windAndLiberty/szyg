# tests/test_evaluator_gate.py
"""Tests for the deterministic gate (Evaluator Layer 1)."""

from loop_agent.state import create_initial_state
from loop_agent.agents.evaluator_gate import deterministic_gate, GateResult


def test_all_tests_pass_gate_passes(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [
        {"command": "pytest", "exit_code": 0, "passed": True},
    ]
    f = tmp_path / "output.py"
    f.write_text("# hello")
    state["code_artifacts"] = [{"path": "output.py", "action": "modified"}]
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is True


def test_test_fails_gate_fails(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [{"command": "pytest", "exit_code": 1, "passed": False}]
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is False


def test_artifact_missing_gate_fails(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [{"command": "pytest", "exit_code": 0}]
    state["code_artifacts"] = [{"path": "nonexistent.py", "action": "modified"}]
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is False


def test_empty_artifacts_gate_fails(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [{"command": "pytest", "exit_code": 0}]
    state["code_artifacts"] = []
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is False


def test_artifact_path_escape_blocked(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [{"command": "pytest", "exit_code": 0}]
    state["code_artifacts"] = [{"path": "../../../etc/passwd", "action": "modified"}]
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is False
