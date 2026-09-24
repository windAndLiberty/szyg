"""集成结果模型。"""

from typing import Any

from pydantic import BaseModel


class TranscriptionResult(BaseModel):
    """语音识别结果。"""

    text: str
    language: str = "zh"
    confidence: float = 1.0
    segments: list[dict] = []


class GenerationResult(BaseModel):
    """生成结果。"""

    success: bool
    prompt_id: str | None = None
    image_data: bytes | None = None
    image_url: str | None = None
    error: str | None = None


class BatchResult(BaseModel):
    """批处理结果。"""

    success: bool
    output_files: list[str] = []
    errors: list[str] = []
    total: int = 0
    completed: int = 0


class ChatResponse(BaseModel):
    """聊天响应。"""

    message: dict = {}
    model: str = ""
    done: bool = True


class GenerateResponse(BaseModel):
    """生成响应。"""

    response: str = ""
    model: str = ""
    done: bool = True


class CompletionResponse(BaseModel):
    """补全响应。"""

    choices: list[dict] = []
    model: str = ""
    usage: dict = {}
