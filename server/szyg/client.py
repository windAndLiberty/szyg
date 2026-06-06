"""
C/S Client Engine — 本地算力模块
部署在 Windows 客户端，直连本地 Ollama / ComfyUI / FFmpeg / Whisper
"""
import os, json, subprocess, asyncio
from pathlib import Path
from typing import Optional

DATA_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data"))
SERVER_URL = os.environ.get("SZYG_SERVER_URL", "http://localhost:8000")


class LocalAI:
    """Local AI engines — Ollama, ComfyUI, Whisper"""

    @staticmethod
    def get_ollama_url() -> str:
        return os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    @staticmethod
    def get_comfyui_url() -> str:
        return os.environ.get("COMFYUI_HOST", "http://localhost:8188")

    @staticmethod
    def is_ollama_running() -> bool:
        import socket
        s = socket.socket()
        try:
            s.connect(("localhost", 11434))
            s.close()
            return True
        except:
            return False

    @staticmethod
    def is_comfyui_running() -> bool:
        import socket
        s = socket.socket()
        try:
            s.connect(("localhost", 8188))
            s.close()
            return True
        except:
            return False

    @staticmethod
    async def ollama_chat(prompt: str, model: str = "qwen3", system: str = "") -> str:
        """Call local Ollama for chat completion"""
        import httpx
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{LocalAI.get_ollama_url()}/api/chat", json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            })
            if resp.status_code == 200:
                return resp.json()["message"]["content"]
            raise Exception(f"Ollama error: {resp.status_code}")

    @staticmethod
    async def ollama_models() -> list[str]:
        """List available Ollama models"""
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{LocalAI.get_ollama_url()}/api/tags")
            if resp.status_code == 200:
                return [m["name"] for m in resp.json().get("models", [])]
            return []

    @staticmethod
    async def comfyui_generate(prompt: str, negative: str = "", steps: int = 15,
                                width: int = 768, height: int = 768) -> str:
        """Generate image via local ComfyUI SD 2.1"""
        import httpx, uuid, time
        workflow = {
            "3": {"class_type": "KSampler", "inputs": {
                "seed": int(time.time()), "steps": steps, "cfg": 7.5,
                "sampler_name": "euler", "scheduler": "normal",
                "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0],
                "negative": ["7", 0], "latent_image": ["5", 0]}},
            "4": {"class_type": "CheckpointLoaderSimple", "inputs": {
                "ckpt_name": "v2-1_768-ema-pruned.safetensors"}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {
                "width": width, "height": height, "batch_size": 1}},
            "6": {"class_type": "CLIPTextEncode", "inputs": {
                "text": prompt, "clip": ["4", 1]}},
            "7": {"class_type": "CLIPTextEncode", "inputs": {
                "text": negative or "ugly, blurry, low quality", "clip": ["4", 1]}},
            "8": {"class_type": "VAEDecode", "inputs": {
                "samples": ["3", 0], "vae": ["4", 2]}},
            "9": {"class_type": "SaveImage", "inputs": {
                "filename_prefix": "szyg", "images": ["8", 0]}},
        }
        client_id = str(uuid.uuid4())[:8]
        async with httpx.AsyncClient(timeout=300) as client:
            # Queue prompt
            r = await client.post(f"{LocalAI.get_comfyui_url()}/prompt",
                                   json={"prompt": workflow, "client_id": client_id})
            if r.status_code != 200:
                raise Exception(f"ComfyUI queue error: {r.text}")
            prompt_id = r.json()["prompt_id"]

            # Poll for result
            for _ in range(120):
                await asyncio.sleep(2)
                r = await client.get(f"{LocalAI.get_comfyui_url()}/history/{prompt_id}")
                if r.status_code == 200:
                    data = r.json()
                    if prompt_id in data:
                        outputs = data[prompt_id]["outputs"]
                        for node_id, output in outputs.items():
                            images = output.get("images", [])
                            if images:
                                img = images[0]
                                return f"{LocalAI.get_comfyui_url()}/view?filename={img['filename']}&subfolder={img.get('subfolder','')}&type={img['type']}"
            raise Exception("ComfyUI generation timed out")


class LocalRuntime:
    """Local tool execution engine"""

    def __init__(self):
        self._processes: dict[str, subprocess.Popen] = {}

    def launch(self, exe_path: str, cwd: str = "") -> subprocess.Popen:
        proc = subprocess.Popen(
            [exe_path], cwd=cwd or str(Path(exe_path).parent),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        self._processes[exe_path] = proc
        return proc

    def stop(self, exe_path: str):
        proc = self._processes.pop(exe_path, None)
        if proc:
            proc.terminate()

    def list_running(self) -> list[str]:
        return [k for k, v in self._processes.items() if v.poll() is None]


class ClientStatus:
    """Client health and capability check"""

    @staticmethod
    def get_all() -> dict:
        return {
            "ollama": LocalAI.is_ollama_running(),
            "ollama_url": LocalAI.get_ollama_url(),
            "comfyui": LocalAI.is_comfyui_running(),
            "comfyui_url": LocalAI.get_comfyui_url(),
            "ffmpeg": ClientStatus._check_ffmpeg(),
            "python": ClientStatus._check_python(),
            "os": os.name,
            "server_url": SERVER_URL,
        }

    @staticmethod
    def _check_ffmpeg() -> bool:
        import os, logging
        _log = logging.getLogger("szyg.client")
        candidates = [
            os.path.join("D:", os.sep, "tools", "ffmpeg", "bin", "ffmpeg.exe"),
            "ffmpeg",
        ]
        for exe in candidates:
            try:
                subprocess.run([exe, "-version"], capture_output=True, timeout=5, check=True)
                _log.info(f"ffmpeg found at: {exe}")
                return True
            except Exception as e:
                _log.debug(f"ffmpeg check failed for {exe}: {e}")
                continue
        return False

    @staticmethod
    def _check_python() -> str:
        import sys
        return sys.version


# Singleton
_runtime: LocalRuntime | None = None

def get_runtime() -> LocalRuntime:
    global _runtime
    if _runtime is None:
        _runtime = LocalRuntime()
    return _runtime
