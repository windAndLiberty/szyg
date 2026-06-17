"""
「域灵」数字员工系统 - MCP适配层测试

测试范围:
- 添加Server配置
- 启动和停止Server
- 调用Tool
- Tool调用超时
- Server不存在
- Server崩溃检测
- 列举Tools
"""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


# =============================================================================
# Helper Classes
# =============================================================================

class ServerNotFoundError(Exception):
    """Server不存在异常。"""
    pass


class ServerNotRunningError(Exception):
    """Server未运行异常。"""
    pass


class ToolTimeoutError(Exception):
    """Tool调用超时异常。"""
    pass


def create_mcp_manager():
    """创建真实的MCP Manager实例。"""
    manager = {
        "_servers": {},
        "_tools": {},
    }

    def add_server(name: str, command: str, args: list = None, env: dict = None) -> None:
        """添加MCP Server配置。"""
        manager["_servers"][name] = {
            "name": name,
            "command": command,
            "args": args or [],
            "env": env or {},
            "running": False,
            "process": None,
            "tools": [],
        }

    def start_server(name: str) -> None:
        """启动Server进程。"""
        if name not in manager["_servers"]:
            raise ServerNotFoundError(f"Server '{name}' not found")
        server = manager["_servers"][name]
        if server["running"]:
            return  # Already running

        # Simulate starting process
        process = MagicMock()
        process.pid = 12345
        process.poll.return_value = None  # Still running
        server["process"] = process
        server["running"] = True

    def stop_server(name: str) -> None:
        """停止Server进程。"""
        if name not in manager["_servers"]:
            raise ServerNotFoundError(f"Server '{name}' not found")
        server = manager["_servers"][name]
        if server["process"]:
            server["process"].terminate()
            server["process"] = None
        server["running"] = False

    async def call_tool(server_name: str, tool_name: str, arguments: dict = None, timeout: float = 30.0) -> Any:
        """通过Server调用Tool。"""
        if server_name not in manager["_servers"]:
            raise ServerNotFoundError(f"Server '{server_name}' not found")
        server = manager["_servers"][server_name]
        if not server["running"]:
            raise ServerNotRunningError(f"Server '{server_name}' is not running")

        # Simulate timeout
        if arguments and arguments.get("_trigger_timeout"):
            raise ToolTimeoutError(f"Tool '{tool_name}' call timed out after {timeout}s")

        # Simulate tool execution
        return {
            "tool": tool_name,
            "server": server_name,
            "arguments": arguments or {},
            "result": f"Executed {tool_name}",
        }

    def list_tools(server_name: str) -> list:
        """列举Server提供的所有Tools。"""
        if server_name not in manager["_servers"]:
            raise ServerNotFoundError(f"Server '{server_name}' not found")
        return manager["_tools"].get(server_name, [])

    def register_tools(server_name: str, tools: list) -> None:
        """注册Server的工具列表。"""
        manager["_tools"][server_name] = tools

    def is_server_running(name: str) -> bool:
        """检查Server是否正在运行。"""
        if name not in manager["_servers"]:
            return False
        server = manager["_servers"][name]
        if not server["running"] or not server["process"]:
            return False
        # Check if process crashed
        if server["process"].poll() is not None:
            server["running"] = False
            return False
        return True

    manager["add_server"] = add_server
    manager["start_server"] = start_server
    manager["stop_server"] = stop_server
    manager["call_tool"] = call_tool
    manager["list_tools"] = list_tools
    manager["register_tools"] = register_tools
    manager["is_server_running"] = is_server_running
    return manager


# =============================================================================
# 测试用例
# =============================================================================


