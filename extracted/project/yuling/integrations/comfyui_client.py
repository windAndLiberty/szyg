"""
ComfyUI 图像生成客户端 — SD 2.1 本地生图。

需要 ComfyUI 运行在 localhost:8188，模型 v2-1_768-ema-pruned.safetensors。

用法:
    client = ComfyUIClient()
    path = await client.generate("a cute cat, cyberpunk style")
"""

import asyncio
from pathlib import Path

import httpx

from yuling.models.common import IntegrationError


class ComfyUIClient:
    """ComfyUI 本地图像生成客户端（SD 2.1）。"""

    def __init__(
        self,
        api_url: str = "http://localhost:8188",
        output_dir: str = "./data/comfyui_output",
        checkpoint: str = "v2-1_768-ema-pruned.safetensors",
        timeout: float = 300.0,
    ):
        self.api_url = api_url.rstrip("/")
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint = checkpoint
        self.timeout = timeout
        self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def generate(
        self,
        prompt: str,
        negative: str = "",
        width: int = 768,
        height: int = 768,
        steps: int = 15,
        cfg: float = 7.5,
        seed: int | None = None,
    ) -> str:
        """生成图像，返回本地文件路径。

        SD 2.1 原生分辨率 768x768，GTX 1650 约 45-70s。
        减少 steps 可加速（15 步约 50s）。
        """
        import random
        if seed is None:
            seed = random.randint(0, 2**31)

        workflow = self._build_workflow(
            prompt=prompt,
            negative=negative or "ugly, blurry, low quality, distorted, bad anatomy, watermark",
            width=width, height=height,
            steps=steps, cfg=cfg, seed=seed,
        )

        pid = await self._queue(workflow)
        filename = await self._wait(pid)
        path = self._copy_to_output(filename)
        return str(path)

    def _build_workflow(self, prompt, negative, width, height, steps, cfg, seed):
        """构建 SD 2.1 完整工作流。"""
        return {
            "1": {"inputs": {"ckpt_name": self.checkpoint}, "class_type": "CheckpointLoaderSimple"},
            "2": {"inputs": {"text": prompt, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
            "3": {"inputs": {"text": negative, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
            "4": {"inputs": {"width": width, "height": height, "batch_size": 1}, "class_type": "EmptyLatentImage"},
            "5": {"inputs": {
                "seed": seed, "steps": steps, "cfg": float(cfg),
                "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0,
                "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0],
                "latent_image": ["4", 0],
            }, "class_type": "KSampler"},
            "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
            "7": {"inputs": {"filename_prefix": "yuling", "images": ["6", 0]}, "class_type": "SaveImage"},
        }

    async def _queue(self, workflow: dict) -> str:
        resp = await self.client.post(f"{self.api_url}/prompt", json={"prompt": workflow})
        resp.raise_for_status()
        return resp.json()["prompt_id"]

    async def _wait(self, prompt_id: str) -> str:
        """轮询直到生成完成，返回 filename。"""
        for _ in range(90):  # 最多 180s
            await asyncio.sleep(2)
            resp = await self.client.get(f"{self.api_url}/history/{prompt_id}")
            resp.raise_for_status()
            data = resp.json()
            if prompt_id in data:
                outputs = data[prompt_id]["outputs"]
                for out in outputs.values():
                    for img in out.get("images", []):
                        return img["filename"]
        raise IntegrationError("ComfyUI generation timed out")

    def _copy_to_output(self, filename: str) -> Path:
        """从 ComfyUI output 目录复制到项目 output 目录。"""
        src = Path(f"/home/bright/code/szyg/ComfyUI/output/{filename}")
        dst = self.output_dir / filename
        if src.exists():
            dst.write_bytes(src.read_bytes())
        return dst

    async def close(self):
        if self._client:
            await self._client.aclose()
