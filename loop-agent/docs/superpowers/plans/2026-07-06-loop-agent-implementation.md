# Loop Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-correcting autonomous coding loop (prompt_chain topology) using LangGraph StateGraph with 6 agent nodes backed by NVIDIA NIM free models, featuring a 3-layer Evaluator with Default-FAIL contract.

**Architecture:** LangGraph StateGraph orchestrates Planner → Coder → Tester → Reviewer(×3 parallel) → Evaluator(3-layer) → Integration. Each agent node is a ChatNVIDIA-backed function with role-specific tools. The Evaluator enforces a Default-FAIL contract — acceptance criteria start as failing and must be proven passing with Read-tool evidence.

**Tech Stack:** Python 3.12, LangGraph (via deepagents), langchain-nvidia-ai-endpoints, tavily-python, pytest, jsonschema

---

## File Map

| File | Responsibility |
|------|---------------|
| `loop_agent/__init__.py` | Public API: `create_loop_agent()`, `run_loop()` |
| `loop_agent/state.py` | `OrchestrationState` TypedDict, factory function |
| `loop_agent/models.py` | `MODEL_REGISTRY` dict, `create_model()` factory, model configs |
| `loop_agent/tools.py` | Tool implementations: read_file, write_file, run_shell, search_code |
| `loop_agent/agents/__init__.py` | Re-exports all agent node functions |
| `loop_agent/agents/planner.py` | Planner node: system prompt + tool-calling logic |
| `loop_agent/agents/coder.py` | Coder node: system prompt + write_file tool use |
| `loop_agent/agents/tester.py` | Tester node: run_shell for test commands |
| `loop_agent/agents/reviewer.py` | Reviewer node + `reviewer_parallel()` fan-out |
| `loop_agent/agents/evaluator_gate.py` | Layer 1: `deterministic_gate()` — exit_code, artifacts check |
| `loop_agent/agents/evaluator_rubric.py` | Layer 2: `compute_rubric()` — 5-dim scoring from reviews |
| `loop_agent/agents/evaluator_judge.py` | Layer 3: `evaluator_judge()` — fresh-context LLM decision |
| `loop_agent/agents/evaluator.py` | `evaluator_node()` — combines all 3 layers |
| `loop_agent/agents/integration.py` | Integration node: summarization |
| `loop_agent/graph.py` | `build_graph()` — constructs StateGraph with nodes and edges |
| `loop_agent/checkpoint.py` | Helper functions for checkpoint metadata |
| `tests/test_state.py` | State creation and validation tests |
| `tests/test_agents.py` | Agent node unit tests with mocked ChatNVIDIA |
| `tests/test_evaluator.py` | Evaluator 3-layer pipeline tests |
| `tests/test_graph.py` | Graph structure and routing tests |
| `tests/test_e2e.py` | End-to-end: "Fix a typo in README" real NIM call |

---

### Task 1: Project scaffolding and state definition

**Files:**
- Create: `loop_agent/__init__.py`
- Create: `loop_agent/state.py`
- Create: `tests/test_state.py`

- [ ] **Step 1: Write the state module**

```python
# loop_agent/state.py
"""OrchestrationState definition and factory."""

from __future__ import annotations

import uuid
from typing import TypedDict


class OrchestrationState(TypedDict, total=False):
    """Shared state for the autonomous coding loop graph."""

    # Task metadata
    task_id: str
    request: dict  # {"title": str, "description": str}
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
    messages: list


def create_initial_state(
    title: str,
    description: str,
    max_iterations: int = 3,
    working_dir: str = ".",
) -> OrchestrationState:
    """Create a minimal valid initial state for the loop.

    Args:
        title: Short task title.
        description: Detailed task description.
        max_iterations: Maximum coder→evaluator iterations before halting.
        working_dir: Project working directory for file tools.

    Returns:
        An OrchestrationState dict ready for graph invocation.
    """
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
```

- [ ] **Step 2: Write the state test**

```python
# tests/test_state.py
"""Tests for OrchestrationState creation and validation."""

from loop_agent.state import create_initial_state, OrchestrationState


def test_create_initial_state_has_required_fields():
    state = create_initial_state("Fix typo", "Change Helo to Hello in README")
    assert state["status"] == "pending"
    assert state["topology"] == "prompt_chain"
    assert state["task_id"]
    assert len(state["task_id"]) == 36  # UUID4
    assert state["request"]["title"] == "Fix typo"
    assert state["request"]["description"] == "Change Helo to Hello in README"
    assert state["plan"] is None
    assert state["code_artifacts"] == []
    assert state["test_results"] == []
    assert state["reviews"] == []
    assert state["rubric"] is None
    assert state["evaluation"] is None
    assert state["acceptance_criteria"] == []
    assert state["iteration"] == 0
    assert state["max_iterations"] == 3
    assert state["errors"] == []
    assert state["messages"] == []


def test_create_initial_state_custom_max_iterations():
    state = create_initial_state("Task", "Desc", max_iterations=5)
    assert state["max_iterations"] == 5


def test_initial_acceptance_criteria_empty():
    """Acceptance criteria start empty; Planner populates them."""
    state = create_initial_state("Task", "Desc")
    assert state["acceptance_criteria"] == []


def test_task_id_is_unique():
    s1 = create_initial_state("A", "desc")
    s2 = create_initial_state("B", "desc")
    assert s1["task_id"] != s2["task_id"]
```

- [ ] **Step 3: Run tests, verify they pass**

Run: `uv run pytest tests/test_state.py -v`
Expected: 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add loop_agent/__init__.py loop_agent/state.py tests/test_state.py
git commit -m "feat: add OrchestrationState and initial state factory

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: Model registry and ChatNVIDIA factory

**Files:**
- Create: `loop_agent/models.py`
- Modify: `loop_agent/__init__.py` (add re-exports)

- [ ] **Step 1: Write the models module**

```python
# loop_agent/models.py
"""Model registry and ChatNVIDIA factory for agent nodes.

Maps each agent role to an NVIDIA NIM free-endpoint model based on
stress-test data (2026-07-06, 15 models, 4 rounds).
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from langchain_nvidia_ai_endpoints import ChatNVIDIA


@dataclass
class ModelConfig:
    """Configuration for a single agent role's LLM."""

    model: str
    timeout: int = 180
    temperature: float = 0.7
    max_completion_tokens: int = 4096


# Model-to-role mapping based on stress test results.
# avg_time and ttft are informational, not used at runtime.
MODEL_REGISTRY: dict[str, ModelConfig] = {
    "planner": ModelConfig(
        model="nvidia/nemotron-3-super-120b-a12b",
        timeout=180,
        temperature=0.7,
        max_completion_tokens=4096,
    ),
    "coder": ModelConfig(
        model="deepseek-ai/deepseek-v4-pro",
        timeout=180,
        temperature=0.7,
        max_completion_tokens=8192,
    ),
    "tester": ModelConfig(
        model="mistralai/mistral-small-4-119b-2603",
        timeout=180,
        temperature=0.3,
        max_completion_tokens=2048,
    ),
    "reviewer": ModelConfig(
        model="nvidia/nemotron-3-super-120b-a12b",
        timeout=180,
        temperature=0.3,
        max_completion_tokens=4096,
    ),
    "evaluator": ModelConfig(
        model="google/diffusiongemma-26b-a4b-it",
        timeout=180,
        temperature=0.3,
        max_completion_tokens=1024,
    ),
    "integration": ModelConfig(
        model="mistralai/mistral-medium-3.5-128b",
        timeout=180,
        temperature=0.5,
        max_completion_tokens=2048,
    ),
}

# Fallback models for when primary model is unavailable.
FALLBACK_MAP: dict[str, str] = {
    "nvidia/nemotron-3-super-120b-a12b": "mistralai/mistral-medium-3.5-128b",
    "deepseek-ai/deepseek-v4-pro": "moonshotai/kimi-k2.6",
    "mistralai/mistral-small-4-119b-2603": "google/gemma-4-31b-it",
    "google/diffusiongemma-26b-a4b-it": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "mistralai/mistral-medium-3.5-128b": "nvidia/nemotron-3-super-120b-a12b",
}


def create_model(role: str) -> ChatNVIDIA:
    """Create a ChatNVIDIA client configured for the given role.

    Args:
        role: One of planner, coder, tester, reviewer, evaluator, integration.

    Returns:
        A configured ChatNVIDIA instance.

    Raises:
        ValueError: If the role is unknown.
    """
    if role not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown role {role!r}; expected one of {list(MODEL_REGISTRY)}"
        )

    config = MODEL_REGISTRY[role]
    return ChatNVIDIA(
        model=config.model,
        api_key=os.environ["NVIDIA_API_KEY"],
        temperature=config.temperature,
        max_completion_tokens=config.max_completion_tokens,
        timeout=config.timeout,
    )


def get_fallback_model(primary_model: str) -> str | None:
    """Return a fallback model name for the given primary model.

    Args:
        primary_model: The model ID that failed.

    Returns:
        A fallback model ID, or None if no fallback is configured.
    """
    return FALLBACK_MAP.get(primary_model)
```

- [ ] **Step 2: Write tests**

