# tests/test_evaluator.py
"""Tests for the combined 3-layer evaluator pipeline."""

from unittest.mock import MagicMock, patch
from loop_agent.state import create_initial_state
from loop_agent.agents.evaluator import evaluator_node


class TestEvaluatorNode:
    def test_deterministic_gate_failure_returns_continue(self, tmp_path):
        state = create_initial_state("Task", "Desc")
        state["test_results"] = [{"command": "pytest", "exit_code": 1, "passed": False}]
        state["code_artifacts"] = [{"path": "out.py", "action": "modified"}]
        (tmp_path / "out.py").write_text("# code")
        result = evaluator_node(state, str(tmp_path))
        assert result["evaluation"]["decision"] == "continue"

    def test_critical_rubric_failure_returns_continue(self, tmp_path):
        state = create_initial_state("Task", "Desc")
        state["test_results"] = [{"command": "pytest", "exit_code": 0}]
        state["code_artifacts"] = [{"path": "out.py", "action": "modified"}]
        state["reviews"] = [
            {"agent": "security", "score": 0.1, "findings": [{"message": "critical vuln"}]},
        ]
        (tmp_path / "out.py").write_text("# code")
        result = evaluator_node(state, str(tmp_path))
        assert result["evaluation"]["decision"] == "continue"

    @patch("loop_agent.agents.evaluator_judge.create_model")
    def test_all_pass_calls_llm_and_can_finish(self, mock_create, tmp_path):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n'
            '{"decision": "finish", "reasoning": "All checks pass", '
            '"acceptance_criteria": [{"id": "AC-1", "passes": true, "evidence": "README.md:1"}], '
            '"feedback": ""}\n'
            '```'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm

        state = create_initial_state("Task", "Desc")
        state["test_results"] = [{"command": "pytest", "exit_code": 0}]
        state["code_artifacts"] = [{"path": "out.py", "action": "modified"}]
        state["reviews"] = [
            {"agent": "correctness", "score": 0.9, "findings": []},
            {"agent": "security", "score": 0.9, "findings": []},
            {"agent": "performance", "score": 0.9, "findings": []},
        ]
        state["acceptance_criteria"] = [{"id": "AC-1", "passes": False, "description": "Test"}]
        (tmp_path / "out.py").write_text("# code")
        result = evaluator_node(state, str(tmp_path))
        assert result["evaluation"]["decision"] == "finish"

    @patch("loop_agent.agents.evaluator_judge.create_model")
    def test_max_iterations_escalates(self, mock_create, tmp_path):
        state = create_initial_state("Task", "Desc", max_iterations=3)
        state["test_results"] = [{"command": "pytest", "exit_code": 0}]
        state["code_artifacts"] = [{"path": "out.py", "action": "modified"}]
        state["reviews"] = [
            {"agent": "correctness", "score": 0.9, "findings": []},
        ]
        state["iteration"] = 3
        (tmp_path / "out.py").write_text("# code")
        result = evaluator_node(state, str(tmp_path))
        assert result["evaluation"]["decision"] == "escalate"


def test_default_fail_override():
    """Default-FAIL: finish with unverified ACs -> override to continue."""
    from loop_agent.agents.evaluator_judge import evaluator_judge
    from loop_agent.agents.evaluator_gate import GateResult
    from loop_agent.agents.evaluator_rubric import RubricResult

    state = create_initial_state("Task", "Desc")
    state["acceptance_criteria"] = [
        {"id": "AC-1", "passes": False, "description": "README shows Hello"},
    ]
    state["iteration"] = 1
    gate = GateResult(passed=True, checks=[])
    rubric = RubricResult(dimensions={}, overall_score=4.0, has_critical_failure=False)

    with patch("loop_agent.agents.evaluator_judge.create_model") as mock_create:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n'
            '{"decision": "finish", "reasoning": "looks good", '
            '"acceptance_criteria": [{"id": "AC-1", "passes": false, "evidence": null}], '
            '"feedback": ""}\n'
            '```'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm
        result = evaluator_judge(state, gate, rubric)
        assert result["decision"] == "continue"
        assert "Default-FAIL" in result["reasoning"]
