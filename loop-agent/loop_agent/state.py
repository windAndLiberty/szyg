# loop_agent/state.py
"""OrchestrationState definition and factory."""

from __future__ import annotations

import uuid
from typing import TypedDict


class OrchestrationState(TypedDict, total=False):
    """Shared state for the autonomous coding loop graph."""

    # Task metadata
    task_id: str
    request: dict[str, str]  # {"title": str, "description": str}
    status: str    # pending|planning|coding|testing|reviewing|integrating|completed|failed|halted
    topology: str  # "prompt_chain"

    # Agent outputs
    plan: dict | None
    code_artifacts: list[dict]
    test_results: list[dict]
    reviews: list[dict]
    rubric: dict | None
    evaluation: dict | None

    # Acceptance criteria (Default-FAIL contract)
    acceptance_criteria: list[dict]

    # Control
    iteration: int
    max_iterations: int
    errors: list[dict]

    # LangGraph messages
    messages: list[dict]


def create_initial_state(
    title: str,
    description: str,
    max_iterations: int = 3,
) -> OrchestrationState:
    """Create a minimal valid initial state for the loop.

    Args:
        title: Short task title.
        description: Detailed task description.
        max_iterations: Maximum coder->evaluator iterations before halting.

    Returns:
        An OrchestrationState dict ready for graph invocation.
    """
    if not title or not title.strip():
        raise ValueError("title must not be empty")
    if max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")
    task_id = str(uuid.uuid4())
    return {
        "task_id": task_id,
        "request": {"title": title, "description": description},
        "status": "pending",
        "topology": "prompt_chain",
        "plan": None,
        "code_artifacts": [],
        "test_results": [],
        "reviews": [],
        "rubric": None,
        "evaluation": None,
        "acceptance_criteria": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "errors": [],
        "messages": [],
    }