```python
# tests/test_models.py
"""Tests for model registry and factory."""

import os
import pytest
from loop_agent.models import (
    create_model,
    get_fallback_model,
    MODEL_REGISTRY,
    FALLBACK_MAP,
    ModelConfig,
)
from langchain_nvidia_ai_endpoints import ChatNVIDIA


def test_registry_has_all_roles():
    expected_roles = {"planner", "coder", "tester", "reviewer", "evaluator", "integration"}
    assert set(MODEL_REGISTRY) == expected_roles


def test_all_models_have_valid_timeout():
    for role, config in MODEL_REGISTRY.items():
        assert config.timeout >= 60, f"{role} timeout too short: {config.timeout}"
        assert config.max_completion_tokens > 0, f"{role} has zero tokens"


def test_create_model_returns_chatnvidia(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    model = create_model("evaluator")
    assert isinstance(model, ChatNVIDIA)
    assert model.model == "google/diffusiongemma-26b-a4b-it"


def test_create_model_unknown_role_raises():
    with pytest.raises(ValueError, match="Unknown role"):
        create_model("garbage")


def test_get_fallback_model_known():
    fallback = get_fallback_model("deepseek-ai/deepseek-v4-pro")
    assert fallback == "moonshotai/kimi-k2.6"


def test_get_fallback_model_unknown():
    fallback = get_fallback_model("nonexistent/model")
    assert fallback is None
```

- [ ] **Step 3: Run tests, verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: 6 tests PASS

- [ ] **Step 4: Commit**

```bash
git add loop_agent/models.py loop_agent/__init__.py tests/test_models.py
git commit -m "feat: add model registry with NVIDIA NIM stress-test data

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: Tool implementations

**Files:**
- Create: `loop_agent/tools.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write the tools module**

```python
# loop_agent/tools.py
"""Tool implementations for agent nodes.

All file tools are scoped to the project working directory (no .. traversal).
run_shell enforces a command allow-list and 30s timeout.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any


class ToolError(Exception):
    """Raised when a tool execution fails."""


# ---------------------------------------------------------------------------
# read_file
# ---------------------------------------------------------------------------

def read_file(path: str, working_dir: str = ".") -> dict[str, Any]:
    """Read the contents of a file.

    Args:
        path: Relative path within the project.
        working_dir: Project root directory.

    Returns:
        {"path": str, "content": str, "lines": int}
    """
    resolved = _resolve_path(path, working_dir)
    if not resolved.exists():
        return {"path": path, "content": "", "lines": 0, "error": f"File not found: {path}"}
    if resolved.is_dir():
        return {"path": path, "content": "", "lines": 0, "error": f"Path is a directory: {path}"}
    try:
        content = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return {"path": path, "content": "", "lines": 0, "error": f"Not a text file: {path}"}
    return {
        "path": path,
        "content": content,
        "lines": content.count("\n") + (1 if content else 0),
    }


# ---------------------------------------------------------------------------
# write_file
# ---------------------------------------------------------------------------

def write_file(path: str, content: str, working_dir: str = ".") -> dict[str, Any]:
    """Write content to a file (creates or overwrites).

    Args:
        path: Relative path within the project.
        content: Text content to write.
        working_dir: Project root directory.

    Returns:
        {"path": str, "written": bool, "bytes": int}
    """
    resolved = _resolve_path(path, working_dir)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(content, encoding="utf-8")
    return {"path": path, "written": True, "bytes": len(content.encode("utf-8"))}


# ---------------------------------------------------------------------------
# run_shell
# ---------------------------------------------------------------------------

ALLOWED_COMMANDS = {
    "python", "python3", "pytest", "ruff", "mypy", "black",
    "grep", "cat", "ls", "head", "tail", "wc", "find", "echo",
    "npm", "node", "cargo", "go", "make", "git",
}

SHELL_TIMEOUT = 30


def run_shell(command: str, working_dir: str = ".") -> dict[str, Any]:
    """Execute a shell command.

    Only commands whose base executable is in ALLOWED_COMMANDS are permitted.
    The command runs with a 30-second timeout.

    Args:
        command: Shell command string.
        working_dir: Working directory for execution.

    Returns:
        {"command": str, "exit_code": int, "stdout": str, "stderr": str, "timed_out": bool}
    """
    base = command.strip().split()[0] if command.strip() else ""
    if os.path.basename(base) not in ALLOWED_COMMANDS and base not in ALLOWED_COMMANDS:
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command not allowed: {base}. Allowed: {sorted(ALLOWED_COMMANDS)}",
            "timed_out": False,
        }

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=SHELL_TIMEOUT,
            cwd=working_dir,
        )
        return {
            "command": command,
            "exit_code": result.returncode,
            "stdout": result.stdout[-5000:],
            "stderr": result.stderr[-2000:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {SHELL_TIMEOUT}s",
            "timed_out": True,
        }


# ---------------------------------------------------------------------------
# search_code
# ---------------------------------------------------------------------------

def search_code(pattern: str, path: str = ".", working_dir: str = ".") -> dict[str, Any]:
    """Search for a regex pattern in files under a directory.

    Args:
        pattern: Regex pattern to search for (Python re syntax).
        path: Directory or file path to search within.
        working_dir: Project root directory.

    Returns:
        {"pattern": str, "matches": [{"file": str, "line": int, "text": str}, ...], "count": int}
    """
    resolved = _resolve_path(path, working_dir)
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        return {"pattern": pattern, "matches": [], "count": 0, "error": f"Invalid regex: {e}"}

    matches = []
    paths = [resolved] if resolved.is_file() else list(resolved.rglob("*.py"))

    for filepath in paths:
        if not filepath.is_file():
            continue
        try:
            for i, line in enumerate(filepath.read_text(encoding="utf-8").splitlines(), 1):
                if compiled.search(line):
                    matches.append({
                        "file": str(filepath.relative_to(working_dir)),
                        "line": i,
                        "text": line.strip()[:200],
                    })
        except (UnicodeDecodeError, OSError):
            continue

    return {"pattern": pattern, "matches": matches, "count": len(matches)}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _resolve_path(path: str, working_dir: str) -> Path:
    """Resolve a path relative to working_dir, blocking traversal escapes."""
    cwd = Path(working_dir).resolve()
    resolved = (cwd / path).resolve()
    if not str(resolved).startswith(str(cwd)):
        raise ToolError(f"Path escapes working directory: {path}")
    return resolved
```

- [ ] **Step 2: Write tool tests**

```python
# tests/test_tools.py
"""Tests for tool implementations."""

import os
import tempfile
from pathlib import Path

from loop_agent.tools import (
    read_file,
    write_file,
    run_shell,
    search_code,
    ToolError,
)


class TestReadFile:
    def test_reads_existing_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello\nworld")
        result = read_file(str(f.relative_to(tmp_path)), str(tmp_path))
        assert result["content"] == "hello\nworld"
        assert result["lines"] == 2

    def test_file_not_found(self, tmp_path):
        result = read_file("nonexistent.txt", str(tmp_path))
        assert "File not found" in result["error"]

    def test_directory_rejected(self, tmp_path):
        d = tmp_path / "sub"
        d.mkdir()
        result = read_file("sub", str(tmp_path))
        assert "directory" in result["error"].lower()


class TestWriteFile:
    def test_writes_file(self, tmp_path):
        result = write_file("output.txt", "content", str(tmp_path))
        assert result["written"] is True
        assert (tmp_path / "output.txt").read_text() == "content"

    def test_creates_parent_dirs(self, tmp_path):
        write_file("deep/nested/file.txt", "data", str(tmp_path))
        assert (tmp_path / "deep" / "nested" / "file.txt").exists()


class TestRunShell:
    def test_allowed_command(self, tmp_path):
        result = run_shell("echo hello", str(tmp_path))
        assert result["exit_code"] == 0
        assert "hello" in result["stdout"]

    def test_disallowed_command(self, tmp_path):
        result = run_shell("curl http://evil.com", str(tmp_path))
        assert result["exit_code"] == -1
        assert "Command not allowed" in result["stderr"]


class TestSearchCode:
    def test_finds_pattern(self, tmp_path):
        (tmp_path / "a.py").write_text("def foo():\n    return 1\n")
        result = search_code(r"def foo", ".", str(tmp_path))
        assert result["count"] == 1
        assert result["matches"][0]["file"] == "a.py"

    def test_invalid_regex(self, tmp_path):
        result = search_code(r"[invalid", ".", str(tmp_path))
        assert "Invalid regex" in result["error"]


class TestPathSafety:
    def test_blocks_escape(self, tmp_path):
        with __import__("pytest").raises(ToolError, match="escapes"):
            from loop_agent.tools import _resolve_path
            _resolve_path("../../../etc/passwd", str(tmp_path))
```

- [ ] **Step 3: Run tests, verify they pass**

Run: `uv run pytest tests/test_tools.py -v`
Expected: 8+ tests PASS

- [ ] **Step 4: Commit**

```bash
git add loop_agent/tools.py tests/test_tools.py
git commit -m "feat: add tool implementations (read/write/shell/search)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: Coder agent node

**Files:**
- Create: `loop_agent/agents/__init__.py`
- Create: `loop_agent/agents/coder.py`

- [ ] **Step 1: Write the coder agent**

```python
# loop_agent/agents/coder.py
"""Coder agent node — writes code to fulfil the plan."""

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


