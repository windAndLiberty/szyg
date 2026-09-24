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
MODEL_REGISTRY: dict[str, ModelConfig] = {
    "planner": ModelConfig(
        model="nvidia/nemotron-3-super-120b-a12b",
        timeout=180,
        temperature=0.7,
        max_completion_tokens=4096,
    ),
    "coder": ModelConfig(
        model="deepseek-ai/deepseek-v4-flash",
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
    "deepseek-ai/deepseek-v4-flash": "moonshotai/kimi-k2.6",
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
