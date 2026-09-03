# loop_agent/agents/planner.py
"""Planner agent node — analyzes task and produces execution plan."""

from __future__ import annotations

import json
import re

from loop_agent.models import create_model
from loop_agent.state import OrchestrationState


PLANNER_SYSTEM_PROMPT = """\
You are a Planner agent in an autonomous coding loop.

## Task
{task_title}

## Description
{task_description}

## Your Job
1. Search for relevant technical background if needed.
2. Read project files to understand the current state.
3. Produce a structured implementation plan.

Output ONLY a JSON object:
```json
{{
  "plan": {{
    "summary": "one-line summary",
    "steps": [
      {{"id": "1", "description": "step description", "status": "pending"}}
    ],
    "acceptance_criteria": [
      {{"id": "AC-1", "description": "specific verifiable criterion"}}
    ]
  }}
}}
```

Each acceptance criterion must be specific and verifiable.
Do not include any text outside the JSON block.
"""


def planner_node(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Planner agent — produces plan and acceptance_criteria."""
    from loop_agent.tools import read_file

    llm = create_model("planner")
    request = state.get("request", {})
    prompt = PLANNER_SYSTEM_PROMPT.format(
        task_title=request.get("title", "Unknown task"),
        task_description=request.get("description", ""),
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Analyze the task and produce a plan."},
    ]

    max_turns = 8
    for _ in range(max_turns):
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        if "read" in content.lower():
            files = _extract_file_paths(content)
            if files:
                results = [read_file(fp, working_dir) for fp in files]
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"File contents:\n{json.dumps(results, indent=2)}\n\nProduce your plan JSON."})
                continue

        parsed = _parse_json_output(content)
        if parsed:
            plan_data = parsed.get("plan", parsed)
            criteria = plan_data.get("acceptance_criteria", [])
            acceptance_criteria = []
            for ac in criteria:
                if isinstance(ac, str):
                    acceptance_criteria.append({
                        "id": f"AC-{len(acceptance_criteria) + 1}",
                        "description": ac, "passes": False, "evidence": None,
                    })
                elif isinstance(ac, dict):
                    acceptance_criteria.append({
                        "id": ac.get("id", f"AC-{len(acceptance_criteria) + 1}"),
                        "description": ac.get("description", str(ac)),
                        "passes": False, "evidence": None,
                    })
            return {
                "plan": plan_data,
                "acceptance_criteria": acceptance_criteria,
                "messages": messages + [{"role": "assistant", "content": content}],
            }

    return {
        "plan": {"summary": "Planner failed", "steps": []},
        "acceptance_criteria": [],
        "errors": [{"stage": "planning", "message": "Planner exceeded max turns", "category": "convergence"}],
        "messages": messages,
    }


def _extract_file_paths(text: str) -> list[str]:
    paths = []
    for match in re.finditer(r'`([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)`', text):
        paths.append(match.group(1))
    return paths[:5]


def _parse_json_output(text: str) -> dict | None:
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(1))
        except json.JSONDecodeError: pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try: return json.loads(match.group(0))
        except json.JSONDecodeError: pass
    return None
