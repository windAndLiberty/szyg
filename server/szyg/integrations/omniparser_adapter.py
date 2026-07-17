"""OmniParser local service adapter for computer-use vision fallback.

OmniParser is intentionally isolated behind a small HTTP service. The main
FastAPI process should not import PyTorch/PaddleOCR or load model weights.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
OMNIPARSER_DIR = Path(os.environ.get("SZYG_OMNIPARSER_DIR", "")) if os.environ.get("SZYG_OMNIPARSER_DIR") else REPO_ROOT / "external" / "OmniParser-master"
OMNIPARSER_URL = os.environ.get("SZYG_OMNIPARSER_URL", "http://127.0.0.1:7862").rstrip("/")
OMNIPARSER_PYTHON = os.environ.get("SZYG_OMNIPARSER_PYTHON", "")
SERVICE_MODULE = "szyg.integrations.omniparser_service"
DEFAULT_OMNIPARSER_PYTHON = OMNIPARSER_DIR / ".venv" / "Scripts" / "python.exe"

REQUIRED_WEIGHTS = [
    "weights/icon_detect/model.pt",
    "weights/icon_detect/model.yaml",
    "weights/icon_detect/train_args.yaml",
    "weights/icon_caption_florence/config.json",
    "weights/icon_caption_florence/generation_config.json",
    "weights/icon_caption_florence/model.safetensors",
]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _request_json(method: str, url: str, payload: dict | None = None, timeout: float = 5.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return json.loads(raw or "{}")


def _bbox_to_bounds(bbox: Any, image_width: int = 0, image_height: int = 0) -> dict:
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return {}
    values = [float(item or 0) for item in bbox]
    if all(0 <= value <= 1 for value in values) and image_width and image_height:
        x1, y1, x2, y2 = values
        return {
            "x": int(x1 * image_width),
            "y": int(y1 * image_height),
            "width": int(max(x2 - x1, 0) * image_width),
            "height": int(max(y2 - y1, 0) * image_height),
        }
    x1, y1, x2, y2 = values
    width = x2 - x1 if x2 >= x1 else x2
    height = y2 - y1 if y2 >= y1 else y2
    return {"x": int(x1), "y": int(y1), "width": int(width), "height": int(height)}


def _role_from_item(item: dict) -> str:
    item_type = str(item.get("type") or "").lower()
    content = str(item.get("content") or item.get("label") or item.get("name") or "").lower()
    text = f"{item_type} {content}"
    if "text" in item_type:
        return "text"
    if any(key in text for key in ("button", "按钮", "submit", "发布", "确认", "取消")):
        return "button"
    if any(key in text for key in ("input", "textbox", "输入", "搜索", "标题")):
        return "input"
    if any(key in text for key in ("icon", "图标")):
        return "icon"
    if any(key in text for key in ("tab", "标签")):
        return "tab"
    return item_type or "vision"


def normalize_omniparser_elements(result: dict) -> list[dict]:
    """Convert OmniParser response into the computer-use element shape."""
    content_list = result.get("parsed_content_list") or []
    width = int(result.get("width") or 0)
    height = int(result.get("height") or 0)
    elements: list[dict] = []

    if isinstance(content_list, str):
        return elements

    for index, item in enumerate(content_list):
        if not isinstance(item, dict):
            continue
        content = item.get("content") or item.get("label") or item.get("name") or ""
        bbox = item.get("bbox") or item.get("box") or item.get("bounds")
        bounds = _bbox_to_bounds(bbox, width, height)
        if not bounds:
            continue
        confidence = float(item.get("confidence") or item.get("score") or 0.55)
        elements.append({
            "source": "vision",
            "index": str(item.get("idx") or item.get("index") or index + 1),
            "role": _role_from_item(item),
            "name": str(content),
            "bounds": bounds,
            "confidence": min(max(confidence, 0.0), 0.85),
            "selector": "",
        })
    return elements


class OmniParserProvider:
    """HTTP adapter and lightweight process manager for local OmniParser."""

    def __init__(self, source_dir: Path | None = None, url: str | None = None, python_path: str | None = None) -> None:
        self.source_dir = source_dir or OMNIPARSER_DIR
        self.url = (url or OMNIPARSER_URL).rstrip("/")
        self.python_path = python_path or OMNIPARSER_PYTHON or (str(DEFAULT_OMNIPARSER_PYTHON) if DEFAULT_OMNIPARSER_PYTHON.exists() else sys.executable)
        self._process: subprocess.Popen[str] | None = None

    def _missing_weights(self) -> list[str]:
        return [item for item in REQUIRED_WEIGHTS if not (self.source_dir / item).exists()]

    async def service_ready(self) -> bool:
        try:
            result = await asyncio.to_thread(_request_json, "GET", f"{self.url}/probe/", None, 2.0)
            return bool(result)
        except Exception:
            return False

    async def status(self) -> dict:
        source_available = self.source_dir.exists()
        missing_weights = self._missing_weights() if source_available else REQUIRED_WEIGHTS
        weights_ready = source_available and not missing_weights
        python_exists = bool(shutil.which(self.python_path) or Path(self.python_path).exists())
        service_ready = await self.service_ready() if python_exists else False
        available = source_available and weights_ready and service_ready

        if not source_available:
            message = "未发现 OmniParser 源码"
        elif not weights_ready:
            message = "已发现 OmniParser 源码，但模型权重未就绪"
        elif not python_exists:
            message = "OmniParser Python 解释器不可用"
        elif not service_ready:
            message = "OmniParser 服务未启动"
        else:
            message = "OmniParser 视觉兜底已就绪"

        return {
            "available": available,
            "source_available": source_available,
            "source_dir": str(self.source_dir),
            "url": self.url,
            "python": self.python_path,
            "python_available": python_exists,
            "weights_ready": weights_ready,
            "missing_weights": missing_weights,
            "service_ready": service_ready,
            "process_running": self._process is not None and self._process.poll() is None,
            "message": message,
        }

    async def start_service(self) -> dict:
        status = await self.status()
        if status["service_ready"]:
            return {"ok": True, "started": False, "message": "OmniParser 服务已运行", "status": status}
        if not status["source_available"] or not status["weights_ready"]:
            return {"ok": False, "started": False, "message": status["message"], "status": status}
        if self._process and self._process.poll() is None:
            return {"ok": True, "started": False, "message": "OmniParser 服务正在启动", "status": status}

        env = os.environ.copy()
        env["SZYG_OMNIPARSER_DIR"] = str(self.source_dir)
        env["SZYG_OMNIPARSER_URL"] = self.url
        env["PYTHONPATH"] = str(REPO_ROOT / "server") + os.pathsep + env.get("PYTHONPATH", "")
        self._process = subprocess.Popen(
            [self.python_path, "-m", SERVICE_MODULE],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        deadline = time.time() + int(os.environ.get("SZYG_OMNIPARSER_START_TIMEOUT", "180"))
        while time.time() < deadline:
            if await self.service_ready():
                return {"ok": True, "started": True, "message": "OmniParser 服务已启动", "status": await self.status()}
            await asyncio.sleep(0.5)
        return {"ok": False, "started": True, "message": "OmniParser 服务启动超时", "status": await self.status()}

    async def parse_image_file(self, image_path: str, auto_start: bool = True) -> dict:
        path = Path(image_path)
        if not path.exists() or not path.is_file():
            return {"ok": False, "error": "截图文件不存在", "elements": []}
        status = await self.status()
        if not status["service_ready"] and auto_start:
            await self.start_service()
            status = await self.status()
        if not status["service_ready"]:
            return {"ok": False, "error": status["message"], "status": status, "elements": []}

        started = _now_ms()
        image_bytes = path.read_bytes()
        image_base64 = base64.b64encode(image_bytes).decode("ascii")
        try:
            result = await asyncio.to_thread(
                _request_json,
                "POST",
                f"{self.url}/parse/",
                {"base64_image": image_base64},
                120.0,
            )
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            return {"ok": False, "error": f"OmniParser 解析失败：{exc}", "status": status, "elements": []}

        try:
            from PIL import Image
            import io

            with Image.open(io.BytesIO(image_bytes)) as image:
                result.setdefault("width", image.width)
                result.setdefault("height", image.height)
        except Exception:
            pass
        elements = normalize_omniparser_elements(result)
        return {
            "ok": True,
            "status": await self.status(),
            "elements": elements,
            "element_count": len(elements),
            "source_counts": {"vision": len(elements)} if elements else {},
            "latency_ms": _now_ms() - started,
            "som_image_base64": result.get("som_image_base64", ""),
        }


_provider: OmniParserProvider | None = None


def get_omniparser_provider() -> OmniParserProvider:
    global _provider
    if _provider is None:
        _provider = OmniParserProvider()
    return _provider
