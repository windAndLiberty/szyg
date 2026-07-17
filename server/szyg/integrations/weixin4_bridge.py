"""Read-only bridge for the newer Windows Weixin desktop client."""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MODERN_WEIXIN_CLASS = "mmui::MainWindow"
LEGACY_WECHAT_CLASS = "WeChatMainWndForPC"
WEIXIN_EXE_PATHS = [
    r"C:\Program Files\Tencent\Weixin\Weixin.exe",
    r"C:\Program Files (x86)\Tencent\Weixin\Weixin.exe",
    r"C:\Program Files\Tencent\WeChat\WeChat.exe",
    r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe",
    r"D:\Program Files\Tencent\Weixin\Weixin.exe",
    r"D:\Program Files\Tencent\WeChat\WeChat.exe",
]


@dataclass
class WeixinWindowInfo:
    found: bool
    client: str = ""
    title: str = ""
    class_name: str = ""
    handle: int = 0
    process_id: int = 0
    is_enabled: bool = False
    is_visible: bool = False
    rect: dict[str, int] = field(default_factory=dict)
    message: str = ""


@dataclass
class WeixinControlInfo:
    name: str = ""
    class_name: str = ""
    control_type: str = ""
    automation_id: str = ""
    handle: int = 0
    rect: dict[str, int] = field(default_factory=dict)


