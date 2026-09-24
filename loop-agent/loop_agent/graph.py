# loop_agent/graph.py
"""LangGraph StateGraph builder for the autonomous coding loop."""

from __future__ import annotations

from functools import partial

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from loop_agent.state import OrchestrationState, create_initial_state
from loop_agent.checkpoint import make_checkpoint_metadata


def route_after_evaluator(state: OrchestrationState) -> str:
    """Conditional edge: decide where to go after evaluator."""
    evaluation = state.get("evaluation") or {}
    decision = evaluation.get("decision", "continue")
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 3)

    if decision == "finish":
        return "integration"
    elif decision == "escalate":
        return "__end__"
    elif decision == "continue":
        if iteration >= max_iterations:
            return "__end__"
        return "coder"
    elif decision == "rewind":
        return "coder"
    else:
        return "__end__"


def classify_node(state: OrchestrationState) -> dict:
    """Classify task and select topology (v1: always prompt_chain)."""
    return {"status": "planning", "topology": "prompt_chain"}


def planner_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    from loop_agent.agents.planner import planner_node
    result = planner_node(state, working_dir)
    result["status"] = "coding"
    return result


def coder_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    from loop_agent.agents.coder import coder_node
    result = coder_node(state, working_dir)
    result["status"] = "testing"
    return result


def tester_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    from loop_agent.agents.tester import tester_node
    result = tester_node(state, working_dir)
    result["status"] = "reviewing"
    return result


def reviewer_parallel_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    from loop_agent.agents.reviewer import reviewer_parallel
    reviews = reviewer_parallel(state, working_dir)
    return {"reviews": reviews, "status": "reviewing"}


def evaluator_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    from loop_agent.agents.evaluator import evaluator_node
    return evaluator_node(state, working_dir)


def integration_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    from loop_agent.agents.integration import integration_node
    return integration_node(state)


def build_graph(working_dir: str = ".") -> StateGraph:
    """Build and compile the LangGraph StateGraph."""
    builder = StateGraph(OrchestrationState)

    builder.add_node("classify", classify_node)
    builder.add_node("planner", partial(planner_wrapper, working_dir=working_dir))
    builder.add_node("coder", partial(coder_wrapper, working_dir=working_dir))
    builder.add_node("tester", partial(tester_wrapper, working_dir=working_dir))
    builder.add_node("reviewer", partial(reviewer_parallel_wrapper, working_dir=working_dir))
    builder.add_node("evaluator", partial(evaluator_wrapper, working_dir=working_dir))
    builder.add_node("integration", partial(integration_wrapper, working_dir=working_dir))

    builder.set_entry_point("classify")
    builder.add_edge("classify", "planner")
    builder.add_edge("planner", "coder")
    builder.add_edge("coder", "tester")
    builder.add_edge("tester", "reviewer")
    builder.add_edge("reviewer", "evaluator")

    builder.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {"coder": "coder", "integration": "integration", "__end__": END},
    )
    builder.add_edge("integration", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


def create_loop_agent(working_dir: str = ".") -> StateGraph:
    """Create a compiled loop agent graph. Main public API entry point."""
    return build_graph(working_dir)


def run_loop(
    graph: StateGraph,
    title: str,
    description: str,
    max_iterations: int = 3,
    working_dir: str = ".",
) -> OrchestrationState:
    """Run the full loop and return the final state."""
    initial = create_initial_state(title, description, max_iterations)
    config = {"configurable": {"thread_id": initial["task_id"]}}
    return graph.invoke(initial, config)
