# loop_agent/agents/coder.py
"""Coder agent node -- writes code to fulfil the plan."""

from __future__ import annotations

import json
import re

from loop_agent.models import create_model
from loop_agent.state import OrchestrationState
from loop_agent.tools import read_file, write_file, run_shell


CODER_SYSTEM_PROMPT = """\
You are a Coder agent in an autonomous coding loop.

## Task
{task_title}

## Description
{task_description}

## Plan
{plan_summary}

## Acceptance Criteria
{acceptance_criteria}

## Working Directory
{workdir}

## Previous Errors (if any)
{previous_errors}

## Your Job
1. Read the files you need to modify using the read_file tool.
2. Make the necessary edits using the write_file tool.
3. Run lint or type checks using the run_shell tool (e.g., "ruff check <file>", "mypy <file>").
4. After making changes, output ONLY a JSON object:

```json
{{
  "code_artifacts": [
    {{"path": "relative/path.py", "action": "modified", "diff": "description of change"}}
  ]
}}
```

If tests previously failed, pay attention to the error output and fix the issues.
If you cannot complete the task, respond with:
```json
{{
  "error": "description of what went wrong"
}}
```
Do not include any text outside the JSON block.
"""


def build_coder_prompt(state: OrchestrationState, working_dir: str = ".") -> str:
    """Build the coder's system prompt from the current state."""
    request = state.get("request", {})
    plan = state.get("plan") or {}
    acceptance = state.get("acceptance_criteria", [])
    errors = state.get("errors", [])
    previous = [e for e in errors if e.get("stage") in ("testing", "reviewing")]

    return CODER_SYSTEM_PROMPT.format(
        task_title=request.get("title", "Unknown task"),
        task_description=request.get("description", ""),
        plan_summary=plan.get("summary", json.dumps(plan, indent=2)) if plan else "No plan yet",
        acceptance_criteria=json.dumps(acceptance, indent=2),
        workdir=working_dir,
        previous_errors=json.dumps(previous, indent=2) if previous else "None",
    )


def coder_node(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Coder agent -- reads files, makes edits, outputs code_artifacts.

    LangGraph node function. Returns partial state update.
    """
    llm = create_model("coder")
    prompt = build_coder_prompt(state, working_dir)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Implement the task. Read files first, then make edits. Output a JSON result."},
    ]

    max_turns = 10
    for _ in range(max_turns):
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # Handle implicit tool requests from the LLM.
        if "read_file" in content.lower():
            files = _extract_file_paths(content)
            if files:
                tool_results = []
                for fp in files:
                    result = read_file(fp, working_dir)
                    tool_results.append(result)
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"File contents:\n{json.dumps(tool_results, indent=2)}\n\nContinue working. Output your final JSON when done.",
                })
                continue

        if "write_file" in content.lower():
            writes = _extract_write_commands(content)
            if writes:
                results = []
                for w in writes:
                    result = write_file(w["path"], w["content"], working_dir)
                    results.append(result)
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"Write results:\n{json.dumps(results, indent=2)}\n\nContinue or output your final JSON.",
                })
                continue

        if "run_shell" in content.lower() or any(cmd in content for cmd in ("pytest", "ruff", "mypy", "grep")):
            commands = _extract_shell_commands(content)
            if commands:
                tool_results = [run_shell(cmd, working_dir) for cmd in commands]
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"Command results:\n{json.dumps(tool_results, indent=2)}\n\nContinue or output your final JSON.",
                })
                continue

        # Try to parse JSON output.
        parsed = _parse_json_output(content)
        if parsed:
            return {
                "code_artifacts": parsed.get("code_artifacts", []),
                "messages": messages + [{"role": "assistant", "content": content}],
            }

    # Exhausted turns.
    return {
        "code_artifacts": [],
        "errors": [{"stage": "coding", "message": "Coder exceeded max tool-calling turns", "category": "convergence"}],
        "messages": messages,
    }


def _extract_file_paths(text: str) -> list[str]:
    """Extract file paths from text mentioning read operations."""
    paths = []
    for match in re.finditer(r'`([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)`', text):
        paths.append(match.group(1))
    return paths[:5]


def _extract_write_commands(text: str) -> list[dict]:
    """Extract write commands from text -- returns list of {path, content}."""
    writes = []
    # Look for ```<lang> <path>\n<content>\n``` blocks.
    for match in re.finditer(r'```(?:python|text|json|yaml)?\s*([a-zA-Z0-9_\-./]+)\n(.*?)```', text, re.DOTALL):
        path = match.group(1).strip()
        content = match.group(2).strip()
        if path and content:
            writes.append({"path": path, "content": content})
    return writes[:5]


def _extract_shell_commands(text: str) -> list[str]:
    """Extract shell commands from LLM output text."""
    commands = []
    for match in re.finditer(r"```(?:bash|shell|sh)?\s*\n(.*?)```", text, re.DOTALL):
        for line in match.group(1).strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append(line)
    for match in re.finditer(r'`([a-z][a-z0-9_\-./ ]+)`', text):
        cmd = match.group(1).strip()
        if any(cmd.startswith(p) for p in ("pytest", "python", "grep", "cat", "ls", "ruff", "mypy")):
            if cmd not in commands:
                commands.append(cmd)
    return commands


def _parse_json_output(text: str) -> dict | None:
    """Extract a JSON object from model output text."""
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
