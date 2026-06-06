"""通用模型和异常基类。"""

from pydantic import BaseModel


class YuLingError(Exception):
    """域灵系统基础异常。"""

    pass


class ConfigError(YuLingError):
    """配置错误。"""

    pass


class ValidationError(YuLingError):
    """验证错误。"""

    pass


class IntegrationError(YuLingError):
    """集成错误。"""

    pass


class MCPError(YuLingError):
    """MCP错误。"""

    pass


class MemoryError(YuLingError):
    """记忆错误。"""

    pass


class SkillNotFoundError(YuLingError):
    """技能未找到。"""

    pass


class DuplicateSkillError(YuLingError):
    """重复技能。"""

    pass


class ServerNotFoundError(YuLingError):
    """Server未找到。"""

    pass


class ToolTimeoutError(YuLingError):
    """工具超时。"""

    pass


class AllBackendsFailedError(YuLingError):
    """所有后端失败。"""

    pass


class ErrorResponse(BaseModel):
    """错误响应模型。"""

    detail: str
    error_code: str | None = None
