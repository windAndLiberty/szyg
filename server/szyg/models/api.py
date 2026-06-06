"""API请求/响应模型。"""

from pydantic import BaseModel


class ChatCompletionRequest(BaseModel):
    """聊天补全请求。"""

    model: str = "qwen2.5"
    messages: list[dict] = []
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 4096


class ChatCompletionResponse(BaseModel):
    """聊天补全响应。"""

    id: str = ""
    object: str = "chat.completion"
    created: int = 0
    model: str = ""
    choices: list[dict] = []
    usage: dict = {}


class ModelInfo(BaseModel):
    """模型信息。"""

    id: str
    object: str = "model"
    created: int = 0


class ModelListResponse(BaseModel):
    """模型列表响应。"""

    object: str = "list"
    data: list[ModelInfo] = []
