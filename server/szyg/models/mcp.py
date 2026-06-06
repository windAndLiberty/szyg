"""MCP相关模型。"""

from typing import Any

from pydantic import BaseModel


class MCPServerConfig(BaseModel):
    """MCP服务器配置。"""

    name: str
    command: str
    args: list[str] = []
    env: dict = {}
    enabled: bool = True
    auto_start: bool = True
    timeout: int = 30


class Tool(BaseModel):
    """工具定义。"""

    name: str
    description: str = ""
    parameters: dict = {}


class ToolResult(BaseModel):
    """工具执行结果。"""

    success: bool
    data: Any = None
    error: str | None = None
    execution_time: float = 0.0
