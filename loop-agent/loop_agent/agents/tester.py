# loop_agent/agents/tester.py
"""Tester agent node — runs tests and captures results."""

from __future__ import annotations

import json
import re

from loop_agent.models import create_model
from loop_agent.state import OrchestrationState
from loop_agent.tools import run_shell


TESTER_SYSTEM_PROMPT = """\
You are a Tester agent in an autonomous coding loop.

## Task
{task_title}

## Code Artifacts (what the Coder changed)
{code_artifacts}

## Acceptance Criteria
{acceptance_criteria}

## Your Job
Decide what test commands to run to verify the changes. Common commands:
- `pytest` for Python projects
- `grep <pattern> <file>` for content checks
- `ls <path>` to verify file existence

For each test, explain what you're checking. Output ONLY a JSON object:
```json
{{
  "test_results": [
    {{
      "command": "the command to run",
      "expected": "what this checks",
      "exit_code": 0,
      "passed": true,
      "stdout": "command output",
      "stderr": ""
    }}
  ]
}}
```
After describing the commands, use the run_shell tool to execute them.
Then update the JSON with actual exit codes and output.
Do not include any text outside the final JSON block.
"""


def build_tester_prompt(state: OrchestrationState) -> str:
    request = state.get("request", {})
    return TESTER_SYSTEM_PROMPT.format(
        task_title=request.get("title", "Unknown task"),
        code_artifacts=json.dumps(state.get("code_artifacts", []), indent=2),
        acceptance_criteria=json.dumps(state.get("acceptance_criteria", []), indent=2),
    )


def tester_node(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Tester agent — runs test commands and reports results."""
    llm = create_model("tester")
    prompt = build_tester_prompt(state)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Run tests to verify the changes. Use run_shell for each test command. Output a JSON test_results array with actual exit codes."},
    ]

    max_turns = 6
    for _ in range(max_turns):
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # If the model asks to run a command, do it.
        commands = _extract_shell_commands(content)
        if commands:
            tool_results = [run_shell(cmd, working_dir) for cmd in commands]
            messages.append({"role": "assistant", "content": content})
            messages.append({
                "role": "user",
                "content": f"Command results:\n{json.dumps(tool_results, indent=2)}\n\nNow output the final JSON test_results.",
            })
            continue

        # Try to parse final JSON.
        parsed = _parse_json_output(content)
        if parsed:
            return {
                "test_results": parsed.get("test_results", []),
                "messages": messages + [{"role": "assistant", "content": content}],
            }

    return {
        "test_results": [],
        "errors": [{"stage": "testing", "message": "Tester exceeded max turns", "category": "convergence"}],
        "messages": messages,
    }


def _extract_shell_commands(text: str) -> list[str]:
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
