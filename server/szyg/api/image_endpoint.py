"""图像生成 API 端点。"""

from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from szyg.agent_core.image_router import ImageRouter
from szyg.media_storage import get_media_output_dir, media_url_for_path

router = APIRouter(prefix="/api/image", tags=["image"])

# Valid image sizes (Volcano Engine requires ≥ 3,686,400 pixels)
VALID_SIZES = ["1920x1920", "2560x1440", "1440x2560", "2048x2048", "2304x1728", "3072x1296"]

STYLE_PROMPTS = {
    "realistic": "photorealistic commercial photography, natural lighting, sharp details, realistic texture",
    "product": "e-commerce product photography, clean background, professional studio lighting, clear product focus, high conversion visual",
    "xiaohongshu_cover": "Xiaohongshu social media cover style, bright clean composition, lifestyle aesthetic, clear title space, eye-catching but polished",
    "douyin_cover": "Douyin short video thumbnail style, high contrast, strong visual hook, dynamic composition, clear subject, viral cover design",
    "anime": "anime illustration style, vibrant colors, clean line art, expressive composition",
    "oil": "oil painting style, textured brush strokes, classical art quality, rich color depth",
    "watercolor": "watercolor illustration style, soft gradients, paper texture, gentle natural colors",
    "cyberpunk": "cyberpunk style, neon lighting, futuristic city mood, cinematic contrast, synthwave atmosphere",
    "minimal": "minimalist design style, clean composition, generous whitespace, modern visual language",
}


def _resolve_url(path: str) -> str:
    """Convert local file path to HTTP URL."""
    media_url = media_url_for_path(path)
    if media_url != path:
        return media_url
    p = Path(path)
    if "volcengine_output" in path.replace("\\", "/"):
        resolved = Path(path).resolve()
        server_output = Path(__file__).resolve().parents[2] / "data" / "volcengine_output"
        if server_output in resolved.parents:
            return f"/api/files/server_volcengine_output/{p.name}"
        return f"/api/files/volcengine_output/{p.name}"
    return path  # fallback: return as-is


def _resolve_local_path(path: str) -> str:
    """Return an absolute local path that executors can pass to upload tools."""
    return str(Path(path).resolve())


def _apply_style(prompt: str, style: str) -> str:
    style_prompt = STYLE_PROMPTS.get((style or "none").strip())
    if not style_prompt:
        return prompt.strip()
    return f"{prompt.strip()}, {style_prompt}"


class GenerateRequest(BaseModel):
    prompt: str
    size: str = "1920x1920"
    count: int = Field(default=1, ge=1, le=4)
    style: str = "none"


@router.post("/generate")
async def generate_image(req: GenerateRequest):
    """AI 图像生成。火山引擎方舟 doubao-image 优先。"""
    if not req.prompt.strip():
        raise HTTPException(400, "prompt is required")

    size = req.size if req.size in VALID_SIZES else "1920x1920"
    final_prompt = _apply_style(req.prompt, req.style)

    # ── Try VolcEngine first ──
    try:
        from szyg.config.loader import load_config
        cfg = load_config()
        vc = cfg.get("llm", {}).get("volcengine", {})
        api_key = vc.get("api_key", "")
        ep = vc.get("endpoints", {}).get("doubao-image", "")

        if api_key and ep:
            from szyg.integrations.volcengine_client import VolcEngineClient
            client = VolcEngineClient(
                api_key=api_key,
                endpoints={"doubao-image": ep},
                output_dir=str(get_media_output_dir("image")),
            )
            paths = []
            for _ in range(req.count):
                path = await client.generate_image(
                    prompt=final_prompt,
                    model="doubao-image",
                    size=size,
                )
                paths.append(path)
            return {
                "backend": "volcengine",
                "images": [_resolve_url(path) for path in paths],
                "paths": [_resolve_local_path(path) for path in paths],
                "size": size,
                "count": len(paths),
                "final_prompt": final_prompt,
            }
    except Exception:
        import traceback
        print("[image_endpoint] VolcEngine failed, falling back to local:")
        traceback.print_exc()

    # Retry with prompt enhancement when the direct provider request failed.
    router = ImageRouter()
    try:
        results = []
        for _ in range(req.count):
            results.append(await router.generate(
                user_input=final_prompt,
                size=size,
            ))
        paths = [p for result in results for p in result["paths"]]
        first = results[0] if results else {}
        return {
            "backend": first.get("backend", "unknown"),
            "enhanced_prompt": first.get("enhanced_prompt", final_prompt),
            "final_prompt": final_prompt,
            "intent": first.get("intent", {}),
            "images": [_resolve_url(p) for p in paths],
            "paths": [_resolve_local_path(p) for p in paths],
            "count": len(paths),
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        await router.close()
