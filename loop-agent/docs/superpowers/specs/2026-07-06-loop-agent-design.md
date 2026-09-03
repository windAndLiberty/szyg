# Loop Agent: Autonomous Coding Loop with NVIDIA NIM Free Models

**Status**: Approved
**Date**: 2026-07-06
**Source**: Conductor prototype (dolphin) + deepagents patterns + NVIDIA NIM stress test

## 1. Overview

Build a self-correcting autonomous coding loop that orchestrates Planner, Coder,
Tester, Reviewer, and Evaluator agents, each backed by a different NVIDIA NIM
free-endpoint model, using LangGraph StateGraph as the infrastructure.

### 1.1 Goals

- Run a `prompt_chain` topology: `planner → coder → tester → reviewer(3×parallel) → evaluator → integration → completed`
- Evaluator closes the loop by deciding `continue` (back to coder), `rewind` (restore checkpoint), `finish`, or `escalate` (halt)
- Every agent is a LangGraph node backed by a ChatNVIDIA model chosen for its role
- Tools: read_file, write_file, run_shell, search_code, tavily_search
- Budget guard: max_iterations halts with `halted` status

### 1.2 Non-Goals

- No other topologies (routing, orchestrator_workers, autonomous — future work)
- No git operations or PR creation
- No persistent database beyond LangGraph's checkpointer
- No web server or API

## 2. Architecture (Approach A: LangGraph StateGraph)

```
START → classify → planner → coder → tester → reviewer_parallel(×3) → evaluator
                                                                       ├─ finish    → integration → completed
                                                                       ├─ continue  → coder (loop)
                                                                       ├─ rewind    → restore checkpoint → coder
                                                                       └─ escalate  → halted
```

- **Graph engine**: LangGraph `StateGraph` with `SqliteSaver` checkpointer
- **Agent nodes**: Each is a Python function that calls `ChatNVIDIA` with role-specific system prompt and tools
- **Conditional edges**: `evaluator` output routes to `coder`, `integration`, or `halted`
- **Parallelism**: `reviewer_parallel` fans out 3 reviewers (correctness, security, performance) via `ThreadPoolExecutor`

## 3. OrchestrationState

```python
class OrchestrationState(TypedDict):
    task_id: str
    request: dict          # {"title": "...", "description": "..."}
    status: str            # pending|planning|coding|testing|reviewing|integrating|completed|failed|halted
    topology: str          # "prompt_chain"

    # Agent outputs
    plan: dict | None
    code_artifacts: list[dict]
    test_results: list[dict]
    reviews: list[dict]
    rubric: dict | None            # 5-dimension scoring output from evaluator
    evaluation: dict | None

    # Acceptance criteria (Default-FAIL contract)
    acceptance_criteria: list[dict]  # [{"id": str, "passes": bool, "evidence": str|null}]

    # Control
    iteration: int
    max_iterations: int
    errors: list[dict]

    # LangGraph messages
    messages: list
```

## 4. Model-to-Role Mapping

Based on the 10-minute stress test (2026-07-06, 15 models, 4 rounds):

| Role | Model | Avg Time | TTFT | TPS | Why |
|------|-------|----------|------|-----|-----|
| Planner | `nvidia/nemotron-3-super-120b-a12b` | 2.3s | 1.3s | 40 | Strong reasoning, fast |
| Coder | `deepseek-ai/deepseek-v4-pro` | 7.6s | 3.9s | 3.3 | Best coding capability |
| Tester | `mistralai/mistral-small-4-119b-2603` | 1.3s | 0.6s | 107 | Fast execution |
| Reviewer | `nvidia/nemotron-3-super-120b-a12b` | 2.3s | 1.3s | 40 | 3 parallel instances |
| Evaluator | `google/diffusiongemma-26b-a4b-it` | 1.0s | 1.0s | 4004 | Fastest decision node |
| Integration | `mistralai/mistral-medium-3.5-128b` | 1.9s | 0.6s | 58 | Good summarization |

Each agent node configures `ChatNVIDIA(timeout=180)` for cold starts.

## 5. Agent Nodes

