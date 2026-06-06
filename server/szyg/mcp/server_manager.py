"""MCP Server管理器，管理外部MCP Server的生命周期。"""

import asyncio
import os
import subprocess
import time
from typing import Any

from szyg.models.common import MCPError, ServerNotFoundError, ToolTimeoutError
from szyg.models.mcp import MCPServerConfig, ToolResult


class MCPServerManager:
    """MCP Server管理器"""

    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._running: dict[str, bool] = {}

    def add_server(
        self,
        name: str,
        command: str,
        args: list[str] = None,
        env: dict = None,
        enabled: bool = True,
        auto_start: bool = True,
        timeout: int = 30,
    ) -> MCPServerConfig:
        """添加Server配置"""
        config = MCPServerConfig(
            name=name,
            command=command,
            args=args or [],
            env=env or {},
            enabled=enabled,
            auto_start=auto_start,
            timeout=timeout,
        )
        self._servers[name] = config
        self._running[name] = False
        if auto_start and enabled:
            self.start_server(name)
        return config

    def start_server(self, name: str) -> bool:
        """启动Server"""
        if name not in self._servers:
            raise ServerNotFoundError(f"Server not found: {name}")
        config = self._servers[name]
        try:
            env = dict(os.environ) if hasattr(os, "environ") else {}
            env.update(config.env)
            process = subprocess.Popen(
                [config.command] + config.args,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._processes[name] = process
            self._running[name] = True
            return True
        except Exception as e:
            raise MCPError(f"Failed to start server {name}: {e}")

    def stop_server(self, name: str) -> bool:
        """停止Server"""
        if name not in self._servers:
            raise ServerNotFoundError(f"Server not found: {name}")
        if name in self._processes:
            process = self._processes[name]
            try:
                process.terminate()
                process.wait(timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            del self._processes[name]
        self._running[name] = False
        return True

    def list_servers(self) -> list[MCPServerConfig]:
        """列出所有Server配置"""
        return list(self._servers.values())

    def is_running(self, name: str) -> bool:
        """检查Server是否运行中"""
        return self._running.get(name, False)

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict = None,
        timeout: float = 30.0,
    ) -> ToolResult:
        """调用Server上的Tool"""
        if server_name not in self._servers:
            raise ServerNotFoundError(f"Server not found: {server_name}")
        if not self._running.get(server_name, False):
            return ToolResult(
                success=False,
                error=f"Server not running: {server_name}",
            )
        # 模拟tool调用（实际应通过MCP协议通信）
        try:
            await asyncio.wait_for(asyncio.sleep(0.01), timeout=timeout)
            return ToolResult(
                success=True,
                data={
                    "result": f"Executed {tool_name} on {server_name}",
                    "arguments": arguments or {},
                },
            )
        except asyncio.TimeoutError:
            raise ToolTimeoutError(f"Tool call timed out after {timeout}s")

    def list_tools(self, server_name: str) -> list[dict]:
        """列出Server上的可用Tools"""
        if server_name not in self._servers:
            raise ServerNotFoundError(f"Server not found: {server_name}")
        # 返回模拟tools列表
        return [{"name": "sample_tool", "description": "A sample tool"}]

    def shutdown_all(self):
        """关闭所有Server"""
        for name in list(self._processes.keys()):
            self.stop_server(name)
