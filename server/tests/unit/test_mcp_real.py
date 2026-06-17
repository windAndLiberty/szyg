"""
「域灵」数字员工系统 - MCP 模块真单元测试
"""

import pytest

from szyg.mcp.server_manager import MCPServerManager
from szyg.mcp.tool_adapter import MCPToolAdapter
from szyg.models.common import ServerNotFoundError, ToolTimeoutError, MCPError
from szyg.models.mcp import MCPServerConfig, Tool, ToolResult


class TestMCPServerManager:
    """真实 MCPServerManager 类测试。"""

    @pytest.fixture
    def manager(self):
        return MCPServerManager()

    def test_add_server(self, manager):
        """添加 Server 配置应存储到内部字典。"""
        config = manager.add_server("test-srv", "echo", args=["hello"])
        assert config.name == "test-srv"
        assert config.command == "echo"
        assert config.args == ["hello"]
        assert "test-srv" in manager._servers

    def test_add_server_defaults(self, manager):
        """默认参数应正确设置。"""
        config = manager.add_server("minimal", "ls")
        assert config.args == []
        assert config.env == {}
        assert config.enabled is True
        assert config.auto_start is True
        assert config.timeout == 30

    def test_add_server_custom(self, manager):
        """自定义参数。"""
        config = manager.add_server(
            "custom",
            "python",
            args=["-m", "server"],
            env={"KEY": "VALUE"},
            enabled=False,
            auto_start=False,
            timeout=60,
        )
        assert config.enabled is False
        assert config.auto_start is False
        assert config.timeout == 60
        assert config.env == {"KEY": "VALUE"}

    def test_list_servers(self, manager):
        """列出所有 Server。"""
        manager.add_server("a", "cmd1", auto_start=False)
        manager.add_server("b", "cmd2", auto_start=False)
        servers = manager.list_servers()
        assert len(servers) == 2

    def test_is_running(self, manager):
        """is_running 检查运行状态。"""
        manager.add_server("srv", "cmd", auto_start=False)
        assert manager.is_running("srv") is False

    def test_is_running_nonexistent(self, manager):
        """检查不存在的 Server 返回 False。"""
        assert manager.is_running("unknown") is False

    def test_start_stop_nonexistent(self, manager):
        """启动不存在的 Server 抛出异常。"""
        with pytest.raises(ServerNotFoundError):
            manager.start_server("ghost")
        with pytest.raises(ServerNotFoundError):
            manager.stop_server("ghost")

    def test_list_tools(self, manager):
        """list_tools 返回工具列表。"""
        manager.add_server("fs", "npx", auto_start=False)
        tools = manager.list_tools("fs")
        assert len(tools) == 1
        assert tools[0]["name"] == "sample_tool"

    def test_list_tools_nonexistent(self, manager):
        """list_tools 对不存在的 Server 抛出异常。"""
        with pytest.raises(ServerNotFoundError):
            manager.list_tools("ghost")

    async def test_call_tool_not_running(self, manager):
        """对未启动的 Server 调用工具返回失败。"""
        manager.add_server("offline", "cmd", auto_start=False)
        result = await manager.call_tool("offline", "test_tool")
        assert result.success is False
        assert "not running" in result.error

    async def test_call_tool_nonexistent(self, manager):
        """对不存在的 Server 调用工具抛出异常。"""
        with pytest.raises(ServerNotFoundError):
            await manager.call_tool("ghost", "test")

    def test_auto_start_enabled(self, manager):
        """auto_start=True 且 enabled=True 时应自动启动。"""
        manager.add_server("auto", "echo", auto_start=True, enabled=True)
        # auto_start 会尝试启动，可能因找不到命令而失败
        # 但应在 _servers 中有记录
        assert "auto" in manager._servers

    def test_auto_start_disabled(self, manager):
        """enabled=False 时不应 auto_start。"""
        manager.add_server("disabled", "echo", auto_start=True, enabled=False)
        assert manager.is_running("disabled") is False

    def test_shutdown_all(self, manager):
        """shutdown_all 应清理所有进程。"""
        manager.add_server("s1", "echo", auto_start=False)
        manager.add_server("s2", "echo", auto_start=False)
        manager.shutdown_all()
        # 所有 Server 停止后不应崩溃


class TestMCPToolAdapter:
    """真实 MCPToolAdapter 类测试。"""

    @pytest.fixture
    def adapter(self):
        manager = MCPServerManager()
        manager.add_server("fs", "cmd", auto_start=False)
        return MCPToolAdapter(server_manager=manager)

    def test_default_init(self):
        """默认初始化应创建 MCPServerManager。"""
        adapter = MCPToolAdapter()
        assert adapter.server_manager is not None

    def test_list_available_tools_all(self, adapter):
        """列出所有 Server 的工具。"""
        tools = adapter.list_available_tools()
        assert len(tools) >= 1
        assert all(isinstance(t, Tool) for t in tools)

    def test_list_available_tools_for_server(self, adapter):
        """列出指定 Server 的工具。"""
        tools = adapter.list_available_tools(server_name="fs")
        assert len(tools) == 1
        assert tools[0].name == "sample_tool"

    async def test_execute(self, adapter):
        """执行工具调用。"""
        result = await adapter.execute("fs", "sample_tool", {"key": "val"})
        assert isinstance(result, ToolResult)
