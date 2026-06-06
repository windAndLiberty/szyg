"""模型相关模型。"""

from typing import Literal

from pydantic import BaseModel


class ChatMessage(BaseModel):
    """聊天消息。"""

    role: Literal["system", "user", "assistant"]
    content: str
    name: str | None = None


class ModelResponse(BaseModel):
    """模型响应。"""

    content: str
    model: str = ""
    usage: dict = {}
    finish_reason: str = "stop"


class StreamingChunk(BaseModel):
    """流式响应块。"""

    content: str
    model: str = ""
    finish_reason: str | None = None


class BackendInfo(BaseModel):
    """后端信息。"""

    name: str
    backend_type: str
    base_url: str
    default_model: str
    available_models: list[str] = []
    priority: int = 1
