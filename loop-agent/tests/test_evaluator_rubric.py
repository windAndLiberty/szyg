# tests/test_evaluator_rubric.py
"""Tests for the rubric scorer (Evaluator Layer 2)."""

from loop_agent.state import create_initial_state
from loop_agent.agents.evaluator_rubric import compute_rubric


def test_empty_reviews_defaults_neutral():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = []
    result = compute_rubric(state)
    assert result.overall_score == 3.0
    assert result.has_critical_failure is False
    assert result.dimensions["correctness"]["score"] == 3


def test_high_score_all_dimensions():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = [
        {"agent": "correctness", "score": 0.9, "findings": []},
        {"agent": "security", "score": 1.0, "findings": []},
        {"agent": "performance", "score": 0.8, "findings": []},
        {"agent": "reviewer", "score": 0.9, "findings": []},
    ]
    result = compute_rubric(state)
    assert result.overall_score >= 3.5
    assert result.has_critical_failure is False


def test_low_score_triggers_critical():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = [
        {"agent": "correctness", "score": 0.9, "findings": []},
        {"agent": "security", "score": 0.2, "findings": [{"message": "SQL injection risk"}]},
    ]
    result = compute_rubric(state)
    assert result.has_critical_failure is True
    assert "security" in result.critical_dims


def test_evidence_accumulates():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = [
        {"agent": "correctness", "score": 0.5, "findings": [
            {"message": "auth.py:42: missing null check"},
        ]},
    ]
    result = compute_rubric(state)
    evidence = result.dimensions["correctness"]["evidence"]
    assert len(evidence) == 1
    assert "auth.py:42" in evidence[0]


def test_worst_score_wins():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = [
        {"agent": "security", "score": 1.0, "findings": []},
        {"agent": "security", "score": 0.3, "findings": [{"message": "xss"}]},
    ]
    result = compute_rubric(state)
    assert result.dimensions["security"]["score"] <= 2
