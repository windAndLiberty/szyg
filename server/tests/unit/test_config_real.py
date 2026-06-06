"""
「域灵」数字员工系统 - Config模块真单元测试

直接导入 yuling.config.settings 中的 Pydantic 模型，
测试验证规则、默认值、序列化/反序列化。
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from yuling.config.settings import (
    AgentConfig,
    APIConfig,
    ComfyUIConfig,
    FFmpegConfig,
    IntegrationsConfig,
    MCPConfig,
    MCPServerDefinition,
    MemoryConfig,
    ModelBackend,
    ModelsConfig,
    WechatyConfig,
    WhisperConfig,
    YuLingSettings,
    get_settings,
    reload_settings,
)


class TestYuLingSettings:
    """测试主配置类。"""

    def test_default_construction(self):
        """默认构造应使用 Field default 值。"""
        settings = YuLingSettings()
        assert settings.agent.name == "域灵"
        assert settings.agent.max_plan_steps == 10
        assert settings.memory.db_path == "./data/memory.db"
        assert settings.memory.enable_fts is True
        assert settings.memory.embedding_dim == 768
        assert settings.api.host == "0.0.0.0"
        assert settings.api.port == 8000
        assert settings.debug is False
        assert settings.log_level == "INFO"

    def test_env_prefix_override(self, monkeypatch):
        """环境变量 YL_ 前缀应覆盖默认值。"""
        monkeypatch.setenv("YL_DEBUG", "true")
        monkeypatch.setenv("YL_LOG_LEVEL", "ERROR")
        monkeypatch.setenv("YL_AGENT__MAX_PLAN_STEPS", "25")
        monkeypatch.setenv("YL_API__PORT", "9999")

        settings = YuLingSettings()
        assert settings.debug is True
        assert settings.log_level == "ERROR"
        assert settings.agent.max_plan_steps == 25
        assert settings.api.port == 9999

    def test_nested_env_override(self, monkeypatch):
        """双层嵌套环境变量应能覆盖。"""
        monkeypatch.setenv("YL_MEMORY__DB_PATH", "/custom/path/memory.db")
        monkeypatch.setenv("YL_MEMORY__SIMILARITY_THRESHOLD", "0.85")

        settings = YuLingSettings()
        assert settings.memory.db_path == "/custom/path/memory.db"
        assert settings.memory.similarity_threshold == 0.85

    def test_global_singleton(self, monkeypatch):
        """get_settings() 应返回单例。"""
        # Force reset
        reload_settings()
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_reload_settings(self):
        """reload_settings() 应返回新实例。"""
        s1 = get_settings()
        s2 = reload_settings()
        assert s1 is not s2  # New instance

    def test_extra_env_ignored(self, monkeypatch):
        """extra='ignore' — 未知环境变量不应报错。"""
        monkeypatch.setenv("YL_UNKNOWN_FIELD", "should_be_ignored")
        settings = YuLingSettings()
        # Should not raise, and field should not exist
        assert not hasattr(settings, "unknown_field")


class TestAgentConfig:
    """测试 AgentConfig 验证规则。"""

    def test_default_values(self):
        cfg = AgentConfig()
        assert cfg.name == "域灵"
        assert cfg.max_plan_steps == 10
        assert cfg.planner_model == "qwen2.5:14b"
        assert cfg.executor_model == "qwen2.5:14b"
        assert cfg.max_retries == 3
        assert cfg.timeout_seconds == 120
        assert cfg.enable_self_correction is True

    def test_max_plan_steps_bounds(self):
        """max_plan_steps 必须在 1-50 之间。"""
        # Valid
        assert AgentConfig(max_plan_steps=1).max_plan_steps == 1
        assert AgentConfig(max_plan_steps=50).max_plan_steps == 50
        assert AgentConfig(max_plan_steps=25).max_plan_steps == 25

        # Out of bounds
        with pytest.raises(ValueError):  # Pydantic ValidationError
            AgentConfig(max_plan_steps=0)
        with pytest.raises(ValueError):
            AgentConfig(max_plan_steps=51)

    def test_max_retries_bounds(self):
        """max_retries 必须在 0-10 之间。"""
        AgentConfig(max_retries=0)
        AgentConfig(max_retries=10)
        with pytest.raises(ValueError):
            AgentConfig(max_retries=-1)
        with pytest.raises(ValueError):
            AgentConfig(max_retries=11)

    def test_timeout_seconds_minimum(self):
        """timeout_seconds 最小为 10。"""
        AgentConfig(timeout_seconds=10)
        with pytest.raises(ValueError):
            AgentConfig(timeout_seconds=9)

    def test_partial_override(self):
        """只覆盖部分字段，其余保持默认。"""
        cfg = AgentConfig(name="自定义", max_plan_steps=20)
        assert cfg.name == "自定义"
        assert cfg.max_plan_steps == 20
        # 其余保持默认
        assert cfg.planner_model == "qwen2.5:14b"
        assert cfg.max_retries == 3


class TestMemoryConfig:
    """测试 MemoryConfig 验证规则。"""

    def test_default_values(self):
        cfg = MemoryConfig()
        assert cfg.db_path == "./data/memory.db"
        assert cfg.enable_fts is True
        assert cfg.embedding_dim == 768
        assert cfg.similarity_threshold == 0.75

    def test_similarity_threshold_bounds(self):
        """similarity_threshold 必须在 0.0-1.0 之间。"""
        MemoryConfig(similarity_threshold=0.0)
        MemoryConfig(similarity_threshold=1.0)
        with pytest.raises(ValueError):
            MemoryConfig(similarity_threshold=-0.1)
        with pytest.raises(ValueError):
            MemoryConfig(similarity_threshold=1.1)

    def test_embedding_dim_bounds(self):
        """embedding_dim 必须在 128-4096 之间。"""
        MemoryConfig(embedding_dim=128)
        MemoryConfig(embedding_dim=4096)
        with pytest.raises(ValueError):
            MemoryConfig(embedding_dim=127)
        with pytest.raises(ValueError):
            MemoryConfig(embedding_dim=4097)


class TestAPIConfig:
    """测试 APIConfig 验证规则。"""

    def test_default_values(self):
        cfg = APIConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8000
        assert cfg.workers == 1
        assert cfg.reload is False

    def test_port_bounds(self):
        """port 必须在 1024-65535 之间。"""
        APIConfig(port=1024)
        APIConfig(port=65535)
        with pytest.raises(ValueError):
            APIConfig(port=1023)
        with pytest.raises(ValueError):
            APIConfig(port=65536)
        with pytest.raises(ValueError):
            APIConfig(port=80)

    def test_workers_bounds(self):
        """workers 必须在 1-8 之间。"""
        APIConfig(workers=1)
        APIConfig(workers=8)
        with pytest.raises(ValueError):
            APIConfig(workers=0)
        with pytest.raises(ValueError):
            APIConfig(workers=9)

    def test_max_request_body_size(self):
        """max_request_body_size 最小 1MB。"""
        cfg = APIConfig(max_request_body_size=2097152)  # 2MB
        assert cfg.max_request_body_size == 2097152
        with pytest.raises(ValueError):
            APIConfig(max_request_body_size=1048575)  # just below 1MB


class TestModelBackend:
    """测试 ModelBackend 验证。"""

    def test_required_fields(self):
        """name, base_url, default_model 为必填字段。"""
        with pytest.raises(ValueError):
            ModelBackend()  # 缺少必填字段

    def test_valid_construction(self):
        backend = ModelBackend(
            name="ollama",
            base_url="http://localhost:11434",
            default_model="qwen2.5",
        )
        assert backend.name == "ollama"
        assert backend.backend_type == "ollama"
        assert backend.base_url == "http://localhost:11434"
        assert backend.default_model == "qwen2.5"
        assert backend.priority == 1
        assert backend.enable_streaming is True

    def test_priority_bounds(self):
        """priority 必须在 1-10 之间。"""
        backend = ModelBackend(
            name="test", base_url="http://x", default_model="x", priority=1
        )
        assert backend.priority == 1

        backend = ModelBackend(
            name="test", base_url="http://x", default_model="x", priority=10
        )
        assert backend.priority == 10

        with pytest.raises(ValueError):
            ModelBackend(name="test", base_url="http://x", default_model="x", priority=0)
        with pytest.raises(ValueError):
            ModelBackend(name="test", base_url="http://x", default_model="x", priority=11)

    def test_backend_type_literal(self):
        """backend_type 只能是 ollama 或 litellm。"""
        backend = ModelBackend(
            name="test", base_url="http://x", default_model="x", backend_type="litellm"
        )
        assert backend.backend_type == "litellm"

        with pytest.raises(ValueError):
            ModelBackend(name="test", base_url="http://x", default_model="x", backend_type="invalid")


class TestMCPConfig:
    """测试 MCP 配置。"""

    def test_default_mcp_config(self):
        cfg = MCPConfig()
        assert cfg.servers == []
        assert cfg.default_timeout == 30
        assert cfg.tool_result_max_length == 10000

    def test_default_timeout_minimum(self):
        """default_timeout 最小为 5。"""
        MCPConfig(default_timeout=5)
        with pytest.raises(ValueError):
            MCPConfig(default_timeout=4)

    def test_tool_result_min_length(self):
        """tool_result_max_length 最小 1000。"""
        MCPConfig(tool_result_max_length=1000)
        with pytest.raises(ValueError):
            MCPConfig(tool_result_max_length=999)

    def test_server_definition(self):
        server = MCPServerDefinition(
            name="test-server",
            command="python",
            args=["-m", "test"],
        )
        assert server.name == "test-server"
        assert server.enabled is True
        assert server.auto_start is True
        assert server.timeout == 30

    def test_server_timeout_minimum(self):
        """server timeout 最小 5 秒。"""
        MCPServerDefinition(name="s", command="c", timeout=5)
        with pytest.raises(ValueError):
            MCPServerDefinition(name="s", command="c", timeout=4)

    def test_mcp_config_with_servers(self):
        cfg = MCPConfig(
            servers=[
                MCPServerDefinition(name="fs", command="npx", args=["-y", "server-filesystem"]),
                MCPServerDefinition(name="db", command="npx", args=["-y", "server-sqlite"]),
            ]
        )
        assert len(cfg.servers) == 2
        assert cfg.servers[0].name == "fs"
        assert cfg.servers[1].name == "db"


class TestSerialization:
    """测试配置模型的序列化/反序列化。"""

    def test_round_trip_json(self):
        """Pydantic 模型应能正确序列化和反序列化。"""
        cfg = AgentConfig(name="test", max_plan_steps=30)
        json_str = cfg.model_dump_json()
        assert '"test"' in json_str
        assert '30' in json_str

        # 反序列化
        cfg2 = AgentConfig.model_validate_json(json_str)
        assert cfg2.name == "test"
        assert cfg2.max_plan_steps == 30

    def test_round_trip_dict(self):
        """model_dump / model_validate 应往返正确。"""
        cfg = MemoryConfig(db_path="/tmp/test.db", enable_fts=False)
        d = cfg.model_dump()
        assert d["db_path"] == "/tmp/test.db"
        assert d["enable_fts"] is False

        cfg2 = MemoryConfig.model_validate(d)
        assert cfg2.db_path == "/tmp/test.db"
        assert cfg2.enable_fts is False