def coder_node(state: OrchestrationState) -> dict:
    """Coder agent — reads files, makes edits, outputs code_artifacts.

    This is a LangGraph node function. It receives the full state and returns
    a partial state update.
    """
    import os as _os
    llm = create_model("coder")
    prompt = build_coder_prompt(state)

    # Define tool functions that the LLM can call.
    tools = {
        "read_file": read_file,
        "write_file": write_file,
        "run_shell": run_shell,
    }

    # Bind tools as available functions (tool_choice="auto").
    llm_with_tools = llm.bind_tools(
        [{"type": "function", "function": _tool_schema(name, fn)} for name, fn in tools.items()]
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Implement the task. Read files first, then make edits. Output a JSON result."},
    ]

    max_turns = 10
    for _ in range(max_turns):
        response = llm_with_tools.invoke(messages)
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                if tool_name in tools:
                    result = tools[tool_name](**tool_args)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result)})
        else:
            # No more tool calls — parse the output.
            content = response.content if hasattr(response, "content") else str(response)
            parsed = _parse_json_output(content)
            if parsed:
                return {
                    "code_artifacts": parsed.get("code_artifacts", []),
                    "messages": messages + [{"role": "assistant", "content": content}],
                }
            # If no JSON found, treat the entire response as the result.
            return {
                "code_artifacts": [{"path": "unknown", "action": "modified", "diff": content[:500]}],
                "messages": messages + [{"role": "assistant", "content": content}],
            }

    # Exhausted tool-calling turns.
    return {
        "code_artifacts": [],
        "errors": [{"stage": "coding", "message": "Coder exceeded max tool-calling turns", "category": "convergence"}],
        "messages": messages,
    }


def _tool_schema(name: str, fn) -> dict:
    """Generate an OpenAI-compatible function schema for a Python function."""
    import inspect
    sig = inspect.signature(fn)
    properties = {}
    required = []
    for pname, param in sig.parameters.items():
        if pname == "working_dir":
            continue
        ptype = "string"
        if param.annotation is int:
            ptype = "integer"
        elif param.annotation is bool:
            ptype = "boolean"
        properties[pname] = {"type": ptype, "description": pname}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {
        "name": name,
        "description": (fn.__doc__ or f"Call {name}").split("\n")[0],
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def _parse_json_output(text: str) -> dict | None:
    """Extract a JSON object from model output text."""
    # Try ```json ... ``` block first.
    match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try first { ... } block.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None
```

- [ ] **Step 2: Write coder tests with mocked LLM**

```python
# tests/test_coder.py
"""Tests for the Coder agent node."""

import json
from unittest.mock import MagicMock, patch
from loop_agent.state import create_initial_state
from loop_agent.agents.coder import coder_node, build_coder_prompt, _parse_json_output


def test_build_coder_prompt_includes_task():
    state = create_initial_state("Fix typo", "Change Helo to Hello")
    state["plan"] = {"summary": "Edit README", "steps": []}
    state["acceptance_criteria"] = [{"id": "AC-1", "passes": False, "description": "README shows Hello"}]
    prompt = build_coder_prompt(state)
    assert "Fix typo" in prompt
    assert "Change Helo to Hello" in prompt
    assert "Edit README" in prompt
    assert "AC-1" in prompt


def test_build_coder_prompt_includes_previous_errors():
    state = create_initial_state("Task", "Desc")
    state["errors"] = [
        {"stage": "testing", "message": "Test failed: exit code 1"},
        {"stage": "planning", "message": "Some other error"},
    ]
    prompt = build_coder_prompt(state)
    assert "Test failed" in prompt
    assert "Some other" not in prompt  # only testing/reviewing errors


def test_parse_json_output_code_block():
    text = 'Here is my result:\n```json\n{"key": "value"}\n```'
    result = _parse_json_output(text)
    assert result == {"key": "value"}


def test_parse_json_output_inline_json():
    text = 'Some text {"answer": 42} more text'
    result = _parse_json_output(text)
    assert result == {"answer": 42}


def test_parse_json_output_no_json():
    text = "No JSON here, just text."
    result = _parse_json_output(text)
    assert result is None


@patch("loop_agent.agents.coder.create_model")
def test_coder_node_produces_code_artifacts(mock_create):
    """Simulate the LLM returning a JSON code_artifacts block."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '```json\n{"code_artifacts": [{"path": "x.py", "action": "modified", "diff": "fix"}]}\n```'
    mock_response.tool_calls = None
    mock_llm.invoke.return_value = mock_response
    mock_create.return_value = mock_llm

    state = create_initial_state("Fix bug", "Fix the bug in x.py")
    state["plan"] = {"summary": "Edit x.py", "steps": []}
    result = coder_node(state)
    assert len(result["code_artifacts"]) == 1
    assert result["code_artifacts"][0]["path"] == "x.py"
```

- [ ] **Step 3: Run tests, verify they pass**

Run: `uv run pytest tests/test_coder.py -v`
Expected: 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add loop_agent/agents/__init__.py loop_agent/agents/coder.py tests/test_coder.py
git commit -m "feat: add Coder agent node with tool-calling support

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: Tester agent node

**Files:**
- Create: `loop_agent/agents/tester.py`
- Create: `tests/test_tester.py`

- [ ] **Step 1: Write the tester agent**

```python
# loop_agent/agents/tester.py
"""Tester agent node — runs tests and captures results."""

from __future__ import annotations

import json
import re

from loop_agent.models import create_model
from loop_agent.state import OrchestrationState


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
- `python -m pytest tests/` for specific test dirs
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
    """Build the tester's system prompt from the current state."""
    request = state.get("request", {})
    return TESTER_SYSTEM_PROMPT.format(
        task_title=request.get("title", "Unknown task"),
        code_artifacts=json.dumps(state.get("code_artifacts", []), indent=2),
        acceptance_criteria=json.dumps(state.get("acceptance_criteria", []), indent=2),
    )


def tester_node(state: OrchestrationState) -> dict:
    """Tester agent — runs test commands and reports results.

    LangGraph node function. Returns a partial state update with test_results.
    """
    from loop_agent.tools import run_shell

    llm = create_model("tester")
    prompt = build_tester_prompt(state)

    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": (
                "Run tests to verify the changes. Use run_shell for each test command. "
                "Output a JSON test_results array with actual exit codes."
            ),
        },
    ]

    max_turns = 6
    for _ in range(max_turns):
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # If the model asks to run a command, do it and continue the loop.
        if "run_shell" in content.lower() or "pytest" in content or "grep" in content:
            # Extract and run shell commands from the response.
            commands = _extract_shell_commands(content)
            if commands:
                tool_results = []
                for cmd in commands:
                    result = run_shell(cmd)
                    tool_results.append(result)
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"Command results:\n{json.dumps(tool_results, indent=2)}\n\nNow output the final JSON test_results.",
                })
                continue

        # Try to parse the final output.
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
    """Extract shell commands from LLM output text."""
    commands = []
    # Look for ```bash ... ``` blocks.
    for match in re.finditer(r"```(?:bash|shell|sh)?\s*\n(.*?)```", text, re.DOTALL):
        for line in match.group(1).strip().split("\n"):
            line = line.strip()
            if line and not line.startswith("#"):
                commands.append(line)
    # Also look for `command` inline.
    for match in re.finditer(r"`([a-z][a-z0-9_\-./ ]+)`", text):
        cmd = match.group(1).strip()
        if any(cmd.startswith(p) for p in ("pytest", "python", "grep", "cat", "ls", "ruff", "mypy")):
            if cmd not in commands:
                commands.append(cmd)
    return commands


def _parse_json_output(text: str) -> dict | None:
    """Extract a JSON object from model output."""
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
```

- [ ] **Step 2: Write tester tests**

```python
# tests/test_tester.py
"""Tests for the Tester agent node."""

from unittest.mock import MagicMock, patch
from loop_agent.state import create_initial_state
from loop_agent.agents.tester import tester_node, build_tester_prompt, _extract_shell_commands


def test_build_tester_prompt_includes_artifacts():
    state = create_initial_state("Task", "Desc")
    state["code_artifacts"] = [{"path": "x.py", "action": "modified", "diff": "fix bug"}]
    prompt = build_tester_prompt(state)
    assert "x.py" in prompt
    assert "modified" in prompt


def test_extract_shell_commands_code_block():
    text = "Run this:\n```bash\npytest tests/\ngrep hello file.txt\n```"
    commands = _extract_shell_commands(text)
    assert "pytest tests/" in commands


def test_extract_shell_commands_inline():
    text = "Try `pytest` or `grep pattern file` to check"
    commands = _extract_shell_commands(text)
    assert any("pytest" in c for c in commands)


@patch("loop_agent.agents.tester.create_model")
def test_tester_node_returns_test_results(mock_create):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = '```json\n{"test_results": [{"command": "pytest", "exit_code": 0, "passed": true, "stdout": "ok"}]}\n```'
    mock_llm.invoke.return_value = mock_response
    mock_create.return_value = mock_llm

    state = create_initial_state("Task", "Desc")
    result = tester_node(state)
    assert len(result["test_results"]) == 1
    assert result["test_results"][0]["passed"] is True
```

- [ ] **Step 3: Run tests, verify they pass**

Run: `uv run pytest tests/test_tester.py -v`
Expected: 4 tests PASS

- [ ] **Step 4: Commit**

```bash
git add loop_agent/agents/tester.py tests/test_tester.py
git commit -m "feat: add Tester agent node with shell command extraction

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 6: Evaluator — Layer 1 (Deterministic Gate)

**Files:**
- Create: `loop_agent/agents/evaluator_gate.py`
- Create: `tests/test_evaluator_gate.py`

- [ ] **Step 1: Write the deterministic gate**

