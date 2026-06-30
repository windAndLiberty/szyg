"""MCP Server管理器，管理外部MCP Server的生命周期。

通过 stdio JSON-RPC 2.0 协议与 MCP Server 子进程通信。
每个 szyg 模块对应一个独立的 MCP Server 进程。
"""
import asyncio
import json
import os
import subprocess
import threading
import time
from typing import Any

from szyg.models.common import MCPError, ServerNotFoundError, ToolTimeoutError
from szyg.models.mcp import MCPServerConfig, ToolResult


class MCPServerManager:
    """MCP Server管理器 — 通过 stdio JSON-RPC 管理子进程生命周期和工具调用"""

    def __init__(self):
        self._servers: dict[str, MCPServerConfig] = {}
        self._processes: dict[str, subprocess.Popen] = {}
        self._running: dict[str, bool] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._lock_lock = threading.Lock()
        self._next_id: int = 1

    def _get_lock(self, name: str) -> threading.Lock:
        """Get or create a per-server lock for safe stdio access."""
        if name not in self._locks:
            with self._lock_lock:
                if name not in self._locks:
                    self._locks[name] = threading.Lock()
        return self._locks[name]

    def _next_request_id(self) -> int:
        """Generate unique request ID for JSON-RPC."""
        rid = self._next_id
        self._next_id += 1
        return rid

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
        """启动 MCP Server 子进程，通过 initialize 握手确认就绪"""
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

            # ── MCP initialize handshake ──
            init_req = json.dumps({
                "jsonrpc": "2.0",
                "id": self._next_request_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "szyg-hermes", "version": "1.0.0"},
                },
            }, ensure_ascii=False)
            process.stdin.write(init_req + "\n")
            process.stdin.flush()
            init_resp_line = process.stdout.readline()
            if not init_resp_line:
                raise MCPError(f"Server {name} did not respond to initialize")
            init_resp = json.loads(init_resp_line)
            if "error" in init_resp:
                raise MCPError(f"Server {name} init error: {init_resp['error']}")

            # Send initialized notification
            notified = json.dumps({
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            })
            process.stdin.write(notified + "\n")
            process.stdin.flush()

            self._running[name] = True
            return True
        except Exception as e:
            # Clean up on failure
            if name in self._processes:
                try:
                    self._processes[name].terminate()
                except Exception:
                    pass
                del self._processes[name]
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
        if name not in self._running:
            return False
        if not self._running[name]:
            return False
        # Double-check process is actually alive
        process = self._processes.get(name)
        if process is None:
            self._running[name] = False
            return False
        if process.poll() is not None:
            self._running[name] = False
            return False
        return True

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict = None,
        timeout: float = 30.0,
    ) -> ToolResult:
        """通过 stdio JSON-RPC 调用 MCP Server 上的 Tool。

        向子进程 stdin 发送 tools/call 请求，从 stdout 读取响应。
        使用线程锁保证同一 Server 的请求串行化，避免 stdio 交错。
        """
        if server_name not in self._servers:
            raise ServerNotFoundError(f"Server not found: {server_name}")
        if not self.is_running(server_name):
            return ToolResult(
                success=False,
                error=f"Server not running: {server_name}",
            )

        process = self._processes[server_name]
        lock = self._get_lock(server_name)
        request_id = self._next_request_id()

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {},
            },
        }

        def _sync_call() -> ToolResult:
            """Synchronous I/O wrapped in asyncio.to_thread for safety."""
            acquired = lock.acquire(timeout=timeout)
            if not acquired:
                return ToolResult(
                    success=False,
                    error=f"Timeout waiting for lock on server {server_name}",
                )
            try:
                # Check process health under lock
                if process.poll() is not None:
                    rc = process.returncode
                    self._running[server_name] = False
                    stderr_tail = ""
                    try:
                        stderr_tail = process.stderr.read()[-500:]
                    except Exception:
                        pass
                    return ToolResult(
                        success=False,
                        error=f"Server process exited with code {rc}: {stderr_tail[-200:]}",
                    )

                # Write request
                try:
                    req_line = json.dumps(request, ensure_ascii=False)
                    process.stdin.write(req_line + "\n")
                    process.stdin.flush()
                except (BrokenPipeError, OSError) as e:
                    self._running[server_name] = False
                    return ToolResult(
                        success=False,
                        error=f"Failed to write to server stdin: {e}",
                    )

                # Read response
                try:
                    resp_line = process.stdout.readline()
                except Exception as e:
                    return ToolResult(
                        success=False,
                        error=f"Failed to read from server stdout: {e}",
                    )

                if not resp_line:
                    # Process may have crashed; collect stderr
                    rc = process.poll()
                    self._running[server_name] = False
                    stderr_tail = ""
                    try:
                        stderr_tail = process.stderr.read()[-1000:]
                    except Exception:
                        pass
                    return ToolResult(
                        success=False,
                        error=f"Server {server_name} closed stdout (exit={rc}). stderr: {stderr_tail[-300:]}",
                    )

                try:
                    response = json.loads(resp_line.strip())
                except json.JSONDecodeError:
                    return ToolResult(
                        success=False,
                        error=f"Invalid JSON from server: {resp_line[:200]}",
                    )

                if "error" in response:
                    err = response["error"]
                    return ToolResult(
                        success=False,
                        error=f"MCP error ({err.get('code', '?')}): {err.get('message', str(err))}",
                    )

                result = response.get("result", {})
                content = result.get("content", [])
                # Extract text from content array
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                text_output = "\n".join(text_parts) if text_parts else json.dumps(result, ensure_ascii=False)

                # Try parsing as JSON if it looks like JSON
                data = text_output
                if text_output.strip().startswith(("{", "[")):
                    try:
                        data = json.loads(text_output)
                    except json.JSONDecodeError:
                        pass

                return ToolResult(
                    success=True,
                    data=data,
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=f"Unexpected error calling {tool_name}: {e}",
                )
            finally:
                lock.release()

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(_sync_call),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            # If timed out, mark process as suspect
            return ToolResult(
                success=False,
                error=f"Tool call to {server_name}/{tool_name} timed out after {timeout}s",
            )

    def list_tools(self, server_name: str) -> list[dict]:
        """列出Server上的可用Tools — 通过 tools/list 请求"""
        if server_name not in self._servers:
            raise ServerNotFoundError(f"Server not found: {server_name}")
        if not self.is_running(server_name):
            return []

        process = self._processes[server_name]
        lock = self._get_lock(server_name)
        request_id = self._next_request_id()

        request = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/list",
        }

        acquired = lock.acquire(timeout=10)
        if not acquired:
            return []
        try:
            if process.poll() is not None:
                self._running[server_name] = False
                return []

            req_line = json.dumps(request, ensure_ascii=False)
            process.stdin.write(req_line + "\n")
            process.stdin.flush()

            resp_line = process.stdout.readline()
            if not resp_line:
                return []

            response = json.loads(resp_line.strip())
            if "error" in response:
                return []

            result = response.get("result", {})
            return result.get("tools", [])
        except Exception:
            return []
        finally:
            lock.release()

    def shutdown_all(self):
        """关闭所有Server"""
        for name in list(self._processes.keys()):
            self.stop_server(name)
