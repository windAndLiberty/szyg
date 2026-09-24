# loop_agent/agents/integration.py
"""Integration agent node — summarizes completed work."""

from __future__ import annotations

import json
import re

from loop_agent.models import create_model
from loop_agent.state import OrchestrationState


INTEGRATION_PROMPT = """\
You are an Integration agent. Summarize the completed work. Output ONLY JSON:
```json
{"summary": "Brief summary of the completed work", "artifacts_summary": ["list of changes"]}
```
"""


def integration_node(state: OrchestrationState) -> dict:
    llm = create_model("integration")
    request = state.get("request", {})
    plan = state.get("plan") or {}

    context = f"""## Task: {request.get('title', 'Unknown')}
## Plan: {plan.get('summary', json.dumps(plan))}
## Code Artifacts: {json.dumps(state.get('code_artifacts', []), indent=2)}
## Test Results: {json.dumps(state.get('test_results', []), indent=2)}
## Reviews: {json.dumps([{'agent': r.get('agent', '?'), 'score': r.get('score', 0)} for r in state.get('reviews', [])], indent=2)}"""

    messages = [
        {"role": "system", "content": INTEGRATION_PROMPT},
        {"role": "user", "content": context + "\n\nSummarize."},
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    parsed = _parse_json_output(content)
    return {
        "status": "completed",
        "messages": messages + ([{"role": "assistant", "content": content}] if parsed else []),
    }


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