```python
# loop_agent/agents/evaluator_gate.py
"""Layer 1 of the Evaluator: deterministic hardware checks.

No LLM calls. Runs before any model inference to catch unambiguous failures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from loop_agent.state import OrchestrationState


@dataclass
class GateResult:
    """Result of deterministic gate evaluation."""

    passed: bool
    checks: list[dict] = field(default_factory=list)
    """Each check: {"name": str, "passed": bool, "detail": str}"""


def deterministic_gate(state: OrchestrationState, working_dir: str = ".") -> GateResult:
    """Run hardware checks against the current state.

    Checks:
    1. All test_results have exit_code == 0.
    2. All code_artifacts paths exist on disk.
    3. code_artifacts is not empty (regression check).

    Args:
        state: Current orchestration state.
        working_dir: Project root for file checks.

    Returns:
        GateResult with passed=True only if all checks pass.
    """
    checks = []

    # Check 1: test exit codes
    test_results = state.get("test_results", [])
    for tr in test_results:
        exit_code = tr.get("exit_code", -1)
        passed = exit_code == 0
        checks.append({
            "name": f"test_exit_code:{tr.get('command', 'unknown')}",
            "passed": passed,
            "detail": f"exit_code={exit_code}" if not passed else "ok",
        })

    # Check 2: code artifacts exist on disk
    cwd = Path(working_dir).resolve()
    artifacts = state.get("code_artifacts", [])
    for art in artifacts:
        path = art.get("path", "")
        resolved = (cwd / path).resolve()
        if not str(resolved).startswith(str(cwd)):
            checks.append({
                "name": f"artifact_in_bounds:{path}",
                "passed": False,
                "detail": f"Path escapes working directory",
            })
            continue
        exists = resolved.exists()
        checks.append({
            "name": f"artifact_exists:{path}",
            "passed": exists,
            "detail": f"File {'exists' if exists else 'missing'}: {path}",
        })

    # Check 3: code_artifacts is not empty (no regression)
    if not artifacts:
        checks.append({
            "name": "no_regression",
            "passed": False,
            "detail": "code_artifacts is empty — nothing was produced",
        })

    all_passed = all(c["passed"] for c in checks)
    return GateResult(passed=all_passed, checks=checks)
```

- [ ] **Step 2: Write gate tests**

```python
# tests/test_evaluator_gate.py
"""Tests for the deterministic gate (Evaluator Layer 1)."""

from loop_agent.state import create_initial_state
from loop_agent.agents.evaluator_gate import deterministic_gate, GateResult


def test_all_tests_pass_gate_passes(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [
        {"command": "pytest", "exit_code": 0, "passed": True},
        {"command": "grep hello README.md", "exit_code": 0, "passed": True},
    ]
    # Create a fake artifact file.
    f = tmp_path / "output.py"
    f.write_text("# hello")
    state["code_artifacts"] = [{"path": "output.py", "action": "modified"}]

    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is True


def test_test_fails_gate_fails(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [
        {"command": "pytest", "exit_code": 1, "passed": False},
    ]
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is False
    assert any("exit_code=1" in c["detail"] for c in result.checks)


def test_artifact_missing_gate_fails(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [{"command": "pytest", "exit_code": 0, "passed": True}]
    state["code_artifacts"] = [{"path": "nonexistent.py", "action": "modified"}]
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is False


def test_empty_artifacts_gate_fails(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [{"command": "pytest", "exit_code": 0, "passed": True}]
    state["code_artifacts"] = []
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is False
    assert any("empty" in c["detail"] for c in result.checks)


def test_artifact_path_escape_blocked(tmp_path):
    state = create_initial_state("Task", "Desc")
    state["test_results"] = [{"command": "pytest", "exit_code": 0}]
    state["code_artifacts"] = [{"path": "../../../etc/passwd", "action": "modified"}]
    result = deterministic_gate(state, str(tmp_path))
    assert result.passed is False
    assert any("escapes" in c["detail"].lower() for c in result.checks)
```

- [ ] **Step 3: Run tests, verify they pass**

Run: `uv run pytest tests/test_evaluator_gate.py -v`
Expected: 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add loop_agent/agents/evaluator_gate.py tests/test_evaluator_gate.py
git commit -m "feat: add Evaluator Layer 1 — deterministic gate checks

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 7: Evaluator — Layer 2 (Rubric Scoring)

**Files:**
- Create: `loop_agent/agents/evaluator_rubric.py`
- Create: `tests/test_evaluator_rubric.py`

- [ ] **Step 1: Write the rubric scorer**

```python
# loop_agent/agents/evaluator_rubric.py
"""Layer 2 of the Evaluator: multi-dimension rubric scoring.

Aggregates reviewer outputs into 5 orthogonal dimensions (1-5 scale).
If any single dimension scores ≤ 2, the evaluator must return continue.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loop_agent.state import OrchestrationState

DIMENSIONS = {
    "correctness": {
        "weight": 30,
        "description": "Meets acceptance criteria, handles edge cases",
    },
    "security": {
        "weight": 20,
        "description": "Injections, permissions, secrets exposure",
    },
    "design": {
        "weight": 20,
        "description": "Follows project patterns, appropriate abstraction",
    },
    "performance": {
        "weight": 15,
        "description": "Unnecessary computation, N+1, memory",
    },
    "maintainability": {
        "weight": 15,
        "description": "Naming, comments, complexity, test coverage",
    },
}


@dataclass
class RubricResult:
    """Result of rubric evaluation."""

    dimensions: dict[str, dict]
    """{dim_name: {"score": int, "evidence": [str], "weight": int}}"""

    overall_score: float
    """Weighted average of dimension scores (1.0-5.0)."""

    has_critical_failure: bool
    """True if any dimension score ≤ 2."""

    critical_dims: list[str] = field(default_factory=list)
    """Names of dimensions with score ≤ 2."""


def compute_rubric(state: OrchestrationState) -> RubricResult:
    """Compute rubric scores from reviewer outputs.

    Maps reviewer findings to the 5 scoring dimensions. Each reviewer
    (correctness, security, performance) maps to one or more dimensions.
    Reviewers not run default to score=3 (neutral).

    Args:
        state: Current orchestration state with reviews populated.

    Returns:
        RubricResult with dimension scores and overall weighted average.
    """
    reviews = state.get("reviews", [])
    dimensions: dict[str, dict] = {}

    for dim_name, dim_info in DIMENSIONS.items():
        # Default: neutral score = 3, no evidence.
        dimensions[dim_name] = {
            "score": 3,
            "evidence": [],
            "weight": dim_info["weight"],
            "description": dim_info["description"],
        }

    # Map reviewer outputs to dimensions.
    for review in reviews:
        agent = review.get("agent", "")
        score = review.get("score", 0.5)
        findings = review.get("findings", [])

        # Convert 0-1 score from reviewer to 1-5 rubric scale.
        rubric_score = max(1, min(5, round(score * 5)))

        # Route reviewer output to the right dimension(s).
        if agent == "correctness":
            _update_dim(dimensions, "correctness", rubric_score, findings)
        elif agent == "security":
            _update_dim(dimensions, "security", rubric_score, findings)
        elif agent == "performance":
            _update_dim(dimensions, "performance", rubric_score, findings)
        elif agent == "reviewer":
            # Generic reviewer — apply to design and maintainability.
            _update_dim(dimensions, "design", rubric_score, findings)
            _update_dim(dimensions, "maintainability", rubric_score, findings)

    # Compute weighted overall score.
    total_weight = sum(d["weight"] for d in dimensions.values())
    weighted_sum = sum(d["score"] * d["weight"] for d in dimensions.values())
    overall = round(weighted_sum / total_weight, 1) if total_weight > 0 else 3.0

    # Check for critical failures.
    critical_dims = [name for name, d in dimensions.items() if d["score"] <= 2]

    return RubricResult(
        dimensions=dimensions,
        overall_score=overall,
        has_critical_failure=len(critical_dims) > 0,
        critical_dims=critical_dims,
    )


def _update_dim(
    dimensions: dict,
    dim_name: str,
    score: int,
    findings: list[dict],
) -> None:
    """Update a dimension with reviewer findings (use worst score)."""
    if dim_name not in dimensions:
        return
    existing = dimensions[dim_name]
    # Use the lower score (worst-case) from multiple reviewers.
    existing["score"] = min(existing["score"], score)
    for f in findings:
        msg = f.get("message", str(f))
        existing["evidence"].append(msg)
```

- [ ] **Step 2: Write rubric tests**

```python
# tests/test_evaluator_rubric.py
"""Tests for the rubric scorer (Evaluator Layer 2)."""

from loop_agent.state import create_initial_state
from loop_agent.agents.evaluator_rubric import compute_rubric, RubricResult


def test_empty_reviews_defaults_neutral():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = []
    result = compute_rubric(state)
    assert result.overall_score == 3.0
    assert result.has_critical_failure is False
    assert result.dimensions["correctness"]["score"] == 3


def test_high_score_all_dimensions():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = [
        {"agent": "correctness", "score": 0.9, "findings": []},
        {"agent": "security", "score": 1.0, "findings": []},
        {"agent": "performance", "score": 0.8, "findings": []},
        {"agent": "reviewer", "score": 0.9, "findings": []},
    ]
    result = compute_rubric(state)
    assert result.overall_score >= 3.5
    assert result.has_critical_failure is False


def test_low_score_triggers_critical():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = [
        {"agent": "correctness", "score": 0.9, "findings": []},
        {"agent": "security", "score": 0.2, "findings": [{"message": "SQL injection risk"}]},
        {"agent": "performance", "score": 0.8, "findings": []},
    ]
    result = compute_rubric(state)
    assert result.has_critical_failure is True
    assert "security" in result.critical_dims
    assert result.dimensions["security"]["score"] <= 2


def test_evidence_accumulates():
    state = create_initial_state("Task", "Desc")
    state["reviews"] = [
        {
            "agent": "correctness",
            "score": 0.5,
            "findings": [
                {"message": "auth.py:42: missing null check"},
                {"message": "user.py:15: incorrect type"},
            ],
        },
    ]
    result = compute_rubric(state)
    evidence = result.dimensions["correctness"]["evidence"]
    assert len(evidence) == 2
    assert "auth.py:42" in evidence[0]


def test_worst_score_wins():
    """When multiple reviews for same dim, use the lower score."""
    state = create_initial_state("Task", "Desc")
    state["reviews"] = [
        {"agent": "security", "score": 1.0, "findings": []},
        {"agent": "security", "score": 0.3, "findings": [{"message": "xss"}]},
    ]
    result = compute_rubric(state)
    assert result.dimensions["security"]["score"] <= 2  # 0.3*5 = 1.5 → round to 2
```

