"""MCP工具适配器 - 统一Tool调用接口."""

from yuling.models.mcp import Tool, ToolResult
from yuling.mcp.server_manager import MCPServerManager


class MCPToolAdapter:
    """MCP工具适配器 - 统一Tool调用接口"""

    def __init__(self, server_manager: MCPServerManager | None = None):
        self.server_manager = server_manager or MCPServerManager()

    async def execute(
        self, server_name: str, tool_name: str, parameters: dict = None
    ) -> ToolResult:
        """执行工具调用"""
        return await self.server_manager.call_tool(
            server_name, tool_name, parameters or {}
        )

    def list_available_tools(self, server_name: str | None = None) -> list[Tool]:
        """列出可用工具"""
        tools = []
        if server_name:
            raw_tools = self.server_manager.list_tools(server_name)
            for t in raw_tools:
                tools.append(
                    Tool(
                        name=t["name"],
                        description=t.get("description", ""),
                        parameters=t.get("parameters", {}),
                    )
                )
        else:
            for server in self.server_manager.list_servers():
                raw_tools = self.server_manager.list_tools(server.name)
                for t in raw_tools:
                    tools.append(
                        Tool(
                            name=t["name"],
                            description=t.get("description", ""),
                            parameters=t.get("parameters", {}),
                        )
                    )
        return tools
