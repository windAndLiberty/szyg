"""Lifecycle and authenticated IPC for the local Hermes agent runtime."""

from __future__ import annotations

import atexit
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import httpx


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class HermesProcessManager:
    """Own one loopback-only Hermes process for the desktop backend."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._port = 0
        self._token = ""
        self._contexts: dict[str, dict[str, Any]] = {}
        atexit.register(self.stop)

    @property
    def token(self) -> str:
        return self._token

    @property
    def base_url(self) -> str:
        if not self._port:
            return ""
        return f"http://127.0.0.1:{self._port}"

    @property
    def headers(self) -> dict[str, str]:
        return {"X-SZYG-Hermes-Token": self._token}

    def register_context(self, context: dict[str, Any]) -> str:
        context_id = secrets.token_urlsafe(24)
        with self._lock:
            self._contexts[context_id] = {**context, "created_at": time.time()}
            cutoff = time.time() - 24 * 3600
            self._contexts = {
                key: value
                for key, value in self._contexts.items()
                if float(value.get("created_at") or 0) >= cutoff
            }
        return context_id

    def get_context(self, context_id: str) -> dict[str, Any] | None:
        with self._lock:
            value = self._contexts.get(context_id)
            return dict(value) if value else None

    def release_context(self, context_id: str) -> None:
        with self._lock:
            self._contexts.pop(context_id, None)

    def _command(self) -> list[str]:
        if getattr(sys, "frozen", False):
            configured = os.environ.get("SZYG_HERMES_RUNTIME_EXECUTABLE", "").strip()
            runtime = Path(configured) if configured else Path(sys.executable).with_name("hermes-runtime.exe")
            if not runtime.is_file():
                raise RuntimeError("智能员工运行组件缺失，请重新安装应用")
            return [str(runtime)]
        entry = Path(__file__).resolve().parents[1] / "hermes_runtime_entry.py"
        isolated_python = entry.parent / ".hermes-venv" / "Scripts" / "python.exe"
        candidates = [isolated_python, Path(sys.executable)]
        checked: set[str] = set()
        for python in candidates:
            key = str(python.resolve()) if python.is_file() else str(python)
            if key in checked or not python.is_file():
                continue
            checked.add(key)
            if self._development_runtime_ready(python, entry.parent):
                return [str(python), str(entry)]
        raise RuntimeError(
            "智能员工开发环境依赖不完整，请安装 server/hermes-runtime-requirements.txt"
        )

    @staticmethod
    def _development_runtime_ready(python: Path, server_root: Path) -> bool:
        """Reject a stale isolated venv before it can stall every chat request."""
        vendor_root = server_root / "vendor" / "hermes_agent"
        probe = (
            "import sys; "
            f"sys.path[:0] = [{str(server_root)!r}, {str(vendor_root)!r}]; "
            "import httpx, pydantic_settings, uvicorn, yaml; "
            "import hermes_state, run_agent; "
            "from szyg.hermes_runtime_app import create_app"
        )
        try:
            result = subprocess.run(
                [str(python), "-c", probe],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def ensure_started(self) -> None:
        with self._lock:
            if self._process and self._process.poll() is None and self._healthy():
                return
            self.stop()
            self._port = _free_loopback_port()
            self._token = secrets.token_urlsafe(48)
            data_dir = Path(os.environ.get("SZYG_DATA_DIR", "data")).resolve()
            runtime_home = data_dir / "hermes"
            log_dir = data_dir / "logs"
            runtime_home.mkdir(parents=True, exist_ok=True)
            log_dir.mkdir(parents=True, exist_ok=True)
            internal_api_url = f"http://127.0.0.1:{os.environ.get('SZYG_BACKEND_PORT', '8000')}"
            env = os.environ.copy()
            env.update({
                "SZYG_HERMES_RUNTIME_PORT": str(self._port),
                "SZYG_HERMES_RUNTIME_TOKEN": self._token,
                "SZYG_HERMES_HOME": str(runtime_home),
                "HERMES_HOME": str(runtime_home),
                "SZYG_INTERNAL_API_URL": internal_api_url,
                "CUA_DRIVER_RS_TELEMETRY_ENABLED": "0",
                "OPENAI_BASE_URL": internal_api_url + "/api/internal/hermes/openai/v1",
                "OPENAI_API_KEY": self.token,
            })
            configured_cua = os.environ.get("SZYG_CUA_DRIVER_PATH", "").strip()
            if configured_cua:
                cua_driver = Path(configured_cua)
            else:
                repo_root = Path(__file__).resolve().parents[2]
                cua_driver = repo_root / "electron" / "providers" / "cua" / "cua-driver.exe"
            if cua_driver.is_file():
                env["HERMES_CUA_DRIVER_CMD"] = str(cua_driver)
            log = (log_dir / "hermes-runtime.log").open("a", encoding="utf-8", buffering=1)
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._process = subprocess.Popen(
                self._command(),
                cwd=str(data_dir),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                creationflags=creationflags,
            )
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if self._process.poll() is not None:
                    raise RuntimeError("智能员工运行组件启动失败")
                if self._healthy():
                    return
                time.sleep(0.25)
            self.stop()
            raise RuntimeError("智能员工运行组件启动超时")

    def _healthy(self) -> bool:
        if not self.base_url or not self._token:
            return False
        try:
            response = httpx.get(
                self.base_url + "/health",
                headers=self.headers,
                timeout=1.5,
                trust_env=False,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def stop(self) -> None:
        with self._lock:
            process, self._process = self._process, None
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            self._port = 0
            self._token = ""


hermes_process_manager = HermesProcessManager()