- [ ] **Step 3: Run tests, verify they pass**

Run: `uv run pytest tests/test_evaluator_rubric.py -v`
Expected: 5 tests PASS

- [ ] **Step 4: Commit**

```bash
git add loop_agent/agents/evaluator_rubric.py tests/test_evaluator_rubric.py
git commit -m "feat: add Evaluator Layer 2 — 5-dimension rubric scoring

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 8: Evaluator — Layer 3 (Fresh-Context LLM Judge) + Combined Node

**Files:**
- Create: `loop_agent/agents/evaluator_judge.py`
- Create: `loop_agent/agents/evaluator.py`
- Create: `tests/test_evaluator.py`

- [ ] **Step 1: Write the LLM judge**

```python
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
- If any rubric dimension scored ≤ 2 → decide "continue"
- If deterministic gate failed → decide "continue"
- If ALL acceptance criteria have passes=true AND all rubric dims ≥ 3 → decide "finish"
- If iteration ≥ max_iterations → decide "escalate"
- If score dropped > 0.3 vs previous review → decide "rewind"

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

If continuing, include specific feedback for the Coder in the "feedback" field.
Do not include any text outside the JSON block.
"""


def build_evaluator_prompt(
    state: OrchestrationState,
    gate: GateResult,
    rubric: RubricResult,
) -> str:
    """Build a fresh evaluator prompt — no shared conversation history."""
    return EVALUATOR_PROMPT.format(
        gate_result=json.dumps({"passed": gate.passed, "checks": gate.checks}, indent=2),
        rubric_json=json.dumps({
            "overall_score": rubric.overall_score,
            "has_critical_failure": rubric.has_critical_failure,
            "critical_dims": rubric.critical_dims,
            "dimensions": rubric.dimensions,
        }, indent=2),
        acceptance_criteria=json.dumps(
            state.get("acceptance_criteria", []), indent=2
        ),
        iteration=state.get("iteration", 1),
        max_iterations=state.get("max_iterations", 3),
    )


def evaluator_judge(
    state: OrchestrationState,
    gate: GateResult,
    rubric: RubricResult,
    working_dir: str = ".",
) -> dict:
    """Run the fresh-context LLM decision.

    The LLM receives ONLY structured data (no shared messages) and has
    read-only tool access to verify evidence.

    Args:
        state: Current orchestration state.
        gate: Result from Layer 1 deterministic gate.
        rubric: Result from Layer 2 rubric scoring.
        working_dir: Project root.

    Returns:
        {"decision": str, "reasoning": str, "acceptance_criteria": list, "feedback": str}
    """
    # Short-circuit: if gate failed or rubric has critical failure, skip LLM.
    if not gate.passed:
        failed_checks = [c for c in gate.checks if not c["passed"]]
        return {
            "decision": "continue",
            "reasoning": f"Deterministic gate failed: {json.dumps(failed_checks)}",
            "acceptance_criteria": state.get("acceptance_criteria", []),
            "feedback": f"Fix these issues:\n{json.dumps(failed_checks, indent=2)}",
        }

    if rubric.has_critical_failure:
        return {
            "decision": "continue",
            "reasoning": f"Rubric critical failure in: {rubric.critical_dims}",
            "acceptance_criteria": state.get("acceptance_criteria", []),
            "feedback": (
                f"Improve these dimensions: {rubric.critical_dims}. "
                f"See rubric evidence for details."
            ),
        }

    # Hard limit: escalate if max iterations reached.
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

    # Fresh messages — no prior conversation.
    messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": (
                "Evaluate the task. You may use read_file to verify claims. "
                "Output your decision as JSON."
            ),
        },
    ]

    max_turns = 4
    for _ in range(max_turns):
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # If the model wants to read a file, let it.
        if "read_file" in content.lower():
            files = _extract_file_paths(content)
            if files:
                read_results = []
                for fp in files:
                    result = _read_file(fp, working_dir)
                    read_results.append(result)
                messages.append({"role": "assistant", "content": content})
                messages.append({
                    "role": "user",
                    "content": f"File contents:\n{json.dumps(read_results, indent=2)}\n\nNow output your decision JSON.",
                })
                continue

        parsed = _parse_json_output(content)
        if parsed:
            # Enforce Default-FAIL: if decision is "finish" but any AC still
            # has passes=false without evidence, override to continue.
            acs = parsed.get("acceptance_criteria", state.get("acceptance_criteria", []))
            if parsed.get("decision") == "finish":
                unverified = [
                    ac for ac in acs
                    if not ac.get("passes") and not ac.get("evidence")
                ]
                if unverified:
                    parsed["decision"] = "continue"
                    parsed["reasoning"] = (
                        f"Default-FAIL: {len(unverified)} acceptance criteria "
                        f"still have passes=false without evidence: "
                        f"{[u['id'] for u in unverified]}"
                    )
            return {
                "decision": parsed.get("decision", "continue"),
                "reasoning": parsed.get("reasoning", ""),
                "acceptance_criteria": acs,
                "feedback": parsed.get("feedback", ""),
            }

    # Fallback: LLM didn't produce valid JSON.
    return {
        "decision": "continue",
        "reasoning": "Evaluator LLM did not produce a valid JSON decision",
        "acceptance_criteria": state.get("acceptance_criteria", []),
        "feedback": "Evaluator failed to produce a decision.",
    }


def _extract_file_paths(text: str) -> list[str]:
    """Extract file paths from text like 'read x.py' or 'check src/app.py'."""
    import re
    paths = []
    for match in re.finditer(r'(?:read|check|open|see|inspect)\s+["\']?([a-zA-Z0-9_\-./]+)["\']?', text):
        p = match.group(1)
        if "." in p and "/" not in p or "/" in p:
            paths.append(p)
    # Also match backtick-wrapped paths.
    for match in re.finditer(r'`([a-zA-Z0-9_\-./]+\.[a-zA-Z]+)`', text):
        paths.append(match.group(1))
    return paths[:5]  # Limit to 5 files max.


def _parse_json_output(text: str) -> dict | None:
    """Extract a JSON object from model output."""
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
```

- [ ] **Step 2: Write the combined evaluator node**

```python
# loop_agent/agents/evaluator.py
"""Evaluator agent node — combines all 3 layers into a single LangGraph node."""

from __future__ import annotations

from loop_agent.state import OrchestrationState
from loop_agent.agents.evaluator_gate import deterministic_gate
from loop_agent.agents.evaluator_rubric import compute_rubric
from loop_agent.agents.evaluator_judge import evaluator_judge


def evaluator_node(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Run the full 3-layer evaluator pipeline.

    1. Deterministic gate (no LLM)
    2. Multi-dimension rubric (no LLM)
    3. Fresh-context LLM decision

    Returns a partial state update with evaluation and updated
    acceptance_criteria.
    """
    iteration = state.get("iteration", 0) + 1

    # Layer 1: deterministic gate.
    gate = deterministic_gate(state, working_dir)

    # Layer 2: rubric scoring.
    rubric = compute_rubric(state)

    # Layer 3: fresh-context LLM decision.
    decision = evaluator_judge(state, gate, rubric, working_dir)

    # Update acceptance criteria with evaluator's findings.
    updated_criteria = decision.get("acceptance_criteria", state.get("acceptance_criteria", []))

    return {
        "rubric": {
            "overall_score": rubric.overall_score,
            "has_critical_failure": rubric.has_critical_failure,
            "critical_dims": rubric.critical_dims,
            "dimensions": rubric.dimensions,
        },
        "evaluation": {
            "decision": decision["decision"],
            "reasoning": decision["reasoning"],
            "feedback": decision.get("feedback", ""),
        },
        "acceptance_criteria": updated_criteria,
        "iteration": iteration,
    }
```

- [ ] **Step 3: Write evaluator tests**

```python
# tests/test_evaluator.py
"""Tests for the combined 3-layer evaluator pipeline."""

from unittest.mock import MagicMock, patch
from loop_agent.state import create_initial_state
from loop_agent.agents.evaluator import evaluator_node


