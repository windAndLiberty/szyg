"""通用模型和异常基类。"""

from pydantic import BaseModel


class SzygError(Exception):
    """szyg 系统基础异常。"""

    pass


class ConfigError(SzygError):
    """配置错误。"""

    pass


class ValidationError(SzygError):
    """验证错误。"""

    pass


class IntegrationError(SzygError):
    """集成错误。"""

    pass


class MCPError(SzygError):
    """MCP错误。"""

    pass


class MemoryError(SzygError):
    """记忆错误。"""

    pass


class SkillNotFoundError(SzygError):
    """技能未找到。"""

    pass


class DuplicateSkillError(SzygError):
    """重复技能。"""

    pass


class ServerNotFoundError(SzygError):
    """Server未找到。"""

    pass


class ToolTimeoutError(SzygError):
    """工具超时。"""

    pass


class AllBackendsFailedError(SzygError):
    """所有后端失败。"""

    pass


class ErrorResponse(BaseModel):
    """错误响应模型。"""

    detail: str
    error_code: str | None = None
