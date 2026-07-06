"""Tests for Planner, Reviewer, and Integration agents."""

from unittest.mock import MagicMock, patch
from loop_agent.state import create_initial_state
from loop_agent.agents.planner import planner_node
from loop_agent.agents.reviewer import reviewer_node, reviewer_parallel
from loop_agent.agents.integration import integration_node


class TestPlanner:
    @patch("loop_agent.agents.planner.create_model")
    def test_planner_produces_plan_and_criteria(self, mock_create):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n{"plan": {"summary": "Edit README", '
            '"steps": [{"id": "1", "description": "fix typo", "status": "pending"}], '
            '"acceptance_criteria": [{"id": "AC-1", "description": "README shows Hello"}]}}\n```'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm
        state = create_initial_state("Fix typo", "Change Helo to Hello")
        result = planner_node(state)
        assert result["plan"]["summary"] == "Edit README"
        assert len(result["acceptance_criteria"]) == 1
        assert result["acceptance_criteria"][0]["passes"] is False

    @patch("loop_agent.agents.planner.create_model")
    def test_planner_string_criteria_converted(self, mock_create):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n{"plan": {"summary": "Edit", "steps": [], '
            '"acceptance_criteria": ["README shows Hello", "tests pass"]}}\n```'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm
        state = create_initial_state("Task", "Desc")
        result = planner_node(state)
        assert len(result["acceptance_criteria"]) == 2
        assert all(ac["passes"] is False for ac in result["acceptance_criteria"])


class TestReviewer:
    @patch("loop_agent.agents.reviewer.create_model")
    def test_reviewer_single_axis(self, mock_create):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"agent": "security", "score": 0.9, "findings": []}'
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm
        state = create_initial_state("Task", "Desc")
        state["code_artifacts"] = [{"path": "x.py"}]
        result = reviewer_node(state, axis="security")
        assert result["agent"] == "security"
        assert result["score"] == 0.9

    @patch("loop_agent.agents.reviewer.reviewer_node")
    def test_reviewer_parallel_runs_all_axes(self, mock_node):
        mock_node.side_effect = lambda state, axis, wd: {"agent": axis, "score": 0.9, "findings": []}
        state = create_initial_state("Task", "Desc")
        state["code_artifacts"] = [{"path": "x.py"}]
        results = reviewer_parallel(state)
        axes = {r["agent"] for r in results}
        assert axes == {"correctness", "security", "performance"}


class TestIntegration:
    @patch("loop_agent.agents.integration.create_model")
    def test_integration_sets_completed(self, mock_create):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"summary": "Fixed typo", "artifacts_summary": ["README.md"]}'
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm
        state = create_initial_state("Task", "Desc")
        result = integration_node(state)
        assert result["status"] == "completed"
