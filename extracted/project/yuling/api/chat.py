import time
import json
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter()


class ChatMessage(BaseModel):
    role: str = "user"
    content: str = ""


class ChatCompletionRequest(BaseModel):
    model: str = "qwen2.5"
    messages: list = Field(default_factory=list)
    stream: bool = False
    temperature: float = 0.7
    max_tokens: int = 4096


async def get_model_router():
    """获取模型路由器（依赖注入）"""
    from yuling.agent_core.model_router import ModelRouter

    return ModelRouter()


@router.post("/chat/completions", tags=["chat"])
async def chat_completions(
    request: ChatCompletionRequest, router=Depends(get_model_router)
):
    """OpenAI兼容的聊天补全端点"""
    if not request.messages:
        raise HTTPException(status_code=422, detail="messages is required")

    try:
        if request.stream:
            return StreamingResponse(
                _stream_response(request, router), media_type="text/event-stream"
            )
        else:
            response = await router.chat(
                messages=request.messages, model=request.model, stream=False
            )
            return {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": (
                                response.content
                                if hasattr(response, "content")
                                else str(response)
                            ),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                },
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _stream_response(request: ChatCompletionRequest, router):
    """流式响应生成器 — 直接使用 router.route_stream() 获取原始流。"""
    try:
        stream_gen = await router.route_stream(
            messages=request.messages, model=request.model
        )
        content_sent = False
        async for chunk in stream_gen:
            # chunk 格式: {"message": {"role": "assistant", "content": "text"}, "done": false}
            if isinstance(chunk, dict):
                msg = chunk.get("message", {})
                content = msg.get("content", "")
                done = chunk.get("done", False)
            elif hasattr(chunk, "content"):
                content = chunk.content
                done = False
            else:
                content = str(chunk)
                done = False

            # 跳过空内容（如 qwen3 模型的 thinking 阶段）
            if not content:
                continue

            content_sent = True
            data = {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": request.model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": content},
                        "finish_reason": "stop" if done else None,
                    }
                ],
            }
            yield f"data: {json.dumps(data)}\n\n"

        yield "data: [DONE]\n\n"
    except Exception as e:
        yield f'data: {{"error": "{str(e)}"}}\n\n'
