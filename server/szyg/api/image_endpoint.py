"""图像生成 API 端点。支持火山引擎方舟、ComfyUI 多后端。"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from szyg.agent_core.image_router import ImageRouter
from szyg.config.loader import load_config

router = APIRouter(prefix="/api/image", tags=["image"])

# Valid image sizes (Volcano Engine requires ≥ 3,686,400 pixels)
VALID_SIZES = ["1920x1920", "2560x1440", "1440x2560", "2048x2048", "2304x1728", "3072x1296"]


def _resolve_url(path: str) -> str:
    """Convert local file path to HTTP URL."""
    p = Path(path)
    # VolcEngine output
    if "volcengine_output" in path:
        return f"/api/files/volcengine_output/{p.name}"
    return path  # fallback: return as-is


class GenerateRequest(BaseModel):
    prompt: str
    size: str = "1920x1920"


@router.post("/generate")
async def generate_image(req: GenerateRequest):
    """AI 图像生成。火山引擎方舟 doubao-image 优先。"""
    if not req.prompt.strip():
        raise HTTPException(400, "prompt is required")

    size = req.size if req.size in VALID_SIZES else "1920x1920"

    # ── Try VolcEngine first ──
    try:
        import yaml
        cfg_path = Path(__file__).parent.parent.parent.parent / "config.yaml"
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        vc = cfg.get("llm", {}).get("volcengine", {})
        api_key = vc.get("api_key", "")
        ep = vc.get("endpoints", {}).get("doubao-image", "")

        if api_key and ep:
            from szyg.integrations.volcengine_client import VolcEngineClient
            client = VolcEngineClient(api_key=api_key, endpoints={"doubao-image": ep})
            path = await client.generate_image(
                prompt=req.prompt,
                model="doubao-image",
                size=size,
            )
            return {
                "backend": "volcengine",
                "images": [_resolve_url(path)],
                "size": size,
            }
    except Exception:
        import traceback
        print("[image_endpoint] VolcEngine failed, falling back to local:")
        traceback.print_exc()

    # ── Fallback: ImageRouter (ComfyUI / VolcEngine Seedream) ──
    router = ImageRouter()
    try:
        result = await router.generate(
            user_input=req.prompt,
            size=size,
        )
        return {
            "backend": result["backend"],
            "enhanced_prompt": result.get("enhanced_prompt", req.prompt),
            "intent": result.get("intent", {}),
            "images": [_resolve_url(p) for p in result["paths"]],
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await router.close()
