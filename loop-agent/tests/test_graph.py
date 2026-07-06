# tests/test_graph.py
"""Tests for graph structure and routing logic."""

from loop_agent.state import create_initial_state
from loop_agent.graph import route_after_evaluator, classify_node, build_graph


class TestRouteAfterEvaluator:
    def test_finish_routes_to_integration(self):
        state = create_initial_state("Task", "Desc")
        state["evaluation"] = {"decision": "finish"}
        assert route_after_evaluator(state) == "integration"

    def test_continue_routes_to_coder(self):
        state = create_initial_state("Task", "Desc")
        state["evaluation"] = {"decision": "continue"}
        state["iteration"] = 1
        assert route_after_evaluator(state) == "coder"

    def test_continue_at_max_iterations_routes_to_end(self):
        state = create_initial_state("Task", "Desc", max_iterations=3)
        state["evaluation"] = {"decision": "continue"}
        state["iteration"] = 3
        assert route_after_evaluator(state) == "__end__"

    def test_escalate_routes_to_end(self):
        state = create_initial_state("Task", "Desc")
        state["evaluation"] = {"decision": "escalate"}
        assert route_after_evaluator(state) == "__end__"

    def test_rewind_routes_to_coder(self):
        state = create_initial_state("Task", "Desc")
        state["evaluation"] = {"decision": "rewind"}
        assert route_after_evaluator(state) == "coder"


class TestClassifyNode:
    def test_classify_sets_prompt_chain(self):
        state = create_initial_state("Task", "Desc")
        result = classify_node(state)
        assert result["status"] == "planning"
        assert result["topology"] == "prompt_chain"


class TestBuildGraph:
    def test_build_graph_returns_compiled_graph(self):
        graph = build_graph(".")
        assert graph is not None

    def test_graph_has_all_required_nodes(self):
        graph = build_graph(".")
        graph_def = graph.get_graph()
        node_names = {n for n in graph_def.nodes if not n.startswith("__")}
        expected = {"classify", "planner", "coder", "tester", "reviewer", "evaluator", "integration"}
        assert expected.issubset(node_names), f"Missing: {expected - node_names}"