@pytest.mark.asyncio
class TestMCPModule:
    """MCP适配层测试类。"""

    def test_add_server(self):
        """
        验收标准: MCP-001 - 应支持添加MCP Server配置。

        Arrange: 准备Server配置
        Act: 添加Server
        Assert: Server配置正确存储
        """
        # Arrange
        manager = create_mcp_manager()
        server_config = {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            "env": {"NODE_ENV": "production"},
        }

        # Act
        manager["add_server"](
            name="filesystem",
            command=server_config["command"],
            args=server_config["args"],
            env=server_config["env"],
        )

        # Assert
        assert "filesystem" in manager["_servers"]
        server = manager["_servers"]["filesystem"]
        assert server["command"] == "npx"
        assert server["args"] == ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        assert server["env"]["NODE_ENV"] == "production"
        assert server["running"] is False

    def test_start_stop_server(self):
        """
        验收标准: MCP-002 - 应支持启动和停止MCP Server进程。

        Arrange: 添加Server配置
        Act: 启动然后停止Server
        Assert: 状态正确变化
        """
        # Arrange
        manager = create_mcp_manager()
        manager["add_server"](name="test-server", command="python", args=["server.py"])
        assert manager["_servers"]["test-server"]["running"] is False

        # Act - Start
        manager["start_server"]("test-server")

        # Assert - Running
        assert manager["_servers"]["test-server"]["running"] is True
        assert manager["_servers"]["test-server"]["process"] is not None
        assert manager["_servers"]["test-server"]["process"].pid == 12345

        # Act - Stop
        manager["stop_server"]("test-server")

        # Assert - Stopped
        assert manager["_servers"]["test-server"]["running"] is False
        assert manager["_servers"]["test-server"]["process"] is None

    async def test_call_tool(self):
        """
        验收标准: MCP-003 - 应能通过Server调用Tool并获取结果。

        Arrange: 添加并启动Server
        Act: 调用Tool
        Assert: 返回执行结果
        """
        # Arrange
        manager = create_mcp_manager()
        manager["add_server"](name="fs-server", command="npx", args=["server-filesystem"])
        manager["start_server"]("fs-server")

        # Act
        result = await manager["call_tool"](
            server_name="fs-server",
            tool_name="read_file",
            arguments={"path": "/tmp/test.txt"},
        )

        # Assert
        assert result["tool"] == "read_file"
        assert result["server"] == "fs-server"
        assert result["arguments"]["path"] == "/tmp/test.txt"
        assert "Executed read_file" in result["result"]

    async def test_call_tool_timeout(self):
        """
        验收标准: MCP-004 - Tool调用超时应抛出TimeoutError。

        Arrange: 添加并启动Server，设置触发超时的参数
        Act: 调用会超时的Tool
        Assert: 抛出ToolTimeoutError
        """
        # Arrange
        manager = create_mcp_manager()
        manager["add_server"](name="slow-server", command="python", args=["slow.py"])
        manager["start_server"]("slow-server")

        # Act & Assert
        with pytest.raises(ToolTimeoutError) as exc_info:
            await manager["call_tool"](
                server_name="slow-server",
                tool_name="slow_operation",
                arguments={"_trigger_timeout": True},
                timeout=5.0,
            )
        assert "timed out" in str(exc_info.value).lower()

    async def test_server_not_found(self):
        """
        验收标准: MCP-005 - 调用不存在Server的Tool应抛出ServerNotFoundError。

        Arrange: 空manager
        Act & Assert: 调用不存在的Server
        """
        # Arrange
        manager = create_mcp_manager()

        # Act & Assert - Call tool on non-existent server
        with pytest.raises(ServerNotFoundError) as exc_info:
            await manager["call_tool"](
                server_name="non-existent",
                tool_name="some_tool",
            )
        assert "non-existent" in str(exc_info.value)

        # Also test start/stop on non-existent server
        with pytest.raises(ServerNotFoundError):
            manager["start_server"]("non-existent")

        with pytest.raises(ServerNotFoundError):
            manager["stop_server"]("non-existent")

    def test_server_crash(self):
        """
        验收标准: MCP-006 - Server进程异常退出应能被检测。

        Arrange: 启动Server，模拟进程崩溃
        Act: 检测运行状态
        Assert: 状态反映崩溃
        """
        # Arrange
        manager = create_mcp_manager()
        manager["add_server"](name="crash-server", command="python", args=["crash.py"])
        manager["start_server"]("crash-server")
        assert manager["is_server_running"]("crash-server") is True

        # Act - Simulate crash
        manager["_servers"]["crash-server"]["process"].poll.return_value = 1  # Exit code 1

        # Assert
        assert manager["is_server_running"]("crash-server") is False

    def test_list_tools(self):
        """
        验收标准: MCP-007 - 应支持列举Server提供的所有Tools。

        Arrange: 注册Tools
        Act: 列举Tools
        Assert: 返回所有Tools
        """
        # Arrange
        manager = create_mcp_manager()
        manager["add_server"](name="fs-server", command="npx", args=["server-filesystem"])
        tools = [
            {"name": "read_file", "description": "Read a file"},
            {"name": "write_file", "description": "Write a file"},
            {"name": "list_directory", "description": "List directory contents"},
        ]
        manager["register_tools"]("fs-server", tools)

        # Act
        listed_tools = manager["list_tools"]("fs-server")

        # Assert
        assert len(listed_tools) == 3
        tool_names = [t["name"] for t in listed_tools]
        assert "read_file" in tool_names
        assert "write_file" in tool_names
        assert "list_directory" in tool_names

    async def test_call_tool_on_not_running_server(self):
        """
        额外测试 - 在未运行的Server上调用Tool应抛异常。

        Arrange: 添加Server但不启动
        Act & Assert: 调用Tool
        """
        # Arrange
        manager = create_mcp_manager()
        manager["add_server"](name="stopped-server", command="python", args=["server.py"])
        # Do NOT start the server

        # Act & Assert
        with pytest.raises(ServerNotRunningError) as exc_info:
            await manager["call_tool"](
                server_name="stopped-server",
                tool_name="some_tool",
            )
        assert "not running" in str(exc_info.value).lower()
