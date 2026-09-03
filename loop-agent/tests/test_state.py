# tests/test_state.py
"""Tests for OrchestrationState creation and validation."""

from loop_agent.state import create_initial_state, OrchestrationState


def test_create_initial_state_has_required_fields():
    state = create_initial_state("Fix typo", "Change Helo to Hello in README")
    assert state["status"] == "pending"
    assert state["topology"] == "prompt_chain"
    assert state["task_id"]
    import uuid
    uuid.UUID(state["task_id"])  # raises ValueError if not valid UUID
    assert state["request"]["title"] == "Fix typo"
    assert state["request"]["description"] == "Change Helo to Hello in README"
    assert state["plan"] is None
    assert state["code_artifacts"] == []
    assert state["test_results"] == []
    assert state["reviews"] == []
    assert state["rubric"] is None
    assert state["evaluation"] is None
    assert state["acceptance_criteria"] == []
    assert state["iteration"] == 0
    assert state["max_iterations"] == 3
    assert state["errors"] == []
    assert state["messages"] == []


def test_create_initial_state_custom_max_iterations():
    state = create_initial_state("Task", "Desc", max_iterations=5)
    assert state["max_iterations"] == 5


def test_initial_acceptance_criteria_empty():
    """Acceptance criteria start empty; Planner populates them."""
    state = create_initial_state("Task", "Desc")
    assert state["acceptance_criteria"] == []


import pytest


def test_task_id_is_unique():
    s1 = create_initial_state("A", "desc")
    s2 = create_initial_state("B", "desc")
    assert s1["task_id"] != s2["task_id"]


def test_create_initial_state_rejects_empty_title():
    with pytest.raises(ValueError, match="title"):
        create_initial_state("", "desc")


def test_create_initial_state_rejects_invalid_max_iterations():
    with pytest.raises(ValueError, match="max_iterations"):
        create_initial_state("Task", "desc", max_iterations=0)
