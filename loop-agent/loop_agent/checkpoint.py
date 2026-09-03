# loop_agent/checkpoint.py
"""Checkpoint helper functions for the loop agent graph."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from loop_agent.state import OrchestrationState


def make_checkpoint_metadata(stage: str, state: OrchestrationState) -> dict:
    """Create checkpoint metadata for the current state."""
    state_hash = hashlib.sha256(
        json.dumps({
            "status": state.get("status"),
            "plan": state.get("plan"),
            "code_artifacts": state.get("code_artifacts"),
            "test_results": state.get("test_results"),
            "iteration": state.get("iteration"),
        }, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]
    return {
        "stage": stage,
        "state_hash": state_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
