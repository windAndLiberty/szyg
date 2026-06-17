"""
火山引擎 ARK 图像生成客户端 — 豆包图像创作模型。

通过火山方舟 API 调用豆包图像生成模型（如 doubao-seedream 等）。
支持文生图，返回本地保存的文件路径。

用法:
    client = VolcanoEngineImageClient(api_key="your-api-key")
    path = await client.generate("一只金色的猫，赛博朋克风格")
"""

import asyncio
import os
import time
from pathlib import Path

import httpx

from szyg.models.common import IntegrationError


class VolcanoEngineImageClient:
    """火山引擎 ARK 图像生成客户端。

    调用火山方舟 OpenAI 兼容接口的 /images/generations 端点。
    支持同步生成、多尺寸、风格控制。
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://ark.cn-beijing.volces.com/api/v3",
        model: str = "doubao-seedream",
        timeout: float = 120.0,
    ):
        self.api_key = api_key or os.environ.get("VOLCANO_ENGINE_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
        style: str | None = None,
        n: int = 1,
        output_dir: str = "./data/volcano_output",
    ) -> list[str]:
        """生成图像，返回本地文件路径列表。

        Args:
            prompt: 图像描述（英文效果最佳）
            size: 图像尺寸，可选 1024x1024, 1024x1792, 1792x1024
            quality: 图像质量，standard 或 hd
            style: 图像风格，如 vivid, natural
            n: 生成数量（通常为 1）
            output_dir: 输出目录

        Returns:
            list[str]: 本地保存的图像文件路径列表
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
        }
        if style:
            payload["style"] = style

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(
                    f"{self.base_url}/images/generations",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

                paths = []
                timestamp = int(time.time())
                for i, item in enumerate(data.get("data", [])):
                    url = item.get("url")
                    if not url:
                        continue
                    # 下载图像
                    img_resp = await client.get(url)
                    img_resp.raise_for_status()
                    path = Path(output_dir) / f"volcano_img_{timestamp}_{i}.png"
                    path.write_bytes(img_resp.content)
                    paths.append(str(path))

                if not paths:
                    raise IntegrationError("VolcanoEngine image generation returned no images")
                return paths

        except httpx.HTTPStatusError as e:
            raise IntegrationError(f"VolcanoEngine image HTTP error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise IntegrationError(f"VolcanoEngine image generation failed: {e}")

    async def close(self):
        pass