### 5.1 Planner

- **Tools**: read_file, search_code, tavily_search
- **System**: Analyze task, search for background, read project files, produce structured plan
- **Output**: `{"plan": {"summary": "...", "steps": [...], "acceptance_criteria": [...]}}`

### 5.2 Coder

- **Tools**: read_file, write_file, run_shell
- **System**: Read target files, make edits, run lint/type-check
- **Output**: `{"code_artifacts": [{"path": "...", "action": "modified|created", "diff": "..."}]}`
- **On re-entry** (continue from evaluator): receives previous test failures and review findings as feedback

### 5.3 Tester

- **Tools**: run_shell, read_file
- **System**: Execute test commands, capture results
- **Output**: `{"test_results": [{"command": "...", "exit_code": N, "passed": bool, "stdout": "..."}]}`

### 5.4 Reviewer (3 parallel instances)

- **Tools**: read_file, search_code, tavily_search
- **Instances**: correctness, security, performance — each with an axis-specific system prompt
- **Output**: `{"reviews": [{"agent": "reviewer", "score": 0.0-1.0, "findings": [...]}]}`
- **Implementation**: `ThreadPoolExecutor` with 3 workers, results merged into `state["reviews"]`

### 5.5 Evaluator (3-Layer Architecture)

The Evaluator is the core differentiator — a **3-layer decision pipeline** that
combines deterministic checks, multi-dimension rubric scoring, and fresh-context
LLM judgement.

```
                ┌──────────────────────────────────────┐
                │       Evaluator Pipeline              │
                │                                      │
                │  Layer 1: Deterministic Gate          │
                │  test exit code → lint → type check   │
                │  hardware PASS/FAIL → no LLM cost     │
                │         │ FAIL → continue             │
                │         ▼ PASS                        │
                │                                      │
                │  Layer 2: Multi-Dimension Rubric      │
                │  5 orthogonal dims, each 1-5 scale    │
                │  Computed from test_results + reviews │
                │         ▼                             │
                │                                      │
                │  Layer 3: Fresh-Context LLM Decision  │
                │  Default-FAIL contract enforced        │
                │  New context window (no shared msgs)   │
                │  → finish / continue / rewind / escalate│
                └──────────────────────────────────────┘
```

#### Layer 1: Deterministic Gate

No LLM call. Evaluated before any model inference. If any check fails,
the evaluator returns `continue` immediately, saving one LLM call per loop.

```python
CHECKS = [
    ("exit_code",     all test_results exit_code == 0),
    ("artifacts_exist",  all promised code_artifacts paths exist on disk),
    ("no_regression",    code_artifacts not empty after previous iteration),
]
```

#### Layer 2: Multi-Dimension Rubric

5 orthogonal scoring dimensions, inspired by AdaRubric and lazycoder patterns.
Prevents a high overall score from masking a specific failure.

| Dimension | Weight | Evaluated By | Criteria |
|-----------|--------|-------------|----------|
| Correctness | 30% | Reviewer (correctness) | Meets acceptance criteria, handles edge cases |
| Security | 20% | Reviewer (security) | Injections, permissions, secrets exposure |
| Design | 20% | Reviewer (design) | Follows project patterns, appropriate abstraction |
| Performance | 15% | Reviewer (performance) | Unnecessary computation, N+1, memory |
| Maintainability | 15% | Reviewer (cleanliness) | Naming, comments, complexity, test coverage |

Each dimension is scored 1-5 with supporting evidence (file:line citations).
The final rubric includes a **dimension-aware filter**: if any single dimension
scores ≤ 2, the evaluator must return `continue` regardless of other scores.

#### Layer 3: Fresh-Context LLM Decision

The decision LLM call uses a **new message list**, not the shared conversation
history. It receives only structured data:

