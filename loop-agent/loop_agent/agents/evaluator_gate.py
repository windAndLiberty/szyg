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


def deterministic_gate(state: OrchestrationState, working_dir: str = ".") -> GateResult:
    """Run hardware checks against the current state.

    Checks:
    1. All test_results have exit_code == 0.
    2. All code_artifacts paths exist on disk.
    3. code_artifacts is not empty (regression check).
    """
    checks = []

    # Check 1: test exit codes
    for tr in state.get("test_results", []):
        exit_code = tr.get("exit_code", -1)
        passed = exit_code == 0
        checks.append({
            "name": f"test_exit_code:{tr.get('command', 'unknown')}",
            "passed": passed,
            "detail": f"exit_code={exit_code}" if not passed else "ok",
        })

    # Check 2: code artifacts exist on disk
    cwd = Path(working_dir).resolve()
    for art in state.get("code_artifacts", []):
        path = art.get("path", "")
        resolved = (cwd / path).resolve()
        if not str(resolved).startswith(str(cwd)):
            checks.append({
                "name": f"artifact_in_bounds:{path}",
                "passed": False,
                "detail": "Path escapes working directory",
            })
            continue
        exists = resolved.exists()
        checks.append({
            "name": f"artifact_exists:{path}",
            "passed": exists,
            "detail": f"File {'exists' if exists else 'missing'}: {path}",
        })

    # Check 3: code_artifacts is not empty
    if not state.get("code_artifacts", []):
        checks.append({
            "name": "no_regression",
            "passed": False,
            "detail": "code_artifacts is empty — nothing was produced",
        })

    all_passed = all(c["passed"] for c in checks)
    return GateResult(passed=all_passed, checks=checks)