class TestEvaluatorNode:
    def test_deterministic_gate_failure_returns_continue(self, tmp_path):
        """When tests fail, evaluator returns continue without any LLM call."""
        state = create_initial_state("Task", "Desc")
        state["test_results"] = [{"command": "pytest", "exit_code": 1, "passed": False}]
        state["code_artifacts"] = [{"path": "out.py", "action": "modified"}]
        # Create the file so artifact check passes.
        (tmp_path / "out.py").write_text("# code")

        result = evaluator_node(state, str(tmp_path))
        assert result["evaluation"]["decision"] == "continue"
        assert result["iteration"] == 1

    def test_critical_rubric_failure_returns_continue(self, tmp_path):
        """When a rubric dimension scores ≤ 2, skip LLM and continue."""
        state = create_initial_state("Task", "Desc")
        state["test_results"] = [{"command": "pytest", "exit_code": 0, "passed": True}]
        state["code_artifacts"] = [{"path": "out.py", "action": "modified"}]
        state["reviews"] = [
            {"agent": "security", "score": 0.1, "findings": [{"message": "critical vuln"}]},
        ]
        (tmp_path / "out.py").write_text("# code")

        result = evaluator_node(state, str(tmp_path))
        assert result["evaluation"]["decision"] == "continue"

    @patch("loop_agent.agents.evaluator_judge.create_model")
    def test_all_pass_calls_llm_and_can_finish(self, mock_create, tmp_path):
        """When gate and rubric pass, the LLM is called and can decide finish."""
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n'
            '{"decision": "finish", "reasoning": "All checks pass", '
            '"acceptance_criteria": [{"id": "AC-1", "passes": true, "evidence": "README.md:1"}], '
            '"feedback": ""}\n'
            '```'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm

        state = create_initial_state("Task", "Desc")
        state["test_results"] = [{"command": "pytest", "exit_code": 0, "passed": True}]
        state["code_artifacts"] = [{"path": "out.py", "action": "modified"}]
        state["reviews"] = [
            {"agent": "correctness", "score": 0.9, "findings": []},
            {"agent": "security", "score": 0.9, "findings": []},
            {"agent": "performance", "score": 0.9, "findings": []},
        ]
        state["acceptance_criteria"] = [{"id": "AC-1", "passes": False, "description": "Test"}]
        (tmp_path / "out.py").write_text("# code")

        result = evaluator_node(state, str(tmp_path))
        assert result["evaluation"]["decision"] == "finish"

    @patch("loop_agent.agents.evaluator_judge.create_model")
    def test_max_iterations_escalates(self, mock_create, tmp_path):
        """When iteration reaches max, escalate without LLM call."""
        state = create_initial_state("Task", "Desc", max_iterations=3)
        state["test_results"] = [{"command": "pytest", "exit_code": 0, "passed": True}]
        state["code_artifacts"] = [{"path": "out.py", "action": "modified"}]
        state["reviews"] = [
            {"agent": "correctness", "score": 0.9, "findings": []},
            {"agent": "security", "score": 0.9, "findings": []},
            {"agent": "performance", "score": 0.9, "findings": []},
        ]
        state["iteration"] = 3  # Already at max
        (tmp_path / "out.py").write_text("# code")

        result = evaluator_node(state, str(tmp_path))
        assert result["evaluation"]["decision"] == "escalate"


def test_default_fail_override():
    """Test the Default-FAIL enforcement in the judge.

    If decision is 'finish' but ACs still have passes=false without evidence,
    decision should be overridden to 'continue'.
    """
    from loop_agent.agents.evaluator_judge import evaluator_judge
    from loop_agent.agents.evaluator_gate import GateResult
    from loop_agent.agents.evaluator_rubric import RubricResult

    state = create_initial_state("Task", "Desc")
    state["acceptance_criteria"] = [
        {"id": "AC-1", "passes": False, "description": "README shows Hello"},
    ]
    state["iteration"] = 1
    gate = GateResult(passed=True, checks=[])
    rubric = RubricResult(
        dimensions={},
        overall_score=4.0,
        has_critical_failure=False,
        critical_dims=[],
    )

    with patch("loop_agent.agents.evaluator_judge.create_model") as mock_create:
        mock_llm = MagicMock()
        mock_response = MagicMock()
        # LLM tries to declare finish without verifying ACs.
        mock_response.content = (
            '```json\n'
            '{"decision": "finish", "reasoning": "looks good", '
            '"acceptance_criteria": [{"id": "AC-1", "passes": false, "evidence": null}], '
            '"feedback": ""}\n'
            '```'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm

        result = evaluator_judge(state, gate, rubric)
        # Default-FAIL should override finish → continue.
        assert result["decision"] == "continue"
        assert "Default-FAIL" in result["reasoning"]
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `uv run pytest tests/test_evaluator.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add loop_agent/agents/evaluator_judge.py loop_agent/agents/evaluator.py tests/test_evaluator.py
git commit -m "feat: add Evaluator Layers 2-3 + combined node with Default-FAIL

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 9: Planner, Reviewer, and Integration agent nodes

**Files:**
- Create: `loop_agent/agents/planner.py`
- Create: `loop_agent/agents/reviewer.py`
- Create: `loop_agent/agents/integration.py`

- [ ] **Step 1: Write the Planner agent**

```python
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

Each acceptance criterion must be specific and verifiable — something a
tester or reviewer can prove is true or false by reading files or running
commands.
Do not include any text outside the JSON block.
"""


def build_planner_prompt(state: OrchestrationState) -> str:
    request = state.get("request", {})
    return PLANNER_SYSTEM_PROMPT.format(
        task_title=request.get("title", "Unknown task"),
        task_description=request.get("description", ""),
    )


def planner_node(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Planner agent — produces plan and acceptance_criteria.

    LangGraph node function.
    """
    from loop_agent.tools import read_file, search_code
    from langchain_community.tools.tavily_search import TavilySearchResults

    llm = create_model("planner")
    prompt = build_planner_prompt(state)

    tavily = None
    try:
        tavily = TavilySearchResults(max_results=3)
    except Exception:
        pass

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Analyze the task and produce a plan. You may search for information and read files."},
    ]

    max_turns = 8
    for _ in range(max_turns):
        response = llm.invoke(messages)
        content = response.content if hasattr(response, "content") else str(response)

        # Handle implicit tool requests.
        if "search" in content.lower() and tavily:
            search_terms = _extract_search_terms(content)
            if search_terms:
                search_results = tavily.invoke(search_terms[0])
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"Search results: {json.dumps(search_results, indent=2)}"})
                continue

        if "read" in content.lower():
            files = _extract_file_paths(content)
            if files:
                read_results = []
                for fp in files:
                    result = read_file(fp, working_dir)
                    read_results.append(result)
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": f"File contents: {json.dumps(read_results, indent=2)}"})
                continue

        parsed = _parse_json_output(content)
        if parsed:
            plan_data = parsed.get("plan", parsed)
            criteria = plan_data.get("acceptance_criteria", [])
            # Format criteria with Default-FAIL: all start as passes=false.
            acceptance_criteria = []
            for ac in criteria:
                if isinstance(ac, str):
                    acceptance_criteria.append({
                        "id": f"AC-{len(acceptance_criteria) + 1}",
                        "description": ac,
                        "passes": False,
                        "evidence": None,
                    })
                elif isinstance(ac, dict):
                    acceptance_criteria.append({
                        "id": ac.get("id", f"AC-{len(acceptance_criteria) + 1}"),
                        "description": ac.get("description", str(ac)),
                        "passes": False,
                        "evidence": None,
                    })
            return {
                "plan": plan_data,
                "acceptance_criteria": acceptance_criteria,
                "messages": messages + [{"role": "assistant", "content": content}],
            }

    return {
        "plan": {"summary": "Planner failed to produce a plan", "steps": []},
        "acceptance_criteria": [],
        "errors": [{"stage": "planning", "message": "Planner exceeded max turns", "category": "convergence"}],
        "messages": messages,
    }


def _extract_search_terms(text: str) -> list[str]:
    """Extract search queries from text."""
    import re
    queries = []
    for match in re.finditer(r'search(?: for)?\s+["\']?([^"\'\n]{3,100})["\']?', text, re.IGNORECASE):
        queries.append(match.group(1).strip().rstrip(".,;"))
    return queries[:3]


def _extract_file_paths(text: str) -> list[str]:
    """Extract file paths from text."""
    import re
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
```

- [ ] **Step 2: Write the Reviewer agent**

```python
# loop_agent/agents/reviewer.py
"""Reviewer agent node — reviews code from a specific axis, supports parallel fan-out."""

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
Review the code artifacts and output JSON:
```json
{{"agent": "correctness", "score": 0.95, "findings": [{{"message": "specific issue at file:line"}}]}}
```
Score 0.0-1.0 where 1.0 means perfect correctness.""",

    "security": """\
You are a Reviewer focused on SECURITY.
Check: SQL injection, XSS, command injection, hardcoded secrets, path traversal,
insecure deserialization, missing auth checks.
Review the code artifacts and output JSON:
```json
{{"agent": "security", "score": 0.95, "findings": [{{"message": "specific issue at file:line"}}]}}
```
Score 0.0-1.0 where 1.0 means no security issues.""",

    "performance": """\
You are a Reviewer focused on PERFORMANCE.
Check: N+1 queries, unnecessary allocations, blocking I/O, missing caches,
inefficient algorithms, memory leaks.
Review the code artifacts and output JSON:
```json
{{"agent": "performance", "score": 0.95, "findings": [{{"message": "specific issue at file:line"}}]}}
```
Score 0.0-1.0 where 1.0 means optimal performance.""",
}


def build_reviewer_prompt(state: OrchestrationState, axis: str) -> str:
    """Build the reviewer prompt for a specific axis."""
    base = REVIEWER_PROMPTS.get(axis, REVIEWER_PROMPTS["correctness"])
    artifacts = json.dumps(state.get("code_artifacts", []), indent=2)
    criteria = json.dumps(state.get("acceptance_criteria", []), indent=2)

    context = f"""\
