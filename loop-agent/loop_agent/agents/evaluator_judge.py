# loop_agent/agents/evaluator_judge.py
"""Layer 3 of the Evaluator: fresh-context LLM decision with Default-FAIL contract."""

from __future__ import annotations

import json
import re

from loop_agent.models import create_model
from loop_agent.state import OrchestrationState
from loop_agent.agents.evaluator_gate import GateResult
from loop_agent.agents.evaluator_rubric import RubricResult


EVALUATOR_PROMPT = """\
You are an Evaluator agent in an autonomous coding loop. Your job is to
decide whether to FINISH the task, CONTINUE with another coding iteration,
REWIND to a previous checkpoint, or ESCALATE to a human.

## Deterministic Gate
{gate_result}

## Rubric Scores
{rubric_json}

## Acceptance Criteria
{acceptance_criteria}

## Iteration
{iteration} of max {max_iterations}

## Decision Rules
- If deterministic gate failed -> decide "continue"
- If any rubric dimension scored <= 2 -> decide "continue"
- If ALL acceptance criteria have passes=true AND all rubric dims >= 3 -> decide "finish"
- If iteration >= max_iterations -> decide "escalate"
- If score dropped > 0.3 vs previous review -> decide "rewind"

## Your Job
1. Review the acceptance criteria. They all start "passes: false".
   You can only mark passes: true if you READ a file and find concrete evidence.
   Use the read_file tool to verify claims.
2. Decide: finish, continue, rewind, or escalate.
3. Output ONLY a JSON object:

```json
{{
  "decision": "finish",
  "reasoning": "All acceptance criteria met, verified by reading README.md line 1",
  "acceptance_criteria": [
    {{"id": "AC-1", "passes": true, "evidence": "README.md:1: content is 'Hello'"}}
  ],
  "feedback": ""
}}
```

If continuing, include specific feedback for the Coder in "feedback".
Do not include any text outside the JSON block.
"""


def build_evaluator_prompt(state: OrchestrationState, gate: GateResult, rubric: RubricResult) -> str:
    return EVALUATOR_PROMPT.format(
        gate_result=json.dumps({"passed": gate.passed, "checks": gate.checks}, indent=2),
        rubric_json=json.dumps({
            "overall_score": rubric.overall_score,
            "has_critical_failure": rubric.has_critical_failure,
            "critical_dims": rubric.critical_dims,
            "dimensions": rubric.dimensions,
        }, indent=2),
        acceptance_criteria=json.dumps(state.get("acceptance_criteria", []), indent=2),
        iteration=state.get("iteration", 1),
        max_iterations=state.get("max_iterations", 3),
    )


def evaluator_judge(
    state: OrchestrationState,
    gate: GateResult,
    rubric: RubricResult,
    working_dir: str = ".",
) -> dict:
    """Run the fresh-context LLM decision."""
    # Short-circuit: gate failed.
    if not gate.passed:
        failed = [c for c in gate.checks if not c["passed"]]
        return {
            "decision": "continue",
            "reasoning": f"Deterministic gate failed: {json.dumps(failed)}",
            "acceptance_criteria": state.get("acceptance_criteria", []),
            "feedback": f"Fix these issues:\n{json.dumps(failed, indent=2)}",
        }

    # Short-circuit: rubric critical failure.
    if rubric.has_critical_failure:
        return {
            "decision": "continue",
            "reasoning": f"Rubric critical failure in: {rubric.critical_dims}",
            "acceptance_criteria": state.get("acceptance_criteria", []),
            "feedback": f"Improve these dimensions: {rubric.critical_dims}.",
        }

    # Hard limit: max iterations.
    iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", 3)
    if iteration >= max_iterations:
        return {
            "decision": "escalate",
            "reasoning": f"Max iterations reached ({iteration}/{max_iterations})",
            "acceptance_criteria": state.get("acceptance_criteria", []),
            "feedback": "Task requires human intervention.",
        }

    # Run the LLM with read-only tools.
    from loop_agent.tools import read_file as _read_file

    llm = create_model("evaluator")
    prompt = build_evaluator_prompt(state, gate, rubric)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Evaluate the task. You may use read_file to verify claims. Output your decision as JSON."},
    ]

    max_turns = 4
    for _ in range(max_turns):
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        if "read_file" in content.lower():
            files = _extract_file_paths(content)
            if files:
                results = [_read_file(fp, working_dir) for fp in files]
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"File contents:\n{json.dumps(results, indent=2)}\n\nNow output your decision JSON.",
                })
                continue

        parsed = _parse_json_output(content)
        if parsed:
            acs = parsed.get("acceptance_criteria", state.get("acceptance_criteria", []))
            # Default-FAIL enforcement.
            if parsed.get("decision") == "finish":
                unverified = [ac for ac in acs if not ac.get("passes") and not ac.get("evidence")]
                if unverified:
                    parsed["decision"] = "continue"
                    parsed["reasoning"] = (
                        f"Default-FAIL: {len(unverified)} ACs still have passes=false: "
                        f"{[u['id'] for u in unverified]}"
                    )
            return {
                "decision": parsed.get("decision", "continue"),
                "reasoning": parsed.get("reasoning", ""),
                "acceptance_criteria": acs,
                "feedback": parsed.get("feedback", ""),
            }

    return {
        "decision": "continue",
        "reasoning": "Evaluator LLM did not produce a valid JSON decision",
        "acceptance_criteria": state.get("acceptance_criteria", []),
        "feedback": "Evaluator failed to produce a decision.",
    }


def _extract_file_paths(text: str) -> list[str]:
    paths = []
    for match in re.finditer(r'`([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)`', text):
        paths.append(match.group(1))
    return paths[:5]


def _parse_json_output(text: str) -> dict | None:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None