class Weixin4Bridge:
    """Small read-only facade for Weixin 4.x / mmui windows."""

    def __init__(self) -> None:
        self._uia: Any | None = None
        self._load_error = ""

    def _load_uia(self) -> Any | None:
        if self._uia is not None:
            return self._uia
        try:
            import uiautomation as uia

            self._uia = uia
            return uia
        except Exception as exc:
            self._load_error = str(exc)
            logger.debug("uiautomation import failed: %s", exc)
            return None

    def _first_existing_window(self) -> tuple[Any | None, str]:
        uia = self._load_uia()
        if uia is None:
            return None, ""

        candidates = [
            (MODERN_WEIXIN_CLASS, "weixin4"),
            (LEGACY_WECHAT_CLASS, "wechat3"),
        ]
        for class_name, client in candidates:
            try:
                window = uia.WindowControl(ClassName=class_name, searchDepth=1)
                if window.Exists(maxSearchSeconds=0.5):
                    return window, client
            except Exception as exc:
                logger.debug("Weixin window probe failed for %s: %s", class_name, exc)

        try:
            window = uia.WindowControl(Name="微信", searchDepth=1)
            if window.Exists(maxSearchSeconds=0.5):
                class_name = str(getattr(window, "ClassName", "") or "")
                client = "weixin4" if class_name == MODERN_WEIXIN_CLASS else "wechat"
                return window, client
        except Exception as exc:
            logger.debug("Weixin title probe failed: %s", exc)

        return None, ""

    def status(self) -> dict:
        window, client = self._first_existing_window()
        if window is None:
            return WeixinWindowInfo(
                found=False,
                message=self._load_error or "未找到微信桌面窗口",
            ).__dict__

        info = self._window_info(window, client)
        info.message = "微信桌面窗口已识别"
        return info.__dict__

    def observe(self, max_children: int = 80) -> dict:
        window, client = self._first_existing_window()
        if window is None:
            return {
                "found": False,
                "message": self._load_error or "未找到微信桌面窗口",
                "window": {},
                "controls": [],
                "input_candidates": [],
            }

        controls = self._collect_controls(window, max_children=max_children)
        input_candidates = [
            item for item in controls
            if item.get("control_type") in {"EditControl", "DocumentControl"}
            or item.get("class_name") in {"QWidget", "RichEditWnd"}
            or any(token in item.get("name", "") for token in ("输入", "消息", "编辑"))
        ]
        return {
            "found": True,
            "message": "微信桌面窗口已识别",
            "window": self._window_info(window, client).__dict__,
            "controls": controls,
            "input_candidates": input_candidates[:10],
        }

    def open_or_focus(self, wait_seconds: int = 12) -> dict:
        window, client = self._first_existing_window()
        if window is None:
            started = self._start_weixin()
            if not started:
                return {
                    "ok": False,
                    "message": "未找到微信安装路径，请先手动启动微信",
                    "window": self.status(),
                }
            deadline = time.time() + max(1, wait_seconds)
            while time.time() < deadline:
                time.sleep(0.5)
                window, client = self._first_existing_window()
                if window is not None:
                    break

        if window is None:
            return {
                "ok": False,
                "message": "微信已尝试启动，但暂未发现窗口",
                "window": self.status(),
            }

        focused = self._focus_window(window)
        return {
            "ok": True,
            "focused": focused,
            "message": "微信已打开，请在微信中确认当前账号",
            "window": self._window_info(window, client).__dict__,
        }

    def _window_info(self, window: Any, client: str) -> WeixinWindowInfo:
        return WeixinWindowInfo(
            found=True,
            client=client,
            title=str(getattr(window, "Name", "") or ""),
            class_name=str(getattr(window, "ClassName", "") or ""),
            handle=int(getattr(window, "NativeWindowHandle", 0) or 0),
            process_id=int(getattr(window, "ProcessId", 0) or 0),
            is_enabled=bool(self._safe_value(window, "IsEnabled", False)),
            is_visible=bool(self._safe_value(window, "IsVisible", True)),
            rect=self._rect_dict(getattr(window, "BoundingRectangle", None)),
        )

    def _start_weixin(self) -> bool:
        for path in WEIXIN_EXE_PATHS:
            p = Path(path)
            if not p.exists():
                continue
            try:
                subprocess.Popen([str(p)])
                return True
            except Exception as exc:
                logger.debug("start Weixin failed for %s: %s", p, exc)
        return False

    def _focus_window(self, window: Any) -> bool:
        try:
            window.SwitchToThisWindow()
            return True
        except Exception:
            pass
        try:
            window.SetActive()
            return True
        except Exception:
            pass
        try:
            window.SetFocus()
            return True
        except Exception as exc:
            logger.debug("focus Weixin failed: %s", exc)
            return False

    def _collect_controls(self, window: Any, max_children: int) -> list[dict]:
        result: list[dict] = []
        queue: list[tuple[Any, int]] = [(window, 0)]
        seen: set[int] = set()

        while queue and len(result) < max_children:
            control, depth = queue.pop(0)
            handle = int(getattr(control, "NativeWindowHandle", 0) or 0)
            identity = handle or id(control)
            if identity in seen:
                continue
            seen.add(identity)

            if depth > 0:
                result.append(self._control_info(control).__dict__ | {"depth": depth})

            if depth >= 3:
                continue

            try:
                children = control.GetChildren()
            except Exception as exc:
                logger.debug("GetChildren failed: %s", exc)
                children = []
            for child in children:
                queue.append((child, depth + 1))

        return result

    def _control_info(self, control: Any) -> WeixinControlInfo:
        return WeixinControlInfo(
            name=str(getattr(control, "Name", "") or ""),
            class_name=str(getattr(control, "ClassName", "") or ""),
            control_type=str(getattr(control, "ControlTypeName", "") or ""),
            automation_id=str(getattr(control, "AutomationId", "") or ""),
            handle=int(getattr(control, "NativeWindowHandle", 0) or 0),
            rect=self._rect_dict(getattr(control, "BoundingRectangle", None)),
        )

    @staticmethod
    def _rect_dict(rect_obj: Any) -> dict[str, int]:
        if not rect_obj:
            return {}
        try:
            return {
                "left": int(rect_obj.left),
                "top": int(rect_obj.top),
                "right": int(rect_obj.right),
                "bottom": int(rect_obj.bottom),
                "width": int(rect_obj.width()),
                "height": int(rect_obj.height()),
            }
        except Exception:
            return {}

    @staticmethod
    def _safe_value(obj: Any, attr_name: str, default: Any) -> Any:
        value = getattr(obj, attr_name, None)
        if value is None:
            return default
        if not callable(value):
            return value
        try:
            return value()
        except Exception:
            return default


def get_weixin4_bridge() -> Weixin4Bridge:
    return Weixin4Bridge()
