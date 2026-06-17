"""
智能图像生成路由 — LLM意图识别 + Prompt增强 + 多后端调度。

流程:
  用户输入 ("画一只赛博朋克风格的猫咪")
    → LLM 意图识别: 提取主体/风格
    → Prompt 增强: 中文→英文 + 构图/光照/画质
    → 后端路由: ComfyUI(SD 2.1本地) > ModelScope(Z-Image-Turbo云端) > 降级
"""

from yuling.integrations.openrouter_client import OpenRouterClient


class ImageRouter:
    """智能图像生成路由器。ComfyUI 主 + ModelScope 降级。"""

    STYLE_TAGS = {
        "写实": "photorealistic, 8k, highly detailed",
        "赛博朋克": "cyberpunk, neon lights, futuristic, blade runner style",
        "动漫": "anime style, studio ghibli, vibrant colors",
        "水墨": "chinese ink painting, traditional, elegant brush strokes",
        "油画": "oil painting, classical, textured canvas",
        "极简": "minimalist, clean, simple composition",
        "3D": "3d render, c4d, octane, ray tracing",
        "像素": "pixel art, 16-bit, retro game style",
    }

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self.llm = OpenRouterClient()
        self._comfyui = None
        self._modelscope = None

    @property
    def comfyui(self):
        if self._comfyui is None:
            from yuling.integrations.comfyui_client import ComfyUIClient
            self._comfyui = ComfyUIClient()
        return self._comfyui

    @property
    def modelscope(self):
        if self._modelscope is None:
            from yuling.integrations.modelscope_image_client import ModelScopeImageClient
            self._modelscope = ModelScopeImageClient()
        return self._modelscope

    async def generate(
        self, user_input: str, style: str | None = None,
        size: str = "768*768", backend: str | None = None,
    ) -> dict:
        """智能图像生成。LLM增强prompt + ComfyUI优先 + ModelScope降级。"""
        intent = await self._analyze_intent(user_input, style)
        chosen = backend or self._select_backend()

        if chosen == "comfyui":
            try:
                path = await self.comfyui.generate(
                    prompt=intent["enhanced_prompt"],
                    negative=intent.get("negative", ""),
                )
                paths = [path]
            except Exception:
                paths = [await self.modelscope.generate(intent["enhanced_prompt"])]

        elif chosen == "modelscope":
            paths = [await self.modelscope.generate(intent["enhanced_prompt"])]
        else:
            paths = [await self.modelscope.generate(intent["enhanced_prompt"])]

        return {
            "backend": chosen,
            "enhanced_prompt": intent["enhanced_prompt"],
            "intent": {
                "subject": intent.get("subject", user_input),
                "style": intent.get("style", ""),
                "negative": intent.get("negative", ""),
            },
            "paths": paths,
        }

    async def _analyze_intent(self, user_input: str, style: str | None) -> dict:
        style_hint = f" 风格偏好: {style}" if style else ""
        resp = await self.llm.chat(messages=[{"role": "user", "content": f"""你是图像生成专家。分析用户输入并返回 JSON:

用户: "{user_input}"{style_hint}

返回格式:
{{
    "subject": "图像主体描述(中文)",
    "style": "风格标签(写实/赛博朋克/动漫/水墨/油画/极简/3D/像素)",
    "enhanced_prompt": "增强后的英文prompt(加入构图、光照、画质关键词，50-150词)",
    "negative": "否定提示词(不想出现的内容，英文)"
}}

只返回 JSON。"""}], max_tokens=500)

        content = resp["message"]["content"]
        import json
        try:
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"): content = content[4:]
            return json.loads(content)
        except (json.JSONDecodeError, KeyError):
            enhanced = f"{user_input}, high quality, detailed"
            if style:
                enhanced = f"{user_input}, {self.STYLE_TAGS.get(style, style)}"
            return {
                "subject": user_input, "style": style or "自动",
                "enhanced_prompt": enhanced,
                "negative": "ugly, blurry, low quality, distorted",
            }

    def _select_backend(self) -> str:
        try:
            import httpx
            r = httpx.get("http://localhost:8188/object_info", timeout=3)
            if r.status_code == 200: return "comfyui"
        except Exception:
            pass
        return "modelscope"

    async def list_styles(self) -> list[str]:
        return list(self.STYLE_TAGS.keys())

    async def close(self):
        await self.llm.close()