```python
fresh_input = {
    "deterministic_gate": {"passed": True},
    "rubric": {
        "correctness": {"score": 4, "evidence": ["auth.py:42: handles empty input"]},
        "security":    {"score": 5, "evidence": [...]},
        "design":      {"score": 3, "evidence": ["user.py:15: should use BaseModel"]},
        "performance": {"score": 4, "evidence": [...]},
        "maintainability": {"score": 4, "evidence": [...]},
    },
    "acceptance_criteria": [
        {"id": "AC-1", "passes": False, "description": "README shows Hello"},
        {"id": "AC-2", "passes": False, "description": "All tests pass"},
    ],
    "iteration": 2,
    "max_iterations": 3,
    "feedback_from_previous": "Security reviewer found SQL injection risk",
}
```

**Decision rules**:

| Condition | Decision | Action |
|-----------|----------|--------|
| Deterministic gate FAIL | `continue` | → coder with failure reason |
| Any rubric dimension ≤ 2 | `continue` | → coder with dimension feedback |
| All ACs pass, all dims ≥ 3, gate pass | `finish` | → integration |
| Score dropped > 0.3 vs previous review | `rewind` | → restore checkpoint, then coder |
| Iteration ≥ max_iterations | `escalate` | → halted |
| Any other unrecoverable error | `escalate` | → halted |

**Tool access**: The evaluator LLM has Read-only tools (no Write, no Edit, no
Run). It can inspect files to verify evidence claims but cannot modify state.
This enforces the Default-FAIL contract — success must be observed, not declared.

**Model**: `google/diffusiongemma-26b-a4b-it` (1.0s avg, fastest in the fleet).
Since the evaluator receives pre-structured data, it does not need a strong
model — it needs a fast, reliable one.

### 5.6 Default-FAIL Contract

The Default-FAIL contract prevents the agent from declaring success without
verifiable evidence. Every acceptance criterion starts `passes: false`. The
Evaluator can only set `passes: true` after observing supporting evidence
through Read-only tools.

#### State Representation

```json
{
  "acceptance_criteria": [
    {
      "id": "AC-1",
      "description": "README.md shows 'Hello' instead of 'Helo'",
      "passes": false,
      "evidence": null
    }
  ]
}
```

#### Enforcement

1. **Planner** creates the criteria from the task request
2. **Each AC starts as `passes: false`** — no agent can pre-mark anything
3. **Evaluator LLM has only Read tools** — cannot write to state
4. **Evaluator's output includes `acceptance_criteria` with updated `passes` and `evidence`**
5. **Post-evaluator hook validates**: if `decision == "finish"` but any AC has
   `passes: false` without evidence, override decision to `continue`

This makes "done" structural rather than aspirational.

### 5.7 Integration

- **Tools**: read_file
- **System**: Summarize completed work
- **Output**: `{"summary": "...", "artifacts_summary": [...]}`

## 6. Graph Construction

### 6.1 Nodes

```
classify_node → planner_node → coder_node → tester_node
→ reviewer_parallel_node → evaluator_node
→ integration_node | halted_node | completed_node
```

### 6.2 Conditional Edge

```python
def route_after_evaluator(state: OrchestrationState) -> str:
    decision = state["evaluation"]["decision"]
    if decision == "finish":
        return "integration"
    elif decision == "continue":
        if state["iteration"] >= state["max_iterations"]:
            return "halted"
        return "coder"
    elif decision == "rewind":
        # LangGraph restores checkpoint internally
        return "coder"
    else:  # escalate
        return "halted"
```

### 6.3 Checkpoints

LangGraph `SqliteSaver` auto-checkpoints after each node. Explicit checkpoint metadata is saved after:
- `planner` → `{"stage": "planning"}`
- `coder` → `{"stage": "coding"}`
- `tester` → `{"stage": "testing"}`

Rewind: Use LangGraph's `graph.get_state(config)` to fetch the checkpoint prior to
the current iteration. The evaluator node returns `Command(goto="coder", update=checkpointed_values)`
to restore state and re-enter the coding phase with the previous plan and
code artifacts intact. An error entry records the rewind reason.

## 7. Tool Definitions

```python
TOOLS = {
    "read_file": ReadFileTool(),       # path → content
    "write_file": WriteFileTool(),     # path, content → confirmation
    "run_shell": RunShellTool(),       # command → stdout, stderr, exit_code
    "search_code": SearchCodeTool(),   # pattern, path → list[Match]
    "tavily_search": TavilySearchResults(max_results=3),
}
```

