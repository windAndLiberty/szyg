"""
Unit tests for szyg.brain_hermes — Hermes Agent core engine.

Tests cover:
- Config loading (default + existing YAML)
- System prompt generation
- MCP server configuration
- Brain status API
- Singleton accessor
"""

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from szyg.brain_hermes import HermesBrain, get_brain, HERMES_HOME


@pytest.fixture
def isolated_brain(tmp_path: Path):
    """Create HermesBrain with isolated home directory and config."""
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir()
    (hermes_home / "sessions").mkdir()
    (hermes_home / "memory").mkdir()

    config_path = tmp_path / "hermes.yaml"

    with patch("szyg.brain_hermes.HERMES_HOME", hermes_home), \
         patch("szyg.brain_hermes.PROJECT_ROOT", tmp_path), \
         patch.dict(os.environ, {"HERMES_HOME": str(hermes_home)}):
        brain = HermesBrain()
        yield brain, config_path


class TestHermesBrainInit:
    def test_creates_hermes_home(self, isolated_brain):
        brain, _ = isolated_brain
        assert HERMES_HOME.exists()
        assert (HERMES_HOME / "sessions").exists()
        assert (HERMES_HOME / "memory").exists()

    def test_sets_env_var(self, isolated_brain):
        brain, _ = isolated_brain
        assert os.environ.get("HERMES_HOME") is not None

    def test_loads_config_creates_default(self, isolated_brain):
        brain, config_path = isolated_brain
        # Config should have been created from defaults
        assert brain.config is not None
        assert "model" in brain.config
        assert "mcp_servers" in brain.config

    def test_loads_existing_config(self, tmp_path):
        hermes_home = tmp_path / ".hermes"
        hermes_home.mkdir()
        (hermes_home / "sessions").mkdir()
        (hermes_home / "memory").mkdir()

        # Pre-create config
        custom_config = {
            "model": {
                "default": "custom/model",
                "provider": "custom",
                "base_url": "https://custom.api.com",
            },
            "mcp_servers": {"custom": {"command": "python3", "args": ["custom.py"]}},
        }
        config_path = tmp_path / "hermes.yaml"
        config_path.write_text(yaml.dump(custom_config), encoding="utf-8")

        with patch("szyg.brain_hermes.HERMES_HOME", hermes_home), \
             patch("szyg.brain_hermes.PROJECT_ROOT", tmp_path):
            brain = HermesBrain()
            assert brain.config["model"]["default"] == "custom/model"


class TestDefaultConfig:
    def test_model_config(self, isolated_brain):
        brain, _ = isolated_brain
        cfg = brain._default_config()
        assert cfg["model"]["default"] == "deepseek/deepseek-v4-pro"
        assert cfg["model"]["provider"] == "deepseek"

    def test_mcp_servers_count(self, isolated_brain):
        brain, _ = isolated_brain
        cfg = brain._default_config()
        assert len(cfg["mcp_servers"]) == 10

    def test_mcp_server_names(self, isolated_brain):
        brain, _ = isolated_brain
        cfg = brain._default_config()
        expected = {"publisher", "scheduler", "tools", "knowledge", "agents",
                    "oem", "platforms", "skills", "video", "web_tools"}
        assert set(cfg["mcp_servers"].keys()) == expected

    def test_agent_metadata(self, isolated_brain):
        brain, _ = isolated_brain
        cfg = brain._default_config()
        assert cfg["agent"]["name"] == "szyg"
        assert cfg["agent"]["timezone"] == "Asia/Shanghai"


class TestSystemPrompt:
    def test_returns_string(self, isolated_brain):
        brain, _ = isolated_brain
        prompt = brain.get_system_prompt()
        assert isinstance(prompt, str)

    def test_contains_subsystems(self, isolated_brain):
        brain, _ = isolated_brain
        prompt = brain.get_system_prompt()
        assert "内容发布管道" in prompt
        assert "平台自动化" in prompt
        assert "视频剪辑引擎" in prompt
        assert "智能调度引擎" in prompt

    def test_contains_marketing_skills(self, isolated_brain):
        brain, _ = isolated_brain
        prompt = brain.get_system_prompt()
        assert "文案写作" in prompt
        assert "文案编辑" in prompt
        assert "内容策略" in prompt
        assert "AI搜索引擎优化" in prompt
        assert "深度研究" in prompt

    def test_contains_hermes_reference(self, isolated_brain):
        brain, _ = isolated_brain
        prompt = brain.get_system_prompt()
        assert "Hermes Agent" in prompt


class TestMCPServers:
    def test_returns_list(self, isolated_brain):
        brain, _ = isolated_brain
        servers = brain.get_mcp_servers()
        assert isinstance(servers, list)

    def test_count(self, isolated_brain):
        brain, _ = isolated_brain
        servers = brain.get_mcp_servers()
        assert len(servers) == 10

    def test_server_structure(self, isolated_brain):
        brain, _ = isolated_brain
        servers = brain.get_mcp_servers()
        for s in servers:
            assert "name" in s
            assert "command" in s
            assert "args" in s

    def test_publisher_server(self, isolated_brain):
        brain, _ = isolated_brain
        servers = brain.get_mcp_servers()
        pub = next(s for s in servers if s["name"] == "publisher")
        assert "publisher_mcp.py" in " ".join(pub["args"])


class TestBrainStatus:
    def test_status_structure(self, isolated_brain):
        brain, _ = isolated_brain
        status = brain.get_status()
        assert status["engine"] == "hermes-agent"
        assert status["version"] == "0.15"
        assert "model" in status
        assert "provider" in status
        assert "mcp_servers" in status
        assert "server_list" in status

    def test_mcp_server_count(self, isolated_brain):
        brain, _ = isolated_brain
        status = brain.get_status()
        assert status["mcp_servers"] == 10

    def test_server_list_type(self, isolated_brain):
        brain, _ = isolated_brain
        status = brain.get_status()
        assert isinstance(status["server_list"], list)


class TestSingleton:
    def test_get_brain_returns_same_instance(self):
        with patch("szyg.brain_hermes._brain", None):
            b1 = get_brain()
            b2 = get_brain()
            assert b1 is b2
