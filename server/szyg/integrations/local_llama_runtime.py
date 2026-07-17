"""Managed llama.cpp runtime for bundled local small models."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

import httpx

from szyg.data_path import DATA_DIR

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = Path(os.environ.get("SZYG_LOCAL_MODEL_DIR", DATA_DIR / "local_models"))
RUNTIME_DIR = Path(os.environ.get("SZYG_LLAMA_RUNTIME_DIR", REPO_ROOT / "runtime" / "llama"))
RUNTIME_LOG_DIR = DATA_DIR / "local_llm"
MANIFEST_PATH = MODEL_DIR / "manifest.json"
DOWNLOAD_STATUS_PATH = MODEL_DIR / "download_status.json"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = int(os.environ.get("SZYG_LLAMA_PORT", "11435"))
DEFAULT_BASE_URL = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/v1"

MODEL_MANIFEST: dict[str, dict[str, Any]] = {
    "qwen3-4b": {
        "id": "qwen3-4b",
        "label": "本地轻量模型",
        "repo": "Qwen/Qwen3-4B-GGUF",
        "quant": "Q4_K_M",
        "filename": "Qwen3-4B-Q4_K_M.gguf",
        "url": "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf",
        "bundled": True,
        "required": True,
        "expected_sha256": "",
    },
    "qwen3-8b": {
        "id": "qwen3-8b",
        "label": "本地增强模型",
        "repo": "Qwen/Qwen3-8B-GGUF",
        "quant": "Q4_K_M",
        "filename": "Qwen3-8B-Q4_K_M.gguf",
        "url": "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf",
        "bundled": False,
        "required": False,
        "expected_sha256": "",
    },
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _find_llama_server(root: Path) -> Path | None:
    direct = root / "llama-server.exe"
    if direct.exists():
        return direct
    if root.exists():
        for candidate in root.rglob("llama-server.exe"):
            return candidate
    return None


class LocalLlamaRuntime:
    """Starts and supervises a local llama-server child process."""

    def __init__(self) -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
        self._process: subprocess.Popen | None = None
        self._download_task: asyncio.Task | None = None

    @property
    def base_url(self) -> str:
        return os.environ.get("SZYG_LOCAL_LLAMA_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

    @property
    def port(self) -> int:
        try:
            return int(self.base_url.split(":")[-1].split("/")[0])
        except Exception:
            return DEFAULT_PORT

    def server_path(self) -> Path | None:
        selected = self.selected_runtime()
        return Path(selected["path"]) if selected.get("path") else None

    def _runtime_candidate(self, backend: str, root: Path) -> dict:
        server = _find_llama_server(root)
        return {
            "backend": backend,
            "available": server is not None,
            "path": str(server) if server else "",
            "root": str(root),
        }

    def runtime_candidates(self) -> dict[str, dict]:
        env_server = os.environ.get("SZYG_LLAMA_SERVER_PATH", "")
        env_path = Path(env_server) if env_server else None
        path_server = shutil.which("llama-server")
        legacy_paths = [
            REPO_ROOT / "runtime" / "llama" / "llama-server.exe",
            REPO_ROOT / "tools" / "llama" / "llama-server.exe",
            REPO_ROOT / "external" / "llama.cpp" / "llama-server.exe",
            REPO_ROOT / "external" / "llama.cpp" / "build" / "bin" / "Release" / "llama-server.exe",
            REPO_ROOT / "external" / "llama.cpp" / "build" / "bin" / "llama-server.exe",
        ]
        legacy_server = next((p for p in legacy_paths if p.exists()), None)
        return {
            "cpu": self._runtime_candidate("cpu", RUNTIME_DIR / "cpu"),
            "vulkan": self._runtime_candidate("vulkan", RUNTIME_DIR / "vulkan"),
            "env": {
                "backend": "custom",
                "available": bool(env_path and env_path.exists()),
                "path": str(env_path) if env_path and env_path.exists() else "",
                "root": str(env_path.parent) if env_path and env_path.exists() else "",
            },
            "legacy": {
                "backend": "legacy",
                "available": legacy_server is not None,
                "path": str(legacy_server) if legacy_server else str(path_server or ""),
                "root": str(legacy_server.parent) if legacy_server else "",
            },
            "path": {
                "backend": "path",
                "available": path_server is not None,
                "path": str(path_server or ""),
                "root": str(Path(path_server).parent) if path_server else "",
            },
        }

    def _gpu_summary(self) -> list[dict]:
        if os.name != "nt":
            return []
        try:
            command = "Get-CimInstance Win32_VideoController | Select-Object Name,AdapterRAM,DriverVersion,VideoProcessor | ConvertTo-Json -Compress"
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return []
            data = json.loads(result.stdout)
            items = data if isinstance(data, list) else [data]
            return [item for item in items if isinstance(item, dict)]
        except Exception:
            return []

    def vulkan_capability(self) -> dict:
        loader = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "vulkan-1.dll"
        gpus = self._gpu_summary()
        real_gpu = any(
            name
            and "microsoft basic" not in name.lower()
            and "remote display" not in name.lower()
            for name in (str(gpu.get("Name") or gpu.get("VideoProcessor") or "") for gpu in gpus)
        )
        return {
            "available": os.name == "nt" and loader.exists() and real_gpu,
            "loader_path": str(loader),
            "loader_exists": loader.exists(),
            "gpus": gpus,
        }

    def selected_runtime(self, prefer_backend: str | None = None) -> dict:
        candidates = self.runtime_candidates()
        mode = (prefer_backend or os.environ.get("SZYG_LLAMA_BACKEND", "auto")).strip().lower()
        if mode in {"gpu", "auto-gpu"}:
            mode = "vulkan"
        if candidates["env"]["available"]:
            return {**candidates["env"], "selection_mode": "env"}
        if mode in {"cpu", "vulkan"}:
            selected = candidates[mode]
            if selected["available"]:
                return {**selected, "selection_mode": mode}
            fallback = candidates["cpu"] if mode == "vulkan" else candidates["vulkan"]
            if fallback["available"]:
                return {**fallback, "selection_mode": f"{mode}_fallback"}
        capability = self.vulkan_capability()
        if capability["available"] and candidates["vulkan"]["available"]:
            return {**candidates["vulkan"], "selection_mode": "auto"}
        for key in ("cpu", "legacy", "path"):
            if candidates[key]["available"]:
                return {**candidates[key], "selection_mode": "auto"}
        return {"backend": "none", "available": False, "path": "", "root": "", "selection_mode": mode}

    def model_path(self, model_id: str) -> Path:
        meta = MODEL_MANIFEST.get(model_id, MODEL_MANIFEST["qwen3-4b"])
        return MODEL_DIR / meta["filename"]

    def _model_status(self, model_id: str) -> dict:
        meta = dict(MODEL_MANIFEST.get(model_id, {}))
        path = self.model_path(model_id)
        installed = path.exists()
        sha = ""
        valid = installed
        if installed and meta.get("expected_sha256"):
            try:
                sha = _sha256(path)
                valid = sha.lower() == str(meta["expected_sha256"]).lower()
            except Exception:
                valid = False
        return {
            **meta,
            "path": str(path),
            "installed": installed,
            "valid": valid,
            "size_bytes": path.stat().st_size if installed else 0,
            "sha256": sha,
        }

    async def health(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=3, proxy=None, trust_env=False) as client:
                response = await client.get(f"{self.base_url}/models")
                return {"ready": response.status_code == 200, "status_code": response.status_code}
        except Exception as exc:
            return {"ready": False, "error": str(exc)}

    async def status(self) -> dict:
        selected = self.selected_runtime()
        health = await self.health()
        process_running = self._process is not None and self._process.poll() is None
        models = {model_id: self._model_status(model_id) for model_id in MODEL_MANIFEST}
        manifest = _read_json(MANIFEST_PATH, {})
        return {
            "ok": True,
            "enabled": True,
            "base_url": self.base_url,
            "server": {
                "available": bool(selected.get("available")),
                "path": str(selected.get("path") or ""),
                "backend": selected.get("backend", "none"),
                "selection_mode": selected.get("selection_mode", "auto"),
                "process_running": process_running,
                "pid": self._process.pid if process_running and self._process else None,
                "log_path": str(RUNTIME_LOG_DIR / "llama-server.log"),
            },
            "runtimes": self.runtime_candidates(),
            "acceleration": {
                "mode": os.environ.get("SZYG_LLAMA_BACKEND", "auto"),
                "selected_backend": selected.get("backend", "none"),
                "vulkan": self.vulkan_capability(),
            },
            "runtime_ready": bool(health.get("ready")),
            "health": health,
            "current_model": manifest.get("current_model", "qwen3-4b"),
            "models": models,
            "download": self.download_status(),
        }

    async def start(self, model_id: str = "qwen3-4b") -> dict:
        if self._process is not None and self._process.poll() is None:
            return {"success": True, "message": "本地小模型已在运行", "status": await self.status()}
        selected = self.selected_runtime()
        if not selected.get("available"):
            return {"success": False, "error_code": "runtime_missing", "message": "本地模型运行组件未安装", "status": await self.status()}
        model_path = self.model_path(model_id)
        if not model_path.exists():
            return {"success": False, "error_code": "model_missing", "message": "本地模型文件未安装", "model": model_id, "status": await self.status()}

        result = await self._start_with_runtime(selected, model_id, model_path)
        if (
            not result.get("success")
            and selected.get("backend") == "vulkan"
            and self.runtime_candidates()["cpu"].get("available")
        ):
            await self.stop()
            cpu_runtime = self.selected_runtime("cpu")
            result = await self._start_with_runtime(cpu_runtime, model_id, model_path, fallback_from="vulkan")
        return result

    async def _start_with_runtime(self, runtime: dict, model_id: str, model_path: Path, fallback_from: str | None = None) -> dict:
        server = Path(str(runtime.get("path") or ""))
        log_path = RUNTIME_LOG_DIR / "llama-server.log"
        log = log_path.open("a", encoding="utf-8", errors="replace")
        args = [
            str(server),
            "--host",
            DEFAULT_HOST,
            "--port",
            str(self.port),
            "-m",
            str(model_path),
            "--alias",
            model_id,
            "--reasoning",
            "off",
            "-c",
            os.environ.get("SZYG_LLAMA_CTX", "4096"),
        ]
        try:
            self._process = subprocess.Popen(
                args,
                cwd=str(server.parent),
                stdout=log,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            _write_json(MANIFEST_PATH, {
                "current_model": model_id,
                "started_at": _now_ms(),
                "backend": runtime.get("backend", "unknown"),
                "fallback_from": fallback_from or "",
            })
            for _ in range(40):
                await asyncio.sleep(0.5)
                if self._process and self._process.poll() is not None:
                    break
                health = await self.health()
                if health.get("ready"):
                    message = "本地小模型已启动"
                    if fallback_from:
                        message = "显卡加速启动失败，已自动切换为基础模式"
                    return {"success": True, "message": message, "status": await self.status()}
            return {"success": False, "error_code": "runtime_not_ready", "message": "本地小模型启动中但暂未就绪", "status": await self.status()}
        except Exception as exc:
            return {"success": False, "error_code": "runtime_start_failed", "message": str(exc), "status": await self.status()}

    async def stop(self) -> dict:
        if self._process is None or self._process.poll() is not None:
            return {"success": True, "message": "本地小模型未运行", "status": await self.status()}
        pid = self._process.pid
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True, timeout=10)
            else:
                self._process.terminate()
                await asyncio.to_thread(self._process.wait, 10)
        except Exception:
            try:
                self._process.kill()
            except Exception:
                pass
        self._process = None
        return {"success": True, "message": "本地小模型已停止", "status": await self.status()}

    def download_status(self) -> dict:
        status = _read_json(DOWNLOAD_STATUS_PATH, {})
        if self._download_task is not None and not self._download_task.done():
            status["running"] = True
        return status or {"running": False, "status": "idle"}

    async def download_model(self, model_id: str = "qwen3-8b") -> dict:
        if model_id not in MODEL_MANIFEST:
            return {"success": False, "error_code": "unknown_model", "message": f"未知模型：{model_id}"}
        if self._download_task is not None and not self._download_task.done():
            return {"success": False, "error_code": "download_running", "message": "已有模型正在下载", "download": self.download_status()}
        self._download_task = asyncio.create_task(asyncio.to_thread(self._download_model_sync, model_id))
        return {"success": True, "message": "已开始下载增强模型", "download": self.download_status()}

    def _download_model_sync(self, model_id: str) -> None:
        meta = MODEL_MANIFEST[model_id]
        target = self.model_path(model_id)
        tmp = target.with_suffix(target.suffix + ".part")
        _write_json(DOWNLOAD_STATUS_PATH, {"running": True, "status": "downloading", "model": model_id, "received": 0, "total": 0, "updated_at": _now_ms()})
        try:
            req = urllib.request.Request(meta["url"], headers={"User-Agent": "szyg-local-llm"})
            with urllib.request.urlopen(req, timeout=30) as response:
                total = int(response.headers.get("Content-Length") or 0)
                received = 0
                with tmp.open("wb") as f:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        received += len(chunk)
                        _write_json(DOWNLOAD_STATUS_PATH, {
                            "running": True,
                            "status": "downloading",
                            "model": model_id,
                            "received": received,
                            "total": total,
                            "percent": round(received * 100 / total, 2) if total else 0,
                            "updated_at": _now_ms(),
                        })
            if meta.get("expected_sha256"):
                actual = _sha256(tmp)
                if actual.lower() != str(meta["expected_sha256"]).lower():
                    raise RuntimeError("模型校验失败")
            tmp.replace(target)
            _write_json(DOWNLOAD_STATUS_PATH, {"running": False, "status": "completed", "model": model_id, "path": str(target), "updated_at": _now_ms()})
        except Exception as exc:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            _write_json(DOWNLOAD_STATUS_PATH, {"running": False, "status": "failed", "model": model_id, "error": str(exc), "updated_at": _now_ms()})

    async def delete_model(self, model_id: str) -> dict:
        if model_id == "qwen3-4b":
            return {"success": False, "error_code": "protected_model", "message": "预装轻量模型不能在产品内删除"}
        path = self.model_path(model_id)
        try:
            path.unlink(missing_ok=True)
            return {"success": True, "message": "增强模型已删除", "status": await self.status()}
        except Exception as exc:
            return {"success": False, "error_code": "delete_failed", "message": str(exc), "status": await self.status()}


_runtime: LocalLlamaRuntime | None = None


def get_local_llama_runtime() -> LocalLlamaRuntime:
    global _runtime
    if _runtime is None:
        _runtime = LocalLlamaRuntime()
    return _runtime