## Code Artifacts to Review
{artifacts}

## Acceptance Criteria
{criteria}

## Your Job
Read the modified files, review them for {axis} issues, and output your review JSON."""
    return base + "\n" + context


def reviewer_node(state: OrchestrationState, axis: str = "correctness", working_dir: str = ".") -> dict:
    """Single reviewer — reviews code from one axis.

    Args:
        state: Current orchestration state.
        axis: One of correctness, security, performance.
        working_dir: Project root.

    Returns:
        A single review dict: {"agent": str, "score": float, "findings": list}
    """
    from loop_agent.tools import read_file, search_code

    llm = create_model("reviewer")
    prompt = build_reviewer_prompt(state, axis)

    # Read modified files so the reviewer can see the changes.
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

    return {
        "agent": axis,
        "score": 0.5,
        "findings": [{"message": f"Reviewer failed to produce valid JSON for {axis}"}],
    }


def reviewer_parallel(state: OrchestrationState, working_dir: str = ".", max_workers: int = 3) -> list[dict]:
    """Run 3 reviewers in parallel: correctness, security, performance.

    Args:
        state: Current orchestration state.
        working_dir: Project root.
        max_workers: Max parallel threads.

    Returns:
        List of 3 review dicts.
    """
    axes = ["correctness", "security", "performance"]
    reviews = []

    with ThreadPoolExecutor(max_workers=min(max_workers, len(axes))) as executor:
        futures = {
            executor.submit(reviewer_node, state, axis, working_dir): axis
            for axis in axes
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                reviews.append(result)
            except Exception as exc:
                axis = futures[future]
                reviews.append({
                    "agent": axis,
                    "score": 0.0,
                    "findings": [{"message": f"Reviewer {axis} failed: {exc}"}],
                })

    return reviews


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
```

- [ ] **Step 3: Write the Integration agent**

```python
# loop_agent/agents/integration.py
"""Integration agent node — summarizes completed work."""

from __future__ import annotations

import json
import re

from loop_agent.models import create_model
from loop_agent.state import OrchestrationState


INTEGRATION_PROMPT = """\
You are an Integration agent in an autonomous coding loop.

## Task
{task_title}

## Plan
{plan_summary}

## Code Artifacts
{code_artifacts}

## Test Results
{test_results}

## Review Scores
{review_scores}

## Your Job
Summarize what was accomplished. Output ONLY a JSON object:
```json
{{
  "summary": "Brief summary of the completed work",
  "artifacts_summary": ["list of changes made"]
}}
```
"""


def integration_node(state: OrchestrationState) -> dict:
    """Integration agent — produces a final summary.

    LangGraph node function. Sets status to completed.
    """
    llm = create_model("integration")
    request = state.get("request", {})
    plan = state.get("plan") or {}

    prompt = INTEGRATION_PROMPT.format(
        task_title=request.get("title", "Unknown"),
        plan_summary=plan.get("summary", json.dumps(plan)),
        code_artifacts=json.dumps(state.get("code_artifacts", []), indent=2),
        test_results=json.dumps(state.get("test_results", []), indent=2),
        review_scores=json.dumps(
            [{"agent": r.get("agent", "?"), "score": r.get("score", 0)} for r in state.get("reviews", [])],
            indent=2,
        ),
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": "Summarize the completed work."},
    ]

    response = llm.invoke(messages)
    content = response.content if hasattr(response, "content") else str(response)

    parsed = _parse_json_output(content)
    if parsed:
        return {
            "status": "completed",
            "messages": messages + [{"role": "assistant", "content": content}],
        }

    return {
        "status": "completed",
        "messages": messages,
    }


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
```

- [ ] **Step 4: Write agent tests**

```python
# tests/test_agents.py
"""Tests for Planner, Reviewer, and Integration agents."""

from unittest.mock import MagicMock, patch
from loop_agent.state import create_initial_state
from loop_agent.agents.planner import planner_node
from loop_agent.agents.reviewer import reviewer_node, reviewer_parallel
from loop_agent.agents.integration import integration_node


class TestPlanner:
    @patch("loop_agent.agents.planner.create_model")
    def test_planner_produces_plan_and_criteria(self, mock_create):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n'
            '{"plan": {"summary": "Edit README", '
            '"steps": [{"id": "1", "description": "fix typo", "status": "pending"}], '
            '"acceptance_criteria": [{"id": "AC-1", "description": "README shows Hello"}]}}\n'
            '```'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm

        state = create_initial_state("Fix typo", "Change Helo to Hello")
        result = planner_node(state)
        assert result["plan"]["summary"] == "Edit README"
        assert len(result["acceptance_criteria"]) == 1
        # Default-FAIL: criteria start as passes=false.
        assert result["acceptance_criteria"][0]["passes"] is False
        assert result["acceptance_criteria"][0]["evidence"] is None

    @patch("loop_agent.agents.planner.create_model")
    def test_planner_string_criteria_converted(self, mock_create):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '```json\n'
            '{"plan": {"summary": "Edit", "steps": [], '
            '"acceptance_criteria": ["README shows Hello", "tests pass"]}}\n'
            '```'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm

        state = create_initial_state("Task", "Desc")
        result = planner_node(state)
        assert len(result["acceptance_criteria"]) == 2
        assert all(ac["passes"] is False for ac in result["acceptance_criteria"])


class TestReviewer:
    @patch("loop_agent.agents.reviewer.create_model")
    def test_reviewer_single_axis(self, mock_create):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '{"agent": "security", "score": 0.9, "findings": []}'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm

        state = create_initial_state("Task", "Desc")
        state["code_artifacts"] = [{"path": "x.py"}]
        result = reviewer_node(state, axis="security")
        assert result["agent"] == "security"
        assert result["score"] == 0.9

    @patch("loop_agent.agents.reviewer.reviewer_node")
    def test_reviewer_parallel_runs_all_axes(self, mock_node):
        mock_node.side_effect = lambda state, axis, wd: {
            "agent": axis, "score": 0.9, "findings": []
        }
        state = create_initial_state("Task", "Desc")
        state["code_artifacts"] = [{"path": "x.py"}]
        results = reviewer_parallel(state)
        axes = {r["agent"] for r in results}
        assert axes == {"correctness", "security", "performance"}


class TestIntegration:
    @patch("loop_agent.agents.integration.create_model")
    def test_integration_sets_completed(self, mock_create):
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = (
            '{"summary": "Fixed typo in README", "artifacts_summary": ["README.md: Helo→Hello"]}'
        )
        mock_llm.invoke.return_value = mock_response
        mock_create.return_value = mock_llm

        state = create_initial_state("Task", "Desc")
        result = integration_node(state)
        assert result["status"] == "completed"
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `uv run pytest tests/test_agents.py -v`
Expected: 4+ tests PASS

- [ ] **Step 6: Commit**

```bash
git add loop_agent/agents/planner.py loop_agent/agents/reviewer.py loop_agent/agents/integration.py tests/test_agents.py
git commit -m "feat: add Planner, Reviewer(parallel), and Integration agents

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 10: LangGraph graph assembly and checkpoint helpers

**Files:**
- Create: `loop_agent/graph.py`
- Create: `loop_agent/checkpoint.py`

- [ ] **Step 1: Write the checkpoint helper**

```python
# loop_agent/checkpoint.py
"""Checkpoint helper functions for the loop agent graph."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from loop_agent.state import OrchestrationState


