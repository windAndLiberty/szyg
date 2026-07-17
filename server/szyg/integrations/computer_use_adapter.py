"""Windows computer-use adapter.

This module keeps desktop automation behind a small local interface so Hermes,
FastAPI routes, and the execution kernel do not depend on a specific external
SDK. Terminator is the preferred backend for v1; lightweight Windows fallbacks
are used for observation so the UI remains useful before Terminator is installed.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from szyg.data_path import DATA_DIR
from szyg.integrations.browser_dom_provider import get_browser_dom_provider
from szyg.integrations.omniparser_adapter import get_omniparser_provider

REPO_ROOT = Path(__file__).resolve().parents[3]
TERMINATOR_DIR = Path(os.environ.get("SZYG_TERMINATOR_DIR", "")) if os.environ.get("SZYG_TERMINATOR_DIR") else REPO_ROOT / "external" / "terminator-main"
TERMINATOR_PY_DIR = TERMINATOR_DIR / "packages" / "terminator-python"
TERMINATOR_NODE_DIR = TERMINATOR_DIR / "packages" / "terminator-nodejs"
TERMINATOR_NODE_BRIDGE = Path(__file__).with_name("terminator_node_bridge.js")
ARTIFACT_DIR = DATA_DIR / "computer_use"
SCREENSHOT_DIR = ARTIFACT_DIR / "screenshots"

APP_ALIASES = {
    "notepad": "notepad.exe",
    "记事本": "notepad.exe",
    "explorer": "explorer.exe",
    "资源管理器": "explorer.exe",
    "chrome": "chrome.exe",
    "浏览器": "chrome.exe",
    "wechat": "WeChat.exe",
    "微信": "WeChat.exe",
    "jianying": "JianyingPro.exe",
    "剪映": "JianyingPro.exe",
}

SELECTOR_SHORTCUTS = {
    "document": "role:Document || role:Edit",
    "文档": "role:Document || role:Edit",
    "输入框": "role:Edit || role:Document || role:TextBox",
    "编辑框": "role:Edit || role:Document || role:TextBox",
    "按钮": "role:Button",
}


def _now() -> str:
    return datetime.now().isoformat()


def _powershell(script: str, timeout: int = 10) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )


def _has_broken_text(value: Any) -> bool:
    return isinstance(value, str) and "\ufffd" in value


def _item_has_broken_text(item: dict) -> bool:
    return _has_broken_text(item.get("title")) or _has_broken_text(item.get("name")) or _has_broken_text(item.get("process"))


def _terminator_python_paths() -> list[Path]:
    paths = [
        TERMINATOR_PY_DIR,
        TERMINATOR_PY_DIR / "target" / "debug",
        TERMINATOR_PY_DIR / "target" / "release",
        TERMINATOR_DIR / "target" / "debug",
        TERMINATOR_DIR / "target" / "release",
    ]
    return [path for path in paths if path.exists()]


def _load_terminator_module():
    for path in _terminator_python_paths():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)
    try:
        return importlib.import_module("terminator")
    except Exception:
        return None


async def _run_node_bridge(action: str, **payload: Any) -> dict:
    node = shutil.which("node")
    if not node or not TERMINATOR_NODE_BRIDGE.exists():
        return {"ok": False, "error": "node bridge unavailable"}
    data = json.dumps({"action": action, **payload}, ensure_ascii=False)
    try:
        process = await asyncio.create_subprocess_exec(
            node,
            str(TERMINATOR_NODE_BRIDGE),
            data,
            cwd=str(REPO_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        text = stdout.decode("utf-8", errors="replace").strip()
        if not text:
            return {"ok": False, "error": stderr.decode("utf-8", errors="replace").strip() or "empty node bridge response"}
        result = json.loads(text)
        if process.returncode != 0 and result.get("ok") is not False:
            result["ok"] = False
        if stderr:
            result["stderr"] = stderr.decode("utf-8", errors="replace")[-2000:]
        return result
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _bounds_to_dict(bounds: Any) -> dict:
    if not bounds:
        return {}
    return {
        "x": getattr(bounds, "x", 0),
        "y": getattr(bounds, "y", 0),
        "width": getattr(bounds, "width", 0),
        "height": getattr(bounds, "height", 0),
    }


def _element_to_dict(element: Any) -> dict:
    try:
        attrs = element.attributes()
    except Exception:
        attrs = None
    try:
        role = element.role()
    except Exception:
        role = getattr(attrs, "role", "") if attrs else ""
    try:
        name = element.name()
    except Exception:
        name = getattr(attrs, "name", "") if attrs else ""
    try:
        element_id = element.id()
    except Exception:
        element_id = ""
    try:
        bounds = element.bounds()
    except Exception:
        bounds = getattr(attrs, "bounds", None) if attrs else None
    try:
        pid = element.process_id()
    except Exception:
        pid = None
    return {
        "id": element_id,
        "name": name or "",
        "title": name or "",
        "role": role or "",
        "pid": pid,
        "bounds": _bounds_to_dict(bounds),
        "selector": _selector_for(role, name),
    }


def _selector_for(role: str | None, name: str | None) -> str:
    parts = []
    if role:
        parts.append(f"role:{role}")
    if name:
        safe_name = str(name).replace("'", "\\'")
        parts.append(f"name:{safe_name}")
    return " && ".join(parts)


def _node_to_dict(node: Any, depth: int = 0, max_depth: int = 2, limit: int = 40) -> dict:
    attrs = getattr(node, "attributes", None)
    item = {
        "id": getattr(node, "id", None),
        "role": getattr(attrs, "role", "") if attrs else "",
        "name": getattr(attrs, "name", "") if attrs else "",
        "bounds": _bounds_to_dict(getattr(attrs, "bounds", None) if attrs else None),
        "children": [],
    }
    if depth >= max_depth:
        return item
    children = getattr(node, "children", []) or []
    item["children"] = [_node_to_dict(child, depth + 1, max_depth, limit) for child in children[:limit]]
    return item


def _description_to_selector(description: str) -> str:
    desc = (description or "").strip()
    if not desc:
        return ""
    if ":" in desc or "&&" in desc or "||" in desc:
        return desc
    lowered = desc.lower()
    if lowered in SELECTOR_SHORTCUTS:
        return SELECTOR_SHORTCUTS[lowered]
    for key, selector in SELECTOR_SHORTCUTS.items():
        if key in desc:
            return selector
    safe = desc.replace("'", "\\'")
    return f"name:{safe}"


def _normalize_process_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name:
        return ""
    lower = name.lower()
    if lower.endswith(".exe"):
        return name[:-4]
    return name


def _window_process(item: dict) -> str:
    for key in ("process", "processName", "name"):
        value = _normalize_process_name(item.get(key))
        if value and not _has_broken_text(value):
            return value
    return ""


def _indexed_elements_from_mapping(mapping: dict, source: str = "uia", limit: int = 80) -> list[dict]:
    rows: list[dict] = []
    for raw_index, entry in list((mapping or {}).items())[:limit]:
        bounds = entry.get("bounds", {}) if isinstance(entry, dict) else {}
        name = (
            entry.get("name")
            or entry.get("text")
            or entry.get("label")
            or entry.get("elementType")
            or ""
        ) if isinstance(entry, dict) else ""
        role = (
            entry.get("role")
            or entry.get("tag")
            or entry.get("source")
            or source
        ) if isinstance(entry, dict) else source
        rows.append({
            "index": str(raw_index),
            "source": source,
            "role": role or source,
            "name": name or "",
            "bounds": bounds or {},
            "selector": entry.get("selector", "") if isinstance(entry, dict) else "",
        })
    return rows


def _source_counts(elements: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for item in elements:
        source = str(item.get("source") or "unknown")
        counts[source] = counts.get(source, 0) + 1
    return counts


def _merge_source_counts(*items: dict) -> dict:
    merged: dict[str, int] = {}
    for item in items:
        for key, value in (item or {}).items():
            merged[str(key)] = merged.get(str(key), 0) + int(value or 0)
    return merged


async def _fallback_list_windows() -> list[dict]:
    if os.name != "nt":
        return []
    script = (
        "Get-Process | Where-Object { $_.MainWindowTitle } | "
        "Select-Object Id,ProcessName,MainWindowTitle | ConvertTo-Json -Depth 2"
    )
    try:
        result = await asyncio.to_thread(_powershell, script)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        raw = json.loads(result.stdout)
        rows = raw if isinstance(raw, list) else [raw]
        return [
            {
                "pid": item.get("Id"),
                "process": item.get("ProcessName", ""),
                "title": item.get("MainWindowTitle", ""),
            }
            for item in rows
            if item.get("MainWindowTitle")
        ]
    except Exception:
        return []


async def _fallback_active_window() -> dict:
    if os.name != "nt":
        return {}
    script = r"""
Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;
public class Win32 {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);
}
"@
$h = [Win32]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 512
[void][Win32]::GetWindowText($h, $sb, $sb.Capacity)
$pid = 0
[void][Win32]::GetWindowThreadProcessId($h, [ref]$pid)
$proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
[PSCustomObject]@{ pid=$pid; process=$proc.ProcessName; title=$sb.ToString() } | ConvertTo-Json -Compress
"""
    try:
        result = await asyncio.to_thread(_powershell, script)
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        return json.loads(result.stdout)
    except Exception:
        return {}


def _repair_window_item(item: dict, fallback_by_pid: dict[int, dict]) -> dict:
    pid = item.get("pid")
    fallback = fallback_by_pid.get(pid) if isinstance(pid, int) else None
    if not fallback:
        return item
    repaired = dict(item)
    if _has_broken_text(repaired.get("title")) or not repaired.get("title"):
        repaired["title"] = fallback.get("title", repaired.get("title", ""))
    if _has_broken_text(repaired.get("name")) or not repaired.get("name"):
        repaired["name"] = fallback.get("title", repaired.get("name", ""))
    if _has_broken_text(repaired.get("process")) or not repaired.get("process"):
        repaired["process"] = fallback.get("process", repaired.get("process", ""))
    return repaired


async def _repair_windows(items: list[dict]) -> list[dict]:
    if not items or not any(_item_has_broken_text(item) for item in items):
        return items
    fallback = await _fallback_list_windows()
    fallback_by_pid = {
        item.get("pid"): item
        for item in fallback
        if isinstance(item.get("pid"), int)
    }
    return [_repair_window_item(item, fallback_by_pid) for item in items]


class ComputerUseAdapter:
    """Small facade for Windows desktop observation and controlled actions."""

    backend_name = "terminator"

    def __init__(self) -> None:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self._terminator = None
        self._desktop = None
        self._last_element = None
        self._last_selector = ""

    def _terminator_module(self):
        if self._terminator is None:
            self._terminator = _load_terminator_module()
        return self._terminator

    def _get_desktop(self):
        module = self._terminator_module()
        if not module:
            return None
        if self._desktop is None:
            self._desktop = module.Desktop(log_level="error")
        return self._desktop

    async def health(self) -> dict:
        omniparser_status = await get_omniparser_provider().status()
        playwright_status = await get_browser_dom_provider().health()
        is_windows = os.name == "nt"
        npx = shutil.which("npx")
        node = shutil.which("node")
        terminator_cmd = shutil.which("terminator")
        source_available = TERMINATOR_DIR.exists()
        python_paths = [str(path) for path in _terminator_python_paths()]
        python_package = self._terminator_module() is not None
        node_package_dir = TERMINATOR_NODE_DIR
        node_native_dir = node_package_dir / "node_modules" / "@mediar-ai"
        node_native_available = any(node_native_dir.glob("terminator-win32-*-msvc")) if node_native_dir.exists() else False
        node_ready = False
        node_error = ""
        desktop_ready = False
        import_error = ""
        try:
            desktop_ready = self._get_desktop() is not None
        except Exception as exc:
            import_error = str(exc)
        if not desktop_ready:
            bridge_health = await _run_node_bridge("health")
            node_ready = bool(bridge_health.get("ok"))
            node_error = bridge_health.get("error", "")
        available = is_windows and (desktop_ready or node_ready)
        return {
            "ok": True,
            "backend": self.backend_name,
            "available": available,
            "windows_only": True,
            "platform": os.name,
            "terminator": {
                "available": available,
                "source_available": source_available,
                "source_dir": str(TERMINATOR_DIR),
                "python_paths": python_paths,
                "command": bool(terminator_cmd),
                "npx": bool(npx),
                "node": bool(node),
                "python_package": python_package,
                "desktop_ready": desktop_ready,
                "import_error": import_error,
                "node_package_dir": str(node_package_dir),
                "node_native_available": node_native_available,
                "node_ready": node_ready,
                "node_error": node_error,
            },
            "vision_fallback": {
                "enabled": bool(omniparser_status.get("available")),
                "backend": "omniparser",
            },
            "providers": {
                "terminator": {
                    "available": available,
                    "message": self._health_message(available, source_available, python_package, import_error or node_error),
                },
                "playwright": playwright_status,
                "omniparser": omniparser_status,
            },
            "message": self._health_message(available, source_available, python_package, import_error or node_error),
        }

    async def list_windows(self) -> list[dict]:
        desktop = self._get_desktop()
        if desktop:
            try:
                apps = await asyncio.to_thread(desktop.applications)
                return await _repair_windows([
                    {
                        **_element_to_dict(app),
                        "process": _element_to_dict(app).get("name", ""),
                    }
                    for app in apps
                ])
            except Exception:
                pass
        node_result = await _run_node_bridge("applications")
        if node_result.get("ok"):
            return await _repair_windows([
                {
                    **item,
                    "process": item.get("process") or item.get("name", ""),
                    "title": item.get("title") or item.get("name", ""),
                }
                for item in node_result.get("applications", [])
            ])
        if os.name != "nt":
            return []
        return await _fallback_list_windows()

    async def active_window(self) -> dict:
        desktop = self._get_desktop()
        if desktop:
            try:
                element = await desktop.get_current_window()
                item = _element_to_dict(element)
                item["process"] = item.get("name", "")
                if _item_has_broken_text(item):
                    fallback = await _fallback_active_window()
                    item = _repair_window_item(item, {fallback.get("pid"): fallback})
                return item
            except Exception:
                pass
        node_result = await _run_node_bridge("current_window")
        if node_result.get("ok"):
            item = node_result.get("window", {})
            item["process"] = item.get("process") or item.get("name", "")
            item["title"] = item.get("title") or item.get("name", "")
            if _item_has_broken_text(item):
                fallback = await _fallback_active_window()
                item = _repair_window_item(item, {fallback.get("pid"): fallback})
            return item
        if os.name != "nt":
            return {}
        return await _fallback_active_window()

    async def screenshot(self) -> dict:
        path = SCREENSHOT_DIR / f"screen_{uuid.uuid4().hex[:10]}.png"
        try:
            from PIL import ImageGrab

            image = await asyncio.to_thread(ImageGrab.grab)
            image.save(path)
            return {"ok": True, "path": str(path), "created_at": _now()}
        except Exception as exc:
            return {"ok": False, "path": "", "message": str(exc), "created_at": _now()}

    async def window_tree(
        self,
        process: str = "",
        title: str = "",
        include_ocr: bool = True,
        include_browser_dom: bool = True,
        include_omniparser: bool = False,
        include_gemini_vision: bool = False,
        max_depth: int = 4,
    ) -> dict:
        target_process = _normalize_process_name(process)
        if not target_process:
            active = await self.active_window()
            target_process = _window_process(active)
            title = title or active.get("title", "")
        if not target_process:
            return {"ok": False, "error": "无法识别目标进程", "error_code": "missing_process"}
        result = await _run_node_bridge(
            "window_tree",
            process=target_process,
            title=title or None,
            include_ocr=include_ocr,
            include_browser_dom=include_browser_dom,
            include_omniparser=include_omniparser,
            include_gemini_vision=include_gemini_vision,
            max_depth=max_depth,
            output_format="CompactYaml",
        )
        if not result.get("ok"):
            return {**result, "process": target_process}
        payload = result.get("result", {})
        elements = _indexed_elements_from_mapping(payload.get("indexToBounds") or payload.get("index_to_bounds") or {}, "uia")
        return {
            "ok": True,
            "process": target_process,
            "title": title,
            "tree": payload.get("tree", {}),
            "formatted": payload.get("formatted", ""),
            "elements": elements,
            "element_count": payload.get("elementCount") or payload.get("element_count") or len(elements),
            "window_screenshot_path": payload.get("windowScreenshotPath") or payload.get("window_screenshot_path") or "",
            "monitor_screenshot_paths": payload.get("monitorScreenshotPaths") or payload.get("monitor_screenshot_paths") or [],
            "source_counts": _source_counts(elements),
        }

    async def clustered_tree(
        self,
        process: str = "",
        include_omniparser: bool = False,
        include_gemini_vision: bool = False,
    ) -> dict:
        target_process = _normalize_process_name(process)
        if not target_process:
            active = await self.active_window()
            target_process = _window_process(active)
        if not target_process:
            return {"ok": False, "error": "无法识别目标进程", "error_code": "missing_process"}
        result = await _run_node_bridge(
            "clustered_tree",
            process=target_process,
            include_omniparser=include_omniparser,
            include_gemini_vision=include_gemini_vision,
        )
        if not result.get("ok"):
            return {**result, "process": target_process}
        payload = result.get("result", {})
        mapping = payload.get("indexToSourceAndBounds") or payload.get("index_to_source_and_bounds") or {}
        elements = _indexed_elements_from_mapping(mapping, "clustered")
        return {
            "ok": True,
            "process": target_process,
            "formatted": payload.get("formatted", ""),
            "elements": elements,
            "element_count": len(elements),
            "source_counts": _source_counts(elements),
        }

    async def ocr_process(self, process: str = "") -> dict:
        target_process = _normalize_process_name(process)
        if not target_process:
            active = await self.active_window()
            target_process = _window_process(active)
        if not target_process:
            return {"ok": False, "error": "无法识别目标进程", "error_code": "missing_process"}
        result = await _run_node_bridge("ocr_process", process=target_process, format_output=True)
        if not result.get("ok"):
            return {**result, "process": target_process}
        payload = result.get("result", {})
        elements = _indexed_elements_from_mapping(payload.get("indexToBounds") or payload.get("index_to_bounds") or {}, "ocr")
        return {
            "ok": True,
            "process": target_process,
            "tree": payload.get("tree", {}),
            "formatted": payload.get("formatted", ""),
            "elements": elements,
            "element_count": payload.get("elementCount") or payload.get("element_count") or len(elements),
            "source_counts": _source_counts(elements),
        }

    async def browser_open(self, url: str) -> dict:
        return await get_browser_dom_provider().open_url(url)

    async def browser_observe(self) -> dict:
        return await get_browser_dom_provider().observe()

    async def plan_actions(self, payload: dict, observation: dict | None = None) -> dict:
        actions = []
        for item in payload.get("steps") or []:
            if isinstance(item, dict) and item.get("action"):
                actions.append(dict(item))
        if payload.get("url") and not any(item.get("action") == "open_url" for item in actions):
            actions.insert(0, {"action": "open_url", "url": payload.get("url"), "provider": "playwright"})
        target_selector = payload.get("target_selector") or ""
        text = payload.get("text") or ""
        if target_selector and text and not any(item.get("action") == "type" for item in actions):
            actions.append({"action": "type", "target": target_selector, "text": text, "provider": "playwright"})
        if payload.get("expected_result") and not any(item.get("action") == "verify" for item in actions):
            actions.append({"action": "verify", "value": payload.get("expected_result"), "provider": "auto"})
        if not actions and payload.get("target_app") and payload.get("target_app") != "windows":
            actions.append({"action": "launch_app", "target": payload.get("target_app"), "provider": "terminator"})
        if payload.get("target_app") in {"notepad", "记事本"} and payload.get("text") and not any(item.get("action") == "type" for item in actions):
            if not any(item.get("action") == "launch_app" for item in actions):
                actions.append({"action": "launch_app", "target": payload.get("target_app"), "provider": "terminator"})
            actions.append({"action": "type", "target": "process:notepad >> role:Document || process:notepad >> role:Edit", "text": payload.get("text"), "provider": "terminator"})
        return {
            "success": True,
            "actions": actions[: int(payload.get("max_steps") or 8)],
            "message": f"已生成 {min(len(actions), int(payload.get('max_steps') or 8))} 个受控动作",
            "observation_sources": (observation or {}).get("source_counts", {}),
        }

    async def execute_computer_actions(self, payload: dict, plan: dict | None = None) -> dict:
        planned_actions = list((plan or {}).get("actions") or [])
        if not planned_actions:
            planned_actions = (await self.plan_actions(payload)).get("actions", [])
        allowed = set(payload.get("allowed_actions") or [])
        results: list[dict] = []
        for action in planned_actions[: int(payload.get("max_steps") or 8)]:
            kind = str(action.get("action") or "").strip()
            if kind == "open_url":
                gate = "open_url"
            elif kind == "launch_app":
                gate = "launch"
            elif kind in {"click", "type", "hotkey", "upload_file", "wait_for", "verify", "observe"}:
                gate = kind
            else:
                return {"success": False, "message": f"不支持的动作：{kind}", "error_code": "unsupported_action", "actions": results}
            if gate not in allowed and kind != "verify":
                return {"success": False, "message": f"动作未被允许：{kind}", "error_code": "blocked_action", "actions": results}
            provider = action.get("provider") or self._route_provider(payload, action)
            if provider == "vision":
                return {"success": False, "message": "视觉候选动作需要人工确认，不能直接自动点击", "error_code": "low_confidence", "actions": results}
            if provider == "playwright":
                result = await get_browser_dom_provider().execute_action(action)
            else:
                result = await self._execute_desktop_action(action, payload)
            results.append({"action": kind, "provider": provider, **result})
            if not result.get("success"):
                return {**result, "actions": results}
        if not results:
            return {"success": True, "message": "已完成观察，未生成需要执行的动作", "actions": results}
        return {
            "success": all(item.get("success") for item in results),
            "message": "电脑使用动作已执行：" + "、".join(item.get("action", "action") for item in results),
            "actions": results,
        }

    def _route_provider(self, payload: dict, action: dict) -> str:
        if payload.get("url") or payload.get("target_app") in {"browser", "chrome"}:
            if action.get("selector") or action.get("target") or action.get("action") in {"open_url", "upload_file", "verify", "wait_for"}:
                return "playwright"
        if action.get("selector") and str(action.get("selector")).startswith(("#", ".", "[", "input", "button", "textarea", "select", "a")):
            return "playwright"
        return "terminator"

    async def _execute_desktop_action(self, action: dict, payload: dict) -> dict:
        kind = str(action.get("action") or "").strip()
        target = str(action.get("target") or action.get("selector") or "").strip()
        if kind == "launch_app":
            return await self.launch_app(target or payload.get("target_app", ""))
        if kind == "observe":
            observed = await self.observe()
            return {"success": bool(observed.get("ok")), "message": observed.get("summary", "已观察桌面"), "observation": observed}
        if kind == "click":
            return await self.click(target)
        if kind == "type":
            if target:
                found = await self.find_element(target)
                if not found.get("success"):
                    return found
            return await self.type_text(str(action.get("text") or action.get("value") or payload.get("text") or ""))
        if kind == "hotkey":
            keys = action.get("keys") or action.get("value") or []
            if isinstance(keys, str):
                keys = [item.strip() for item in keys.replace("+", ",").split(",") if item.strip()]
            return await self.hotkey(keys)
        if kind == "wait_for":
            await asyncio.sleep(float(action.get("seconds") or 1))
            return {"success": True, "message": "已等待桌面状态变化"}
        if kind == "verify":
            selector = target or str(action.get("value") or "")
            if not selector:
                return {"success": True, "message": "未配置桌面验证条件，已记录执行后观察"}
            return await self.verify_exists(selector)
        return {"success": False, "message": f"桌面不支持动作：{kind}", "error_code": "unsupported_action"}

    async def observe(self) -> dict:
        health, active, windows, screenshot = await asyncio.gather(
            self.health(),
            self.active_window(),
            self.list_windows(),
            self.screenshot(),
        )
        browser_result = await self.browser_observe()
        elements = list(browser_result.get("elements", [])) if browser_result.get("ok") else []
        tree = {}
        source_counts = dict(browser_result.get("source_counts", {})) if browser_result.get("ok") else {}
        formatted = ""
        primary_provider = "playwright" if elements else "fallback"
        target_process = _window_process(active)
        desktop = self._get_desktop()
        desktop_elements: list[dict] = []
        if desktop and active.get("pid"):
            try:
                tree_obj = await asyncio.to_thread(desktop.get_window_tree, int(active["pid"]), active.get("title") or None)
                tree = _node_to_dict(tree_obj)
                desktop_elements = _flatten_tree(tree)
                elements = [*elements, *desktop_elements]
                source_counts = _merge_source_counts(source_counts, _source_counts(desktop_elements))
                if primary_provider == "fallback":
                    primary_provider = "terminator"
            except Exception:
                desktop_elements = []
        elif target_process:
            tree_result = await self.window_tree(
                process=target_process,
                title=active.get("title", ""),
                include_ocr=True,
                include_browser_dom=True,
                include_omniparser=False,
                include_gemini_vision=False,
            )
            if tree_result.get("ok"):
                tree = tree_result.get("tree", {})
                desktop_elements = tree_result.get("elements", [])
                elements = [*elements, *desktop_elements]
                formatted = tree_result.get("formatted", "")
                source_counts = _merge_source_counts(source_counts, tree_result.get("source_counts", {}))
                if primary_provider == "fallback":
                    primary_provider = "terminator"
                if tree_result.get("window_screenshot_path") and not screenshot.get("ok"):
                    screenshot = {"ok": True, "path": tree_result.get("window_screenshot_path"), "created_at": _now()}
        vision_result = {}
        providers = health.get("providers", {})
        if screenshot.get("ok") and len(elements) < 3:
            try:
                vision_result = await get_omniparser_provider().parse_image_file(screenshot.get("path", ""), auto_start=True)
                if vision_result.get("ok") and vision_result.get("elements"):
                    vision_elements = vision_result.get("elements", [])
                    elements = [*elements, *vision_elements]
                    source_counts = _merge_source_counts(source_counts, vision_result.get("source_counts", {}))
                    if primary_provider == "fallback":
                        primary_provider = "vision"
            except Exception as exc:
                vision_result = {"ok": False, "error": str(exc), "elements": []}
        omniparser_status = vision_result.get("status")
        if omniparser_status:
            providers = {**providers, "omniparser": omniparser_status}
        return {
            "ok": True,
            "health": health,
            "providers": providers,
            "primary_provider": primary_provider,
            "active_window": active,
            "windows": windows,
            "screenshot": screenshot,
            "browser": browser_result,
            "elements": elements,
            "tree": tree,
            "formatted": formatted,
            "element_count": len(elements),
            "source_counts": source_counts,
            "vision": {
                "ok": bool(vision_result.get("ok")),
                "message": vision_result.get("error") or (vision_result.get("status") or {}).get("message", ""),
                "element_count": len(vision_result.get("elements", [])),
            },
            "summary": self._summarize_observation(active, windows, screenshot),
            "created_at": _now(),
        }

    async def launch_app(self, target_app: str) -> dict:
        command = APP_ALIASES.get((target_app or "").strip().lower()) or APP_ALIASES.get((target_app or "").strip())
        if not command:
            return {"success": False, "message": f"未知应用：{target_app}", "error_code": "unsupported_app"}
        desktop = self._get_desktop()
        if desktop:
            try:
                element = await asyncio.to_thread(desktop.open_application, command)
                await asyncio.sleep(1)
                return {
                    "success": True,
                    "message": f"已通过 Terminator 打开 {target_app}",
                    "command": command,
                    "element": _element_to_dict(element),
                    "engine": "terminator-python",
                }
            except Exception as exc:
                return {"success": False, "message": str(exc), "error_code": "launch_failed", "command": command, "engine": "terminator-python"}
        node_result = await _run_node_bridge("open_application", name=command)
        if node_result.get("ok"):
            await asyncio.sleep(1)
            return {
                "success": True,
                "message": f"已通过 Terminator 打开 {target_app}",
                "command": command,
                "element": node_result.get("element", {}),
                "engine": "terminator-nodejs",
            }
        if node_result.get("error") and "Cannot find module" not in node_result.get("error", ""):
            return {"success": False, "message": node_result.get("error", ""), "error_code": "launch_failed", "command": command, "engine": "terminator-nodejs"}
        try:
            subprocess.Popen([command], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await asyncio.sleep(1)
            return {"success": True, "message": f"已尝试打开 {target_app}", "command": command}
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "launch_failed", "command": command}

    async def find_element(self, description: str) -> dict:
        desktop = self._get_desktop()
        selector = _description_to_selector(description)
        if not desktop:
            node_result = await _run_node_bridge("find", selector=selector)
            if node_result.get("ok"):
                self._last_selector = selector
                return {
                    "success": True,
                    "message": f"已找到元素：{selector}",
                    "selector": selector,
                    "element": node_result.get("element", {}),
                    "engine": "terminator-nodejs",
                }
            return {
                "success": False,
                "message": node_result.get("error") or "Terminator binding 未就绪，无法进行结构化元素定位",
                "error_code": "desktop_backend_unavailable" if "Cannot find module" in node_result.get("error", "") else "low_confidence",
                "description": description,
                "selector": selector,
                "engine": "terminator-nodejs",
            }
        try:
            element = await desktop.locator(selector).first()
            self._last_element = element
            self._last_selector = selector
            return {
                "success": True,
                "message": f"已找到元素：{selector}",
                "selector": selector,
                "element": _element_to_dict(element),
                "engine": "terminator-python",
            }
        except Exception as exc:
            return {
                "success": False,
                "message": str(exc),
                "error_code": "low_confidence",
                "description": description,
                "selector": selector,
                "engine": "terminator-python",
            }

    async def click(self, description: str) -> dict:
        found = await self.find_element(description)
        if not found.get("success"):
            return {**found, "action": "click"}
        if found.get("engine") == "terminator-nodejs":
            node_result = await _run_node_bridge("click", selector=found.get("selector") or self._last_selector)
            if node_result.get("ok"):
                return {**found, "success": True, "message": "已通过 Terminator 点击目标元素", "action": "click", "click_result": node_result}
            return {**found, "success": False, "message": node_result.get("error", ""), "error_code": "click_failed", "action": "click"}
        try:
            result = await asyncio.to_thread(self._last_element.click)
            return {
                **found,
                "success": True,
                "message": "已通过 Terminator 点击目标元素",
                "action": "click",
                "click_result": str(result),
            }
        except Exception as exc:
            return {**found, "success": False, "message": str(exc), "error_code": "click_failed", "action": "click"}

    async def type_text(self, text: str) -> dict:
        if not text:
            return {"success": True, "message": "没有需要输入的文字"}
        desktop = self._get_desktop()
        if desktop:
            try:
                element = self._last_element
                if element is None:
                    try:
                        current = await desktop.get_current_window()
                        element = await current.locator("role:Document || role:Edit || role:TextBox").first()
                    except Exception:
                        element = desktop.focused_element()
                await asyncio.to_thread(element.type_text, text, True)
                self._last_element = element
                return {
                    "success": True,
                    "message": "已通过 Terminator 向目标控件输入文字",
                    "element": _element_to_dict(element),
                    "engine": "terminator-python",
                }
            except Exception as exc:
                return {"success": False, "message": str(exc), "error_code": "type_failed", "engine": "terminator-python"}
        node_result = await _run_node_bridge("type_text", text=text, selector=self._last_selector)
        if node_result.get("ok"):
            return {
                "success": True,
                "message": "已通过 Terminator 向目标控件输入文字",
                "element": node_result.get("element", {}),
                "engine": "terminator-nodejs",
            }
        if node_result.get("error") and "Cannot find module" not in node_result.get("error", ""):
            return {"success": False, "message": node_result.get("error", ""), "error_code": "type_failed", "engine": "terminator-nodejs"}
        if os.name != "nt":
            return {"success": False, "message": "仅支持 Windows", "error_code": "unsupported_platform"}
        escaped = text.replace("'", "''")
        script = f"$ws = New-Object -ComObject WScript.Shell; $ws.SendKeys('{escaped}')"
        try:
            result = await asyncio.to_thread(_powershell, script, 10)
            if result.returncode != 0:
                return {"success": False, "message": result.stderr.strip(), "error_code": "type_failed"}
            return {"success": True, "message": "已向当前窗口输入文字"}
        except Exception as exc:
            return {"success": False, "message": str(exc), "error_code": "type_failed"}

    async def hotkey(self, keys: list[str]) -> dict:
        desktop = self._get_desktop()
        key = "+".join(keys or [])
        if not key:
            return {"success": True, "message": "没有需要执行的快捷键", "keys": keys}
        if desktop:
            try:
                await desktop.press_key(key)
                return {"success": True, "message": f"已通过 Terminator 执行快捷键 {key}", "keys": keys, "engine": "terminator-python"}
            except Exception as exc:
                return {"success": False, "message": str(exc), "error_code": "hotkey_failed", "keys": keys, "engine": "terminator-python"}
        node_result = await _run_node_bridge("press_key", key=key)
        if node_result.get("ok"):
            return {"success": True, "message": f"已通过 Terminator 执行快捷键 {key}", "keys": keys, "engine": "terminator-nodejs"}
        if node_result.get("error") and "Cannot find module" not in node_result.get("error", ""):
            return {"success": False, "message": node_result.get("error", ""), "error_code": "hotkey_failed", "keys": keys, "engine": "terminator-nodejs"}
        return {"success": False, "message": "Terminator Python binding 未就绪，无法执行快捷键", "error_code": "desktop_backend_unavailable", "keys": keys}

    async def click_index(
        self,
        index: int,
        vision_type: str = "UiTree",
        process: str = "",
        x_percentage: int = 50,
        y_percentage: int = 50,
    ) -> dict:
        target_process = _normalize_process_name(process)
        node_result = await _run_node_bridge(
            "click_index",
            index=index,
            vision_type=vision_type,
            process=target_process or None,
            x_percentage=x_percentage,
            y_percentage=y_percentage,
        )
        if node_result.get("ok"):
            return {"success": True, "message": f"已点击观察索引 #{index}", "result": node_result.get("result", {}), "engine": "terminator-nodejs"}
        return {"success": False, "message": node_result.get("error", ""), "error_code": "click_failed", "engine": "terminator-nodejs"}

    async def click_bounds(self, bounds: dict, process: str = "") -> dict:
        target_process = _normalize_process_name(process)
        node_result = await _run_node_bridge("click_bounds", bounds=bounds, process=target_process or None)
        if node_result.get("ok"):
            return {"success": True, "message": "已点击指定屏幕区域", "result": node_result.get("result", {}), "engine": "terminator-nodejs"}
        return {"success": False, "message": node_result.get("error", ""), "error_code": "click_failed", "engine": "terminator-nodejs"}

    async def verify_exists(self, selector: str, timeout_ms: int = 3000, scope_selector: str = "") -> dict:
        node_result = await _run_node_bridge(
            "verify_exists",
            selector=_description_to_selector(selector),
            scope_selector=scope_selector or None,
            timeout_ms=timeout_ms,
        )
        if node_result.get("ok"):
            return {"success": True, "message": "已验证目标元素存在", "element": node_result.get("element", {}), "selector": node_result.get("selector", ""), "engine": "terminator-nodejs"}
        return {"success": False, "message": node_result.get("error", ""), "error_code": "verify_failed", "engine": "terminator-nodejs"}

    async def cleanup(self) -> dict:
        return {"success": True, "message": "desktop adapter cleaned up"}

    def _summarize_observation(self, active: dict, windows: list[dict], screenshot: dict) -> str:
        title = active.get("title") or "未识别前台窗口"
        count = len(windows)
        shot = "已截图" if screenshot.get("ok") else "未截图"
        return f"当前窗口：{title}；可见窗口 {count} 个；{shot}"

    def _health_message(self, available: bool, source_available: bool, python_package: bool, import_error: str) -> str:
        if available:
            return "Terminator 本机执行组件已就绪"
        if source_available and not python_package:
            return "已发现 Terminator 源码，但 Python binding 尚未构建或安装"
        if import_error:
            return f"Terminator 初始化失败：{import_error}"
        return "本机执行组件未就绪，可先使用观察能力"


def _flatten_tree(tree: dict, limit: int = 80) -> list[dict]:
    rows: list[dict] = []

    def walk(node: dict) -> None:
        if len(rows) >= limit:
            return
        rows.append({
            "id": node.get("id"),
            "source": "uia",
            "role": node.get("role", ""),
            "name": node.get("name", ""),
            "bounds": node.get("bounds", {}),
            "selector": _selector_for(node.get("role"), node.get("name")),
        })
        for child in node.get("children", []) or []:
            walk(child)

    if tree:
        walk(tree)
    return rows


_adapter: ComputerUseAdapter | None = None


def get_computer_use_adapter() -> ComputerUseAdapter:
    global _adapter
    if _adapter is None:
        _adapter = ComputerUseAdapter()
    return _adapter
