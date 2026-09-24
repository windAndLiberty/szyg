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
        "lines": len(content.splitlines()),
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
            "stdout_truncated": len(result.stdout) > 5000,
            "stderr_truncated": len(result.stderr) > 2000,
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