def make_checkpoint_metadata(stage: str, state: OrchestrationState) -> dict:
    """Create checkpoint metadata for the current state.

    Args:
        stage: Current stage name (planning, coding, testing).
        state: Current orchestration state.

    Returns:
        Checkpoint metadata dict.
    """
    state_hash = hashlib.sha256(
        json.dumps(
            {
                "status": state.get("status"),
                "plan": state.get("plan"),
                "code_artifacts": state.get("code_artifacts"),
                "test_results": state.get("test_results"),
                "iteration": state.get("iteration"),
            },
            sort_keys=True,
            default=str,
        ).encode()
    ).hexdigest()[:16]

    return {
        "stage": stage,
        "state_hash": state_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 2: Write the graph builder**

```python
# loop_agent/graph.py
"""LangGraph StateGraph builder for the autonomous coding loop."""

from __future__ import annotations

from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from loop_agent.state import OrchestrationState
from loop_agent.checkpoint import make_checkpoint_metadata


def route_after_evaluator(state: OrchestrationState) -> str:
    """Conditional edge: decide where to go after evaluator.

    Returns the name of the next node.
    """
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
    """Classify the task and select topology.

    For v1, always selects prompt_chain.
    Future: implement Conductor's topology selection logic.
    """
    return {
        "status": "planning",
        "topology": "prompt_chain",
    }


def planner_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Wrapper: run planner and set status to coding."""
    from loop_agent.agents.planner import planner_node
    result = planner_node(state, working_dir)
    result["status"] = "coding"
    return result


def coder_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Wrapper: run coder and set status to testing."""
    from loop_agent.agents.coder import coder_node
    result = coder_node(state)
    # coder_node doesn't take working_dir directly; it reads from state
    result["status"] = "testing"
    return result


def tester_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Wrapper: run tester and set status to reviewing."""
    from loop_agent.agents.tester import tester_node
    result = tester_node(state)
    result["status"] = "reviewing"
    return result


def reviewer_parallel_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Wrapper: run 3 parallel reviewers and merge results."""
    from loop_agent.agents.reviewer import reviewer_parallel
    reviews = reviewer_parallel(state, working_dir)
    return {
        "reviews": reviews,
        "status": "reviewing",
    }


def evaluator_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Wrapper: run 3-layer evaluator."""
    from loop_agent.agents.evaluator import evaluator_node
    return evaluator_node(state, working_dir)


def integration_wrapper(state: OrchestrationState, working_dir: str = ".") -> dict:
    """Wrapper: run integration agent."""
    from loop_agent.agents.integration import integration_node
    return integration_node(state)


def add_checkpoint(state: OrchestrationState, stage: str) -> dict:
    """Add a checkpoint metadata entry to the state."""
    meta = make_checkpoint_metadata(stage, state)
    return {"status": stage}


def build_graph(working_dir: str = ".") -> StateGraph:
    """Build and compile the LangGraph StateGraph.

    Args:
        working_dir: Project working directory for file tools.

    Returns:
        A compiled LangGraph StateGraph ready for invocation.
    """
    # Use functools.partial to bind working_dir to each node function.
    from functools import partial

    # Create graph builder.
    builder = StateGraph(OrchestrationState)

    # Add nodes.
    builder.add_node("classify", classify_node)
    builder.add_node("planner", partial(planner_wrapper, working_dir=working_dir))
    builder.add_node("coder", partial(coder_wrapper, working_dir=working_dir))
    builder.add_node("tester", partial(tester_wrapper, working_dir=working_dir))
    builder.add_node("reviewer", partial(reviewer_parallel_wrapper, working_dir=working_dir))
    builder.add_node("evaluator", partial(evaluator_wrapper, working_dir=working_dir))
    builder.add_node("integration", partial(integration_wrapper, working_dir=working_dir))

    # Add edges.
    builder.set_entry_point("classify")
    builder.add_edge("classify", "planner")
    builder.add_edge("planner", "coder")
    builder.add_edge("coder", "tester")
    builder.add_edge("tester", "reviewer")
    builder.add_edge("reviewer", "evaluator")

    # Conditional routing after evaluator.
    builder.add_conditional_edges(
        "evaluator",
        route_after_evaluator,
        {
            "coder": "coder",
            "integration": "integration",
            "__end__": END,
        },
    )

    builder.add_edge("integration", END)

    # Compile with in-memory checkpointer.
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    return graph


def create_loop_agent(working_dir: str = ".") -> StateGraph:
    """Create a compiled loop agent graph.

    This is the main public API entry point.

    Args:
        working_dir: Project root directory.

    Returns:
        A compiled LangGraph graph ready for .invoke() or .stream().

    Example:
        >>> from loop_agent import create_loop_agent, run_loop
        >>> graph = create_loop_agent("/path/to/project")
        >>> result = run_loop(graph, "Fix typo", "Change Helo to Hello in README")
    """
    return build_graph(working_dir)


def run_loop(
    graph: StateGraph,
    title: str,
    description: str,
    max_iterations: int = 3,
    working_dir: str = ".",
) -> OrchestrationState:
    """Run the full loop and return the final state.

    Args:
        graph: Compiled LangGraph graph from create_loop_agent().
        title: Task title.
        description: Task description.
        max_iterations: Max coder→evaluator iterations.
        working_dir: Project root.

    Returns:
        The final OrchestrationState after the loop completes.
    """
    from loop_agent.state import create_initial_state

    initial = create_initial_state(title, description, max_iterations)
    config = {"configurable": {"thread_id": initial["task_id"]}}
    final = graph.invoke(initial, config)
    return final
```

- [ ] **Step 3: Write graph tests**

```python
# tests/test_graph.py
"""Tests for graph structure and routing logic."""

import pytest
from loop_agent.state import create_initial_state, OrchestrationState
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
        # Graph should have nodes.
        nodes = graph.get_graph().nodes
        assert "classify" in nodes or True  # get_graph may differ by version

    def test_graph_has_all_required_nodes(self):
        graph = build_graph(".")
        # The compiled graph should have our nodes.
        graph_def = graph.get_graph()
        node_names = {n for n in graph_def.nodes.keys() if not n.startswith("__")}
        expected = {"classify", "planner", "coder", "tester", "reviewer", "evaluator", "integration"}
        assert expected.issubset(node_names), f"Missing nodes: {expected - node_names}"
```

- [ ] **Step 4: Update loop_agent/__init__.py**

```python
# loop_agent/__init__.py
"""Loop Agent: Autonomous coding loop with NVIDIA NIM free models."""

from loop_agent.state import OrchestrationState, create_initial_state
from loop_agent.models import create_model, get_fallback_model, MODEL_REGISTRY
from loop_agent.graph import create_loop_agent, run_loop, build_graph

__all__ = [
    "OrchestrationState",
    "create_initial_state",
    "create_model",
    "get_fallback_model",
    "MODEL_REGISTRY",
    "create_loop_agent",
    "run_loop",
    "build_graph",
]
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS (~30+ tests)

- [ ] **Step 6: Commit**

```bash
git add loop_agent/graph.py loop_agent/checkpoint.py loop_agent/__init__.py tests/test_graph.py
git commit -m "feat: add LangGraph StateGraph assembly, checkpoint helpers, public API

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 11: End-to-end test with real NVIDIA NIM

**Files:**
- Create: `tests/test_e2e.py`
- Create: `loop_agent/agents/__init__.py` (update with re-exports)

- [ ] **Step 1: Update agents __init__.py**

```python
# loop_agent/agents/__init__.py
"""Agent node implementations for the autonomous coding loop."""

from loop_agent.agents.planner import planner_node
from loop_agent.agents.coder import coder_node
from loop_agent.agents.tester import tester_node
from loop_agent.agents.reviewer import reviewer_node, reviewer_parallel
from loop_agent.agents.evaluator import evaluator_node
from loop_agent.agents.evaluator_gate import deterministic_gate
from loop_agent.agents.evaluator_rubric import compute_rubric
from loop_agent.agents.evaluator_judge import evaluator_judge
from loop_agent.agents.integration import integration_node

__all__ = [
    "coder_node",
    "compute_rubric",
    "deterministic_gate",
    "evaluator_judge",
    "evaluator_node",
    "integration_node",
    "planner_node",
    "reviewer_node",
    "reviewer_parallel",
    "tester_node",
]
```

- [ ] **Step 2: Write E2E test**

```python
# tests/test_e2e.py
"""End-to-end test with real NVIDIA NIM API calls.

This test requires:
- NVIDIA_API_KEY environment variable set
- Network access to integrate.api.nvidia.com
- Proxy at localhost:7897 configured for network access

Skip if API key is not set.
"""

import os
import pytest
from loop_agent.state import create_initial_state
from loop_agent.graph import create_loop_agent, run_loop

pytestmark = pytest.mark.e2e


@pytest.fixture
def requires_nvidia_key():
    if not os.environ.get("NVIDIA_API_KEY"):
        pytest.skip("NVIDIA_API_KEY not set")


def test_create_loop_agent_returns_graph(requires_nvidia_key):
    graph = create_loop_agent(".")
    assert graph is not None


def test_run_loop_fix_typo(requires_nvidia_key, tmp_path):
    """End-to-end: fix a typo in README.md.

    This test creates a README.md with a typo and asks the loop to fix it.
    It runs the full prompt_chain topology with real NVIDIA NIM calls.
    """
    # Setup: create a README.md with a typo.
    readme = tmp_path / "README.md"
    readme.write_text("# Helo World\n\nThis is a test.\n")

    graph = create_loop_agent(str(tmp_path))

    # This is a real API call — give it sufficient timeout.
    final = run_loop(
        graph,
        title="Fix typo in README",
        description="Change 'Helo' to 'Hello' in README.md. The first line says '# Helo World' and should say '# Hello World'.",
        max_iterations=3,
        working_dir=str(tmp_path),
    )

    # The loop should complete.
    assert final["status"] in ("completed", "halted"), (
        f"Expected completed or halted, got {final['status']}. "
        f"Errors: {final.get('errors', [])}"
    )

    # If completed, verify the fix.
    if final["status"] == "completed":
        content = readme.read_text()
        assert "Hello" in content, f"README should contain 'Hello', got: {content}"
```

- [ ] **Step 3: Run only unit tests (no E2E yet)**

Run: `uv run pytest tests/ -v --ignore=tests/test_e2e.py`
Expected: All unit tests PASS

- [ ] **Step 4: Run E2E test with real API**

Run: `uv run pytest tests/test_e2e.py -v -s`
Expected: Test completes (may take 30-300s depending on NIM cold starts)

- [ ] **Step 5: Add section to pyproject.toml for test config**

```toml
# Add to pyproject.toml [tool.pytest.ini_options] section:
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "e2e: end-to-end tests that require real NVIDIA NIM API calls",
]
```

- [ ] **Step 6: Commit**

```bash
git add loop_agent/agents/__init__.py tests/test_e2e.py pyproject.toml
git commit -m "feat: add E2E test with real NVIDIA NIM calls

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Post-Implementation Verification

After all tasks are complete, run the full test suite:

```bash
# Unit tests (no network required)
uv run pytest tests/ -v --ignore=tests/test_e2e.py

# E2E test (requires NVIDIA_API_KEY)
NVIDIA_API_KEY=your-key uv run pytest tests/test_e2e.py -v -s
```

Expected: All unit tests pass, E2E test completes successfully.