- All file tools are scoped to the project working directory (no `..` traversal)
- `run_shell` has a command allow-list: `pytest`, `python`, `grep`, `ruff`, `mypy`, `cat`, `ls`
- `run_shell` timeout: 30s per command

## 8. Error Handling

| Error Type | Behavior |
|-----------|----------|
| Agent LLM call timeout | Retry once, then mark agent output with error, evaluator decides |
| Agent returns unparseable JSON | Retry with stricter prompt, then mark error |
| Tool execution failure | Return error to agent, agent decides retry or report failure |
| max_iterations reached | Force `escalate` → `halted` |
| NVIDIA NIM model unavailable | Fallback to alternate model from stress test results |
| **Iteration budget** (Layer 3 override) | Iter 1-3: standard evaluator; Iter 4: rubric threshold +0.2; Iter 5: escalate |

## 9. File Structure

```
/home/bright/code/orchestration/
├── loop_agent/
│   ├── __init__.py          # create_loop_agent(), run_loop()
│   ├── state.py             # OrchestrationState
│   ├── models.py            # model registry, ChatNVIDIA factory
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py
│   │   ├── coder.py
│   │   ├── tester.py
│   │   ├── reviewer.py         # includes parallel dispatch
│   │   ├── evaluator.py        # 3-layer evaluator pipeline
│   │   ├── evaluator_gate.py   # Layer 1: deterministic checks
│   │   ├── evaluator_rubric.py # Layer 2: multi-dimension scoring
│   │   ├── evaluator_judge.py  # Layer 3: fresh-context LLM decision
│   │   └── integration.py
│   ├── graph.py             # build_graph(), route_after_evaluator()
│   ├── tools.py             # tool implementations
│   └── checkpoint.py        # helper: save/restore checkpoint metadata
├── tests/
│   ├── test_state.py
│   ├── test_agents.py
│   ├── test_graph.py
│   └── test_e2e.py
├── loop_patterns.py         # preserved reference
└── pyproject.toml
```

## 10. Acceptance Criteria

1. `from loop_agent import create_loop_agent, run_loop` imports successfully
2. Running `"Fix typo: change Helo to Hello in README.md"` completes with `status: completed`
3. A task with failing tests loops back to coder and retries
4. A task that exceeds max_iterations halts with `status: halted`
5. Evaluator correctly routes finish→integration, continue→coder, escalate→halted
6. Reviewer runs 3 axes in parallel (verified by timing test: 3 reviewers complete in <4s total)
7. All agent outputs are valid JSON matching their expected schema
8. Checkpoints are saved after planner, coder, tester nodes
9. **Evaluator Layer 1 (Deterministic Gate)** returns `continue` before any LLM when test exit code != 0
10. **Evaluator Layer 2 (Rubric)** produces 5 orthogonal scores; any dim ≤ 2 forces `continue`
11. **Evaluator Layer 3 (Fresh Context)** receives only structured data, not shared conversation history
12. **Default-FAIL contract**: acceptance_criteria start all `passes: false`; evaluator must Read evidence before marking true
13. Post-evaluator hook overrides `finish` → `continue` if any AC has `passes: false` without evidence

## 11. Development Order

1. `state.py` — data model (including acceptance_criteria, rubric fields)
2. `models.py` — ChatNVIDIA factory with stress-test data
3. `tools.py` — tool implementations
4. `agents/coder.py` — first agent (core of the loop)
5. `agents/tester.py` — second agent (closes coding loop)
6. `agents/evaluator_gate.py` — Layer 1: deterministic checks
7. `agents/evaluator_rubric.py` — Layer 2: rubric scoring
8. `agents/evaluator_judge.py` — Layer 3: fresh-context decision + Default-FAIL
9. `agents/evaluator.py` — combine 3 layers into evaluator node
10. `agents/planner.py`, `reviewer.py`, `integration.py`
11. `graph.py` — assemble StateGraph with conditional routing
12. `checkpoint.py` — checkpoint/rewind logic
13. `tests/` — alongside each module
