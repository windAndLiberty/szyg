# loop_agent/agents/evaluator.py
"""Evaluator agent node — combines all 3 layers into a single LangGraph node."""

from __future__ import annotations

from loop_agent.state import OrchestrationState
from loop_agent.agents.evaluator_gate import deterministic_gate
from loop_agent.agents.evaluator_rubric import compute_rubric
from loop_agent.agents.evaluator_judge import evaluator_judge


def evaluator_node(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Run the full 3-layer evaluator pipeline.

    1. Deterministic gate (no LLM)
    2. Multi-dimension rubric (no LLM)
    3. Fresh-context LLM decision

    Returns a partial state update with evaluation and updated acceptance_criteria.
    """
    iteration = state.get("iteration", 0) + 1

    gate = deterministic_gate(state, working_dir)
    rubric = compute_rubric(state)
    decision = evaluator_judge(state, gate, rubric, working_dir)

    # Determine status based on decision and iteration limit.
    status = "reviewing"  # default while loop continues
    dec = decision["decision"]
    if dec == "finish":
        status = "completed"
    elif dec == "escalate":
        status = "halted"
    elif iteration >= state.get("max_iterations", 3):
        status = "halted"

    return {
        "rubric": {
            "overall_score": rubric.overall_score,
            "has_critical_failure": rubric.has_critical_failure,
            "critical_dims": rubric.critical_dims,
            "dimensions": rubric.dimensions,
        },
        "evaluation": {
            "decision": dec,
            "reasoning": decision["reasoning"],
            "feedback": decision.get("feedback", ""),
        },
        "acceptance_criteria": decision.get("acceptance_criteria", state.get("acceptance_criteria", [])),
        "iteration": iteration,
        "status": status,
    }
