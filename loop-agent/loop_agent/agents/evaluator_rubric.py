# loop_agent/agents/evaluator_rubric.py
"""Layer 2 of the Evaluator: multi-dimension rubric scoring.

Aggregates reviewer outputs into 5 orthogonal dimensions (1-5 scale).
If any single dimension scores ≤ 2, the evaluator must return continue.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loop_agent.state import OrchestrationState

DIMENSIONS = {
    "correctness": {"weight": 30, "description": "Meets acceptance criteria, handles edge cases"},
    "security": {"weight": 20, "description": "Injections, permissions, secrets exposure"},
    "design": {"weight": 20, "description": "Follows project patterns, appropriate abstraction"},
    "performance": {"weight": 15, "description": "Unnecessary computation, N+1, memory"},
    "maintainability": {"weight": 15, "description": "Naming, comments, complexity, test coverage"},
}


@dataclass
class RubricResult:
    dimensions: dict[str, dict]
    overall_score: float
    has_critical_failure: bool
    critical_dims: list[str] = field(default_factory=list)


def compute_rubric(state: OrchestrationState) -> RubricResult:
    """Compute rubric scores from reviewer outputs."""
    reviews = state.get("reviews", [])
    dims: dict[str, dict] = {}
    scores: dict[str, list[int]] = {name: [] for name in DIMENSIONS}

    # Base structure and evidence collection
    for dim_name, dim_info in DIMENSIONS.items():
        dims[dim_name] = {
            "score": 3, "evidence": [],
            "weight": dim_info["weight"], "description": dim_info["description"],
        }

    # Pass 1: collect rubric scores and evidence per dimension
    for review in reviews:
        agent = review.get("agent", "")
        score = review.get("score", 0.5)
        findings = review.get("findings", [])
        rubric_score = max(1, min(5, round(score * 5)))

        target_dims: list[str] = []
        if agent == "correctness":
            target_dims.append("correctness")
        elif agent == "security":
            target_dims.append("security")
        elif agent == "performance":
            target_dims.append("performance")
        elif agent == "reviewer":
            target_dims.extend(["design", "maintainability"])

        for d in target_dims:
            scores[d].append(rubric_score)
            for f in findings:
                msg = f.get("message", str(f))
                dims[d]["evidence"].append(msg)

    # Pass 2: compute score per dimension — worst score from reviews, or 3 if none
    for dim_name in DIMENSIONS:
        if scores[dim_name]:
            dims[dim_name]["score"] = min(scores[dim_name])

    total_weight = sum(d["weight"] for d in dims.values())
    weighted_sum = sum(d["score"] * d["weight"] for d in dims.values())
    overall = round(weighted_sum / total_weight, 1) if total_weight > 0 else 3.0
    critical_dims = [name for name, d in dims.items() if d["score"] <= 2]

    return RubricResult(
        dimensions=dims,
        overall_score=overall,
        has_critical_failure=len(critical_dims) > 0,
        critical_dims=critical_dims,
    )
