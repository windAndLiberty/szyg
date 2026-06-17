"""
ModelScope 图像生成客户端 — Z-Image-Turbo。

通过 ModelScope Inference API 异步生图。

用法:
    client = ModelScopeImageClient()
    path = await client.generate("a golden cat")
"""

import asyncio
import os
import time
from pathlib import Path

import httpx


class ModelScopeImageClient:
    """ModelScope 图像生成客户端 (Z-Image-Turbo)。"""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "Tongyi-MAI/Z-Image-Turbo",
        timeout: float = 120.0,
    ):
        self.api_key = api_key or os.environ.get("MODELSCOPE_API_KEY", "")
        self.model = model
        self.timeout = timeout
        self.base = "https://api-inference.modelscope.cn/v1"

    async def generate(
        self, prompt: str, output_dir: str = "./data/output"
    ) -> str:
        """异步生成图像，返回本地路径。"""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-ModelScope-Async-Mode": "true",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as c:
            # 提交
            r = await c.post(
                f"{self.base}/images/generations",
                headers=headers,
                json={"model": self.model, "prompt": prompt},
            )
            r.raise_for_status()
            task_id = r.json()["task_id"]

            # 轮询
            task_headers = {**headers, "X-ModelScope-Task-Type": "image_generation"}
            for _ in range(60):
                await asyncio.sleep(3)
                r = await c.get(f"{self.base}/tasks/{task_id}", headers=task_headers)
                r.raise_for_status()
                data = r.json()
                if data["task_status"] == "SUCCEED":
                    url = data["output_images"][0]
                    img_r = await c.get(url)
                    path = Path(output_dir) / f"modelscope_{task_id[:8]}.png"
                    path.write_bytes(img_r.content)
                    return str(path)
                elif data["task_status"] == "FAILED":
                    raise RuntimeError(f"ModelScope generation failed: {data}")

            raise TimeoutError("ModelScope generation timed out")

    async def close(self):
        pass
