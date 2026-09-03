"""
C/S Client Engine — 本地算力模块
部署在 Windows 客户端，直连本地 Ollama / FFmpeg / Whisper
"""
import os, subprocess
from pathlib import Path

DATA_DIR = Path(os.environ.get("SZYG_DATA_DIR", "data"))
SERVER_URL = os.environ.get("SZYG_SERVER_URL", "http://localhost:8000")


class LocalAI:
    """Local AI engines — Ollama and Whisper."""

    @staticmethod
    def get_ollama_url() -> str:
        return os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    @staticmethod
    def is_ollama_running() -> bool:
        import socket, logging
        _log = logging.getLogger("szyg.client")
        s = socket.socket()
        try:
            s.settimeout(2)
            s.connect(("localhost", 11434))
            s.close()
            return True
        except (ConnectionRefusedError, OSError, TimeoutError):
            return False
        except Exception:
            _log.exception("Unexpected error checking Ollama health")
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
