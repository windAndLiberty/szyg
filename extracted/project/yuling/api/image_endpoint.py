"""图像生成 API 端点。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from yuling.agent_core.image_router import ImageRouter
from yuling.config.loader import load_config

router = APIRouter(prefix="/api/image", tags=["image"])


class GenerateRequest(BaseModel):
    prompt: str
    style: str | None = None
    size: str = "1024*1024"
    backend: str | None = None


class StyleResponse(BaseModel):
    styles: list[str]


@router.get("/styles")
async def list_styles():
    """列出可用风格标签。"""
    r = ImageRouter()
    try:
        styles = await r.list_styles()
        return {"styles": styles}
    finally:
        await r.close()


@router.post("/generate")
async def generate_image(req: GenerateRequest):
    """智能图像生成。LLM 自动做意图识别和 prompt 增强。"""
    if not req.prompt.strip():
        raise HTTPException(400, "prompt is required")

    router = ImageRouter()
    try:
        result = await router.generate(
            user_input=req.prompt,
            style=req.style,
            size=req.size,
            backend=req.backend,
        )
        return {
            "backend": result["backend"],
            "enhanced_prompt": result["enhanced_prompt"],
            "intent": result["intent"],
            "images": result["paths"],
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await router.close()
