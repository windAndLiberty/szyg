"""Local small-model runtime API."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from szyg.integrations.local_llama_runtime import get_local_llama_runtime
from szyg.integrations.local_small_model_client import LocalSmallModelClient
from szyg.integrations.local_task_router import get_local_task_router

router = APIRouter(prefix="/api/local-llm", tags=["local-llm"])


class LocalChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    system: str = "你是 szyg 的本地小模型助手，只处理简单、低风险任务。"
    model: str = "qwen3-4b"
    max_tokens: int = Field(512, ge=32, le=2048)


class LocalTaskRequest(BaseModel):
    task_type: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    max_tokens: int = Field(512, ge=32, le=2048)


@router.get("/status")
async def status():
    return await get_local_llama_runtime().status()


@router.post("/start")
async def start(model: str = "qwen3-4b"):
    return await get_local_llama_runtime().start(model)


@router.post("/stop")
async def stop():
    return await get_local_llama_runtime().stop()


@router.post("/chat")
async def chat(body: LocalChatRequest):
    runtime = get_local_llama_runtime()
    state = await runtime.status()
    if not state.get("runtime_ready"):
        started = await runtime.start(body.model)
        if not started.get("success"):
            return {"success": False, "message": started.get("message", "本地小模型未就绪"), "status": started.get("status", state)}
    client = LocalSmallModelClient(default_model=body.model)
    try:
        result = await client.chat(
            [
                {"role": "system", "content": body.system},
                {"role": "user", "content": body.prompt},
            ],
            max_tokens=body.max_tokens,
        )
        return {"success": True, "message": result.get("message", {}).get("content", ""), "model": result.get("model", body.model)}
    except Exception as exc:
        return {"success": False, "message": str(exc)}
    finally:
        await client.close()


@router.post("/task")
async def run_task(body: LocalTaskRequest):
    result = await get_local_task_router().run(body.task_type, body.text, max_tokens=body.max_tokens)
    return {"success": bool(result.get("content")), **result}


@router.post("/models/qwen3-8b/download")
async def download_qwen3_8b():
    return await get_local_llama_runtime().download_model("qwen3-8b")


@router.get("/models/download-status")
async def download_status():
    return get_local_llama_runtime().download_status()


@router.delete("/models/qwen3-8b")
async def delete_qwen3_8b():
    return await get_local_llama_runtime().delete_model("qwen3-8b")
