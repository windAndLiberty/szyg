"""Compatibility facade backed exclusively by the isolated computer-use runtime."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from szyg.data_path import DATA_DIR
from szyg.hermes_process_manager import hermes_process_manager


ARTIFACT_DIR = DATA_DIR / "computer_use"
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"
APP_ALIASES = {
    "notepad": "notepad.exe",
    "记事本": "notepad.exe",
    "explorer": "explorer.exe",
    "资源管理器": "explorer.exe",
    "chrome": "chrome.exe",
    "浏览器": "msedge.exe",
    "wechat": "WeChat.exe",
    "微信": "WeChat.exe",
    "jianying": "JianyingPro.exe",
    "剪映": "JianyingPro.exe",
}


def _now() -> str:
    return datetime.now().isoformat()


def _decode_result(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
        return parsed if isinstance(parsed, dict) else {"value": parsed}
    except json.JSONDecodeError:
        return {"error": str(value or "电脑操作未返回结果")}


def _image_from_result(result: dict[str, Any]) -> tuple[str, str]:
    for part in result.get("content") or []:
        if not isinstance(part, dict) or part.get("type") != "image_url":
            continue
        url = str((part.get("image_url") or {}).get("url") or "")
        if url.startswith("data:") and ";base64," in url:
            mime, encoded = url.split(";base64,", 1)
            return mime.removeprefix("data:"), encoded
    return "", ""


class ComputerUseAdapter:
    """Preserve existing product APIs while using one Cua execution source."""

    backend_name = "desktop"

    def __init__(self) -> None:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._last_elements: list[dict[str, Any]] = []

    async def _action(self, args: dict[str, Any], *, approved: bool = False) -> dict[str, Any]:
        await asyncio.to_thread(hermes_process_manager.ensure_started)
        async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
            response = await client.post(
                hermes_process_manager.base_url + "/v1/computer/action",
                headers=hermes_process_manager.headers,
                json={
                    "args": args,
                    "session_id": "szyg-computer-use",
                    "approved": approved,
                    "include_frame": args.get("action") == "capture",
                },
            )
        if response.status_code >= 400:
            return {"error": "电脑操作能力暂时不可用", "status_code": response.status_code}
        response_payload = response.json()
        result = _decode_result(response_payload.get("result"))
        frame = response_payload.get("frame") or {}
        image_url = str(frame.get("image_url") or "")
        if image_url:
            result["content"] = [{"type": "image_url", "image_url": {"url": image_url}}]
            result["text_summary"] = result.get("summary") or frame.get("content") or "已获取当前画面"
        return result

    async def health(self) -> dict[str, Any]:
        if os.name != "nt":
            return {
                "ok": True,
                "available": False,
                "platform": os.name,
                "backend": self.backend_name,
                "providers": {"desktop": {"available": False}},
                "message": "当前系统暂不支持电脑操作",
            }
        try:
            await asyncio.to_thread(hermes_process_manager.ensure_started)
            async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
                response = await client.get(
                    hermes_process_manager.base_url + "/v1/computer/status",
                    headers=hermes_process_manager.headers,
                )
            status = response.json() if response.status_code == 200 else {}
            available = bool(status.get("installed") and status.get("ready"))
            return {
                "ok": True,
                "available": available,
                "platform": os.name,
                "windows_only": True,
                "backend": self.backend_name,
                "providers": {"desktop": {"available": available}},
                "message": "电脑操作能力已就绪" if available else "电脑操作能力需要检查",
                "details": status,
            }
        except Exception as exc:
            return {
                "ok": True,
                "available": False,
                "platform": os.name,
                "backend": self.backend_name,
                "providers": {"desktop": {"available": False}},
                "message": "电脑操作能力暂时不可用",
                "error": str(exc)[:300],
            }

    async def list_windows(self) -> list[dict[str, Any]]:
        return list((await self._action({"action": "list_windows"})).get("windows") or [])

    async def active_window(self) -> dict[str, Any]:
        result = await self._action({"action": "capture", "mode": "ax", "max_elements": 1})
        return {
            "process": result.get("app") or "",
            "title": result.get("window_title") or "",
        }

    async def screenshot(self) -> dict[str, Any]:
        result = await self._action({"action": "capture", "mode": "vision"})
        mime, encoded = _image_from_result(result)
        if not encoded:
            return {"ok": False, "path": "", "message": result.get("error") or "未获取到桌面画面", "created_at": _now()}
        suffix = ".jpg" if "jpeg" in mime else ".png"
        path = SCREENSHOT_DIR / f"screen_{uuid.uuid4().hex[:10]}{suffix}"
        try:
            path.write_bytes(base64.b64decode(encoded))
        except (ValueError, OSError) as exc:
            return {"ok": False, "path": "", "message": str(exc), "created_at": _now()}
        return {"ok": True, "path": str(path), "created_at": _now(), "image_url": f"data:{mime};base64,{encoded}"}

    async def window_tree(self, process: str = "", title: str = "", **_: Any) -> dict[str, Any]:
        args: dict[str, Any] = {"action": "capture", "mode": "ax", "max_elements": 500}
        if process:
            args["app"] = process
        result = await self._action(args)
        self._last_elements = list(result.get("elements") or [])
        return {
            "ok": not bool(result.get("error")),
            "process": process or result.get("app") or "",
            "title": title or result.get("window_title") or "",
            "formatted": result.get("summary") or "",
            "elements": self._last_elements,
            "element_count": result.get("total_elements", len(self._last_elements)),
            "source_counts": {"desktop": len(self._last_elements)},
            "error": result.get("error", ""),
        }

    async def clustered_tree(self, process: str = "", **kwargs: Any) -> dict[str, Any]:
        return await self.window_tree(process=process, **kwargs)

    async def ocr_process(self, process: str = "") -> dict[str, Any]:
        return await self.window_tree(process=process)

    async def browser_open(self, url: str) -> dict[str, Any]:
        if not url.strip():
            return {"success": False, "ok": False, "message": "网页地址为空"}
        opened = await asyncio.to_thread(webbrowser.open, url, 2, True)
        return {
            "success": bool(opened),
            "ok": bool(opened),
            "message": "已在默认浏览器打开页面" if opened else "暂时无法打开页面",
        }

    async def browser_observe(self) -> dict[str, Any]:
        result = await self._action({"action": "cua_browser_state"})
        return {"ok": not bool(result.get("error")), **result}

    async def plan_actions(self, payload: dict[str, Any], observation: dict[str, Any] | None = None) -> dict[str, Any]:
        actions = [dict(item) for item in payload.get("steps") or [] if isinstance(item, dict) and item.get("action")]
        if payload.get("url") and not any(item.get("action") == "open_url" for item in actions):
            actions.insert(0, {"action": "open_url", "url": payload["url"]})
        if payload.get("target_app") not in {"", "windows", "browser", "chrome"} and not actions:
            actions.append({"action": "launch_app", "target": payload["target_app"]})
        if payload.get("text"):
            actions.append({"action": "type", "text": payload["text"]})
        return {
            "success": True,
            "actions": actions[: int(payload.get("max_steps") or 8)],
            "message": f"已生成 {min(len(actions), int(payload.get('max_steps') or 8))} 个受控动作",
            "observation_sources": (observation or {}).get("source_counts", {}),
        }

    async def execute_computer_actions(self, payload: dict[str, Any], plan: dict[str, Any] | None = None) -> dict[str, Any]:
        actions = list((plan or {}).get("actions") or [])
        if not actions:
            actions = (await self.plan_actions(payload)).get("actions", [])
        allowed = set(payload.get("allowed_actions") or [])
        results = []
        for action in actions[: int(payload.get("max_steps") or 8)]:
            kind = str(action.get("action") or "")
            gate = {"launch_app": "launch", "open_url": "open_url"}.get(kind, kind)
            if gate not in allowed and kind != "verify":
                return {"success": False, "message": f"动作未被允许：{kind}", "error_code": "blocked_action", "actions": results}
            result = await self._execute_action(action, payload)
            results.append({"action": kind, **result})
            if not result.get("success"):
                return {**result, "actions": results}
        return {"success": True, "message": "电脑操作已完成" if results else "已完成观察", "actions": results}

    async def _execute_action(self, action: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        kind = str(action.get("action") or "")
        if kind == "launch_app":
            return await self.launch_app(str(action.get("target") or payload.get("target_app") or ""))
        if kind == "open_url":
            return await self.browser_open(str(action.get("url") or payload.get("url") or ""))
        if kind == "click":
            element = action.get("element") or action.get("index")
            result = await self._action({"action": "click", "element": element}, approved=True)
        elif kind == "type":
            result = await self._action({"action": "type", "text": str(action.get("text") or payload.get("text") or "")}, approved=True)
        elif kind == "hotkey":
            keys = action.get("keys") or []
            result = await self._action({"action": "key", "keys": "+".join(keys) if isinstance(keys, list) else str(keys)}, approved=True)
        elif kind == "wait_for":
            result = await self._action({"action": "wait", "seconds": float(action.get("seconds") or 1)})
        elif kind == "verify":
            return await self.verify_exists(str(action.get("target") or action.get("value") or ""))
        elif kind == "observe":
            observed = await self.observe()
            return {"success": bool(observed.get("ok")), "message": observed.get("summary", "已观察桌面")}
        else:
            return {"success": False, "message": f"不支持的动作：{kind}", "error_code": "unsupported_action"}
        return {"success": not bool(result.get("error")), "message": result.get("error") or "动作已执行", "result": result}

    async def observe(self) -> dict[str, Any]:
        capture = await self._action({"action": "capture", "mode": "som", "max_elements": 200})
        self._last_elements = list(capture.get("elements") or [])
        screenshot = await self._save_capture(capture)
        active = {"process": capture.get("app") or "", "title": capture.get("window_title") or ""}
        windows = await self.list_windows()
        return {
            "ok": not bool(capture.get("error")),
            "health": await self.health(),
            "providers": {"desktop": {"available": not bool(capture.get("error"))}},
            "primary_provider": "desktop",
            "active_window": active,
            "windows": windows,
            "screenshot": screenshot,
            "elements": self._last_elements,
            "formatted": capture.get("text_summary") or capture.get("summary") or "",
            "element_count": capture.get("total_elements", len(self._last_elements)),
            "source_counts": {"desktop": len(self._last_elements)},
            "summary": f"当前窗口：{active.get('title') or '未识别'}；可见窗口 {len(windows)} 个",
            "created_at": _now(),
        }

    async def _save_capture(self, result: dict[str, Any]) -> dict[str, Any]:
        mime, encoded = _image_from_result(result)
        if not encoded:
            return {"ok": False, "path": "", "message": result.get("error") or "未获取到桌面画面"}
        suffix = ".jpg" if "jpeg" in mime else ".png"
        path = SCREENSHOT_DIR / f"screen_{uuid.uuid4().hex[:10]}{suffix}"
        await asyncio.to_thread(path.write_bytes, base64.b64decode(encoded))
        return {"ok": True, "path": str(path), "image_url": f"data:{mime};base64,{encoded}", "created_at": _now()}

    async def launch_app(self, target_app: str) -> dict[str, Any]:
        command = APP_ALIASES.get(target_app.strip().lower()) or APP_ALIASES.get(target_app.strip())
        if not command:
            return {"success": False, "message": f"暂不支持打开：{target_app}", "error_code": "unsupported_app"}
        try:
            subprocess.Popen([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(1)
            result = await self._action({"action": "focus_app", "app": Path(command).stem, "raise_window": True}, approved=True)
            return {"success": not bool(result.get("error")), "message": result.get("error") or f"已打开 {target_app}", "result": result}
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "launch_failed"}

    async def find_element(self, description: str) -> dict[str, Any]:
        needle = description.strip().lower()
        for position, item in enumerate(self._last_elements, start=1):
            haystack = " ".join(str(item.get(key) or "") for key in ("name", "label", "role", "value")).lower()
            if needle and needle in haystack:
                return {"success": True, "message": "已找到目标元素", "index": item.get("index") or position, "element": item}
        refreshed = await self.window_tree()
        if refreshed.get("ok") and self._last_elements:
            return await self.find_element(description) if any(needle in " ".join(str(v) for v in item.values()).lower() for item in self._last_elements) else {"success": False, "message": "未找到目标元素", "error_code": "low_confidence"}
        return {"success": False, "message": "未找到目标元素", "error_code": "low_confidence"}

    async def click(self, description: str) -> dict[str, Any]:
        found = await self.find_element(description)
        if not found.get("success"):
            return found
        result = await self._action({"action": "click", "element": found["index"]})
        return {"success": not bool(result.get("error")), "message": result.get("error") or "已点击目标元素", "result": result}

    async def type_text(self, text: str) -> dict[str, Any]:
        result = await self._action({"action": "type", "text": text})
        return {"success": not bool(result.get("error")), "message": result.get("error") or "已输入文字", "result": result}

    async def hotkey(self, keys: list[str]) -> dict[str, Any]:
        result = await self._action({"action": "key", "keys": "+".join(keys or [])})
        return {"success": not bool(result.get("error")), "message": result.get("error") or "已执行快捷键", "result": result}

    async def click_index(self, index: int, **_: Any) -> dict[str, Any]:
        result = await self._action({"action": "click", "element": index})
        return {"success": not bool(result.get("error")), "message": result.get("error") or f"已点击元素 #{index}", "result": result}

    async def click_bounds(self, bounds: dict[str, Any], process: str = "") -> dict[str, Any]:
        x = int(bounds.get("x", bounds.get("left", 0))) + int(bounds.get("width", 0)) // 2
        y = int(bounds.get("y", bounds.get("top", 0))) + int(bounds.get("height", 0)) // 2
        result = await self._action({"action": "click", "coordinate": [x, y]})
        return {"success": not bool(result.get("error")), "message": result.get("error") or "已点击指定区域", "result": result}

    async def verify_exists(self, selector: str, timeout_ms: int = 3000, scope_selector: str = "") -> dict[str, Any]:
        del scope_selector
        deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
        while asyncio.get_running_loop().time() < deadline:
            result = await self.find_element(selector)
            if result.get("success"):
                return {**result, "message": "已验证目标元素存在"}
            await asyncio.sleep(0.25)
        return {"success": False, "message": "未找到目标元素", "error_code": "verify_failed"}

    async def cleanup(self) -> dict[str, Any]:
        return {"success": True, "message": "电脑操作会话已整理"}


_adapter: ComputerUseAdapter | None = None


def get_computer_use_adapter() -> ComputerUseAdapter:
    global _adapter
    if _adapter is None:
        _adapter = ComputerUseAdapter()
    return _adapter
