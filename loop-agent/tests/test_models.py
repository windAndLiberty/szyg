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
    fallback = get_fallback_model("deepseek-ai/deepseek-v4-flash")
    assert fallback == "moonshotai/kimi-k2.6"


def test_get_fallback_model_unknown():
    fallback = get_fallback_model("nonexistent/model")
    assert fallback is None
