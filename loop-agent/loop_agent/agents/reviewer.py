# loop_agent/agents/reviewer.py
"""Reviewer agent node — reviews code from specific axes, supports parallel fan-out."""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from loop_agent.models import create_model
from loop_agent.state import OrchestrationState


REVIEWER_PROMPTS = {
    "correctness": """\
You are a Reviewer focused on CORRECTNESS.
Check: does this code meet the acceptance criteria? Are edge cases handled?
Are there logic errors, off-by-one bugs, null reference issues?
Review the code artifacts. Output JSON:
```json
{"agent": "correctness", "score": 0.95, "findings": [{"message": "specific issue at file:line"}]}
```
Score 0.0-1.0 where 1.0 means perfect correctness.""",

    "security": """\
You are a Reviewer focused on SECURITY.
Check: SQL injection, XSS, command injection, hardcoded secrets, path traversal,
insecure deserialization, missing auth checks.
Review the code artifacts. Output JSON:
```json
{"agent": "security", "score": 0.95, "findings": [{"message": "specific issue at file:line"}]}
```
Score 0.0-1.0 where 1.0 means no security issues.""",

    "performance": """\
You are a Reviewer focused on PERFORMANCE.
Check: N+1 queries, unnecessary allocations, blocking I/O, missing caches,
inefficient algorithms, memory leaks.
Review the code artifacts. Output JSON:
```json
{"agent": "performance", "score": 0.95, "findings": [{"message": "specific issue at file:line"}]}
```
Score 0.0-1.0 where 1.0 means optimal performance.""",
}


def build_reviewer_prompt(state: OrchestrationState, axis: str) -> str:
    base = REVIEWER_PROMPTS.get(axis, REVIEWER_PROMPTS["correctness"])
    artifacts = json.dumps(state.get("code_artifacts", []), indent=2)
    criteria = json.dumps(state.get("acceptance_criteria", []), indent=2)
    return base + f"\n\n## Code Artifacts\n{artifacts}\n\n## Acceptance Criteria\n{criteria}\n\nRead the modified files, review for {axis} issues, and output your review JSON."


def reviewer_node(state: OrchestrationState, axis: str = "correctness", working_dir: str = ".") -> dict:
    from loop_agent.tools import read_file

    llm = create_model("reviewer")
    prompt = build_reviewer_prompt(state, axis)

    artifacts = state.get("code_artifacts", [])
    file_contents = ""
    for art in artifacts:
        path = art.get("path", "")
        if path:
            result = read_file(path, working_dir)
            if result.get("content"):
                file_contents += f"\n--- {path} ---\n{result['content']}\n"

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Review these changes for {axis} issues:\n{file_contents[:8000]}\n\nOutput your review JSON."},
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)
    parsed = _parse_json_output(content)
    if parsed:
        return parsed
    return {"agent": axis, "score": 0.5, "findings": [{"message": f"Reviewer failed to produce valid JSON for {axis}"}]}


def reviewer_parallel(state: OrchestrationState, working_dir: str = ".", max_workers: int = 3) -> list[dict]:
    axes = ["correctness", "security", "performance"]
    reviews = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(axes))) as executor:
        futures = {executor.submit(reviewer_node, state, axis, working_dir): axis for axis in axes}
        for future in as_completed(futures):
            try:
                reviews.append(future.result())
            except Exception as exc:
                axis = futures[future]
                reviews.append({"agent": axis, "score": 0.0, "findings": [{"message": f"Reviewer {axis} failed: {exc}"}]})
    return reviews


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
