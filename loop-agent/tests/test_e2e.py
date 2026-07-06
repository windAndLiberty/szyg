"""End-to-end test with real NVIDIA NIM API calls.

Requires: NVIDIA_API_KEY env var, network access to integrate.api.nvidia.com
"""

import os
import pytest
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
    """End-to-end: fix a typo in README.md with real NIM API calls."""
    readme = tmp_path / "README.md"
    readme.write_text("# Helo World\n\nThis is a test.\n")

    graph = create_loop_agent(str(tmp_path))
    final = run_loop(
        graph,
        title="Fix typo in README",
        description="Change 'Helo' to 'Hello' in README.md. The first line says '# Helo World' and should say '# Hello World'.",
        max_iterations=3,
        working_dir=str(tmp_path),
    )

    assert final["status"] in ("completed", "halted"), (
        f"Expected completed or halted, got {final['status']}. "
        f"Errors: {final.get('errors', [])}"
    )

    if final["status"] == "completed":
        content = readme.read_text()
        assert "Hello" in content, f"README should contain 'Hello', got: {content}"
