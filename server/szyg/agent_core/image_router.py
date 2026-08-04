"""
智能图像生成路由 — LLM意图识别 + Prompt增强 + 云端图像生成。

流程:
  用户输入 ("画一只赛博朋克风格的猫咪")
    → LLM 意图识别: 提取主体/风格
    → Prompt 增强: 中文→英文 + 构图/光照/画质
    → 云端图像生成服务
"""

import logging

from szyg.integrations.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class ImageRouter:
    """智能图像生成路由器。"""

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
        self.llm = OllamaClient()
        self._volcengine = None

    @property
    def volcengine(self):
        if self._volcengine is None:
            from szyg.integrations.volcengine_client import VolcEngineClient
            self._volcengine = VolcEngineClient()
        return self._volcengine

    async def generate(
        self, user_input: str, style: str | None = None,
        size: str = "768*768", backend: str | None = None,
    ) -> dict:
        """增强提示词并调用云端图像生成服务。"""
        intent = await self._analyze_intent(user_input, style)
        paths = [await self.volcengine.generate_image(intent["enhanced_prompt"])]

        return {
            "backend": "volcengine",
            "enhanced_prompt": intent["enhanced_prompt"],
            "intent": {
                "subject": intent.get("subject", user_input),
                "style": intent.get("style", ""),
                "negative": intent.get("negative", ""),
            },
            "paths": paths,
        }

    async def _analyze_intent(self, user_input: str, style: str | None) -> dict:
        """Analyze user intent via LLM. Falls back to direct prompt if LLM unavailable."""
        # Build direct prompt fallback (no LLM needed)
        direct_prompt = user_input
        if style and style in self.STYLE_TAGS:
            direct_prompt = f"{user_input}, {self.STYLE_TAGS[style]}"
        direct_result = {
            "subject": user_input,
            "style": style or "自动",
            "enhanced_prompt": direct_prompt,
            "negative": "ugly, blurry, low quality, distorted",
        }

        style_hint = f" 风格偏好: {style}" if style else ""
        try:
            resp = await self.llm.chat(messages=[{"role": "user", "content": f"""你是图像生成专家。分析用户输入并返回 JSON:

用户: "{user_input}"{style_hint}

返回格式:
{{
    "subject": "图像主体描述(中文)",
    "style": "风格标签(写实/赛博朋克/动漫/水墨/油画/极简/3D/像素)",
    "enhanced_prompt": "增强后的英文prompt(加入构图、光照、画质关键词，50-150词)",
    "negative": "否定提示词(不想出现的内容，英文)"
}}

只返回 JSON。"""}])

            content = resp["message"]["content"]
            import json
            try:
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"): content = content[4:]
                return json.loads(content)
            except (json.JSONDecodeError, KeyError):
                return direct_result
        except Exception as e:
            logger.debug("LLM prompt enhancement unavailable, using raw prompt: %s", e)
            return direct_result

    async def list_styles(self) -> list[str]:
        return list(self.STYLE_TAGS.keys())

    async def close(self):
        await self.llm.close()
