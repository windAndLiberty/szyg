"""「域灵」数字员工系统 - 数据模型包"""

from szyg.models.common import (
    AllBackendsFailedError,
    ConfigError,
    DuplicateSkillError,
    ErrorResponse,
    IntegrationError,
    MCPError,
    ServerNotFoundError,
    SkillNotFoundError,
    ToolTimeoutError,
    ValidationError,
    YuLingError,
)
from szyg.models.integration import (
    BatchResult,
    ChatResponse,
    CompletionResponse,
    GenerationResult,
    GenerateResponse,
    TranscriptionResult,
)
from szyg.models.mcp import MCPServerConfig, Tool, ToolResult
from szyg.models.model import BackendInfo, ChatMessage, ModelResponse, StreamingChunk
from szyg.models.skill import Skill, SkillParameter, SkillResult
from szyg.models.task import TaskPlan, TaskStep

__all__ = [
    # common
    "YuLingError",
    "ServerNotFoundError",
    "MCPError",
    "ToolTimeoutError",
    "IntegrationError",
    "ValidationError",
    "ConfigError",
    "SkillNotFoundError",
    "DuplicateSkillError",
    "AllBackendsFailedError",
    "ErrorResponse",
    # mcp
    "MCPServerConfig",
    "Tool",
    "ToolResult",
    # integration
    "TranscriptionResult",
    "GenerationResult",
    "BatchResult",
    "ChatResponse",
    "GenerateResponse",
    "CompletionResponse",
    # model
    "ChatMessage",
    "ModelResponse",
    "StreamingChunk",
    "BackendInfo",
    # skill
    "Skill",
    "SkillParameter",
    "SkillResult",
    # task
    "TaskPlan",
    "TaskStep",
]
