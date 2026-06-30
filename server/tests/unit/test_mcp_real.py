"""
「域灵」数字员工系统 - MCP 模块真单元测试

使用真实的 MCP server 子进程（tests/fixtures/test_mcp_server.py）验证
MCPServerManager 和 MCPToolAdapter 的完整链路：启动 → initialize握手 →
tools/list → tools/call → 停止。
"""

import sys
import os
import pytest

from szyg.mcp.server_manager import MCPServerManager
from szyg.mcp.tool_adapter import MCPToolAdapter
from szyg.models.common import ServerNotFoundError, ToolTimeoutError, MCPError
from szyg.models.mcp import MCPServerConfig, Tool, ToolResult

_FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "mcp_server_stub.py")


class TestMCPServerManager:
    """真实 MCPServerManager 类测试。"""

    @pytest.fixture
    def manager(self):
        return MCPServerManager()

    def test_add_server(self, manager):
        """添加 Server 配置应存储到内部字典（不自动启动）。"""
        config = manager.add_server("test-srv", "echo", args=["hello"], auto_start=False)
        assert config.name == "test-srv"
        assert config.command == "echo"
        assert config.args == ["hello"]
        assert "test-srv" in manager._servers

    def test_add_server_defaults(self, manager):
        """add_server 函数签名默认值: enabled=True, timeout=30。auto_start传False避免子进程。"""
        config = manager.add_server("minimal", "ls", auto_start=False)
        assert config.args == []
        assert config.env == {}
        assert config.enabled is True
        assert config.auto_start is False
        assert config.timeout == 30

    def test_add_server_defaults_real(self, manager):
        """auto_start=True + enabled=True 时应真正启动子进程并完成 MCP 握手。"""
        config = manager.add_server(
            "real-server", sys.executable, args=[_FIXTURE],
            auto_start=True, enabled=True,
        )
        assert config.name == "real-server"
        assert "real-server" in manager._servers
        assert manager.is_running("real-server") is True
        manager.stop_server("real-server")

    def test_add_server_custom(self, manager):
        """自定义参数。"""
        config = manager.add_server(
            "custom", "python", args=["-m", "server"],
            env={"KEY": "VALUE"}, enabled=False, auto_start=False, timeout=60,
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

    def test_list_tools_not_running(self, manager):
        """list_tools 对未启动的 Server 返回空列表。"""
        manager.add_server("fs", "npx", auto_start=False)
        tools = manager.list_tools("fs")
        assert tools == []

    def test_list_tools_real(self, manager):
        """list_tools 对真实运行的 MCP server 返回 sample_tool。"""
        manager.add_server("real", sys.executable, args=[_FIXTURE], auto_start=True)
        try:
            tools = manager.list_tools("real")
            assert len(tools) == 1
            assert tools[0]["name"] == "sample_tool"
            assert tools[0]["description"] == "A sample tool for testing"
        finally:
            manager.stop_server("real")

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

    async def test_call_tool_real(self, manager):
        """对真实运行的 MCP server 调用工具应成功。"""
        manager.add_server("real", sys.executable, args=[_FIXTURE], auto_start=True)
        try:
            result = await manager.call_tool("real", "sample_tool", {"key": "val"})
            assert result.success is True
        finally:
            manager.stop_server("real")

    def test_auto_start_enabled(self, manager):
        """auto_start=True 且 enabled=True 时应自动启动子进程。"""
        manager.add_server("auto", sys.executable, args=[_FIXTURE], auto_start=True, enabled=True)
        try:
            assert "auto" in manager._servers
            assert manager.is_running("auto") is True
        finally:
            manager.stop_server("auto")

    def test_auto_start_disabled(self, manager):
        """enabled=False 时不应 auto_start。"""
        manager.add_server("disabled", "echo", auto_start=True, enabled=False)
        assert manager.is_running("disabled") is False

    def test_shutdown_all(self, manager):
        """shutdown_all 应清理所有进程。"""
        manager.add_server("s1", sys.executable, args=[_FIXTURE], auto_start=True)
        manager.add_server("s2", sys.executable, args=[_FIXTURE], auto_start=True)
        manager.shutdown_all()
        assert manager.is_running("s1") is False
        assert manager.is_running("s2") is False


class TestMCPToolAdapter:
    """真实 MCPToolAdapter 类测试。"""

    @pytest.fixture
    def adapter(self):
        manager = MCPServerManager()
        manager.add_server("fs", sys.executable, args=[_FIXTURE], auto_start=True)
        return MCPToolAdapter(server_manager=manager)

    def test_default_init(self):
        """默认初始化应创建 MCPServerManager。"""
        adapter = MCPToolAdapter()
        assert adapter.server_manager is not None

    def test_list_available_tools_all(self, adapter):
        """列出所有 Server 的工具 — 真实 MCP server 应返回 sample_tool。"""
        tools = adapter.list_available_tools()
        assert len(tools) >= 1
        assert all(isinstance(t, Tool) for t in tools)
        assert any(t.name == "sample_tool" for t in tools)

    def test_list_available_tools_for_server(self, adapter):
        """列出指定 Server 的工具。"""
        tools = adapter.list_available_tools(server_name="fs")
        assert len(tools) == 1
        assert tools[0].name == "sample_tool"
        assert isinstance(tools[0], Tool)

    async def test_execute(self, adapter):
        """执行工具调用 — 真实 MCP server 应返回成功的 ToolResult。"""
        result = await adapter.execute("fs", "sample_tool", {"key": "val"})
        assert isinstance(result, ToolResult)
        assert result.success is True
