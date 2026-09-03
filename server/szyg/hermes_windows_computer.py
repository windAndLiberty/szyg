"""Windows execution backend for Hermes' native ``computer_use`` tool.

The upstream Cua Windows runtime is bundled and integrity checked, but its
window/UIA enumeration can block indefinitely on some Windows builds.  This
backend keeps the Hermes tool schema and safety gates while using bounded
Win32 primitives for the operations that must remain dependable in SZYG.
"""

from __future__ import annotations

import base64
import ctypes
import io
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw, ImageGrab
from tools.computer_use.backend import ActionResult, CaptureResult, ComputerUseBackend, UIElement


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

SW_RESTORE = 9
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x01000


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG)),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", INPUTUNION)]


def _process_name(pid: int) -> str:
    try:
        import psutil

        return psutil.Process(pid).name()
    except Exception:
        handle = kernel32.OpenProcess(0x1000, False, int(pid))
        if handle:
            try:
                size = wintypes.DWORD(32768)
                buffer = ctypes.create_unicode_buffer(size.value)
                if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                    return os.path.basename(buffer.value) or f"pid-{pid}"
            finally:
                kernel32.CloseHandle(handle)
        return f"pid-{pid}"


def _window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _class_name(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buffer, len(buffer))
    return buffer.value


def _rect(hwnd: int) -> Tuple[int, int, int, int]:
    value = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(value)):
        return (0, 0, 0, 0)
    return (value.left, value.top, value.right - value.left, value.bottom - value.top)


def _pid(hwnd: int) -> int:
    value = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(value))
    return int(value.value)


def _visible_windows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @callback_type
    def callback(hwnd: int, _: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True
        x, y, width, height = _rect(hwnd)
        if width < 80 or height < 50:
            return True
        pid = _pid(hwnd)
        rows.append({
            "app_name": _process_name(pid),
            "pid": pid,
            "window_id": int(hwnd),
            "title": _window_text(hwnd),
            "class_name": _class_name(hwnd),
            "bounds": {"x": x, "y": y, "width": width, "height": height},
            "off_screen": False,
            "z_index": 10_000 - len(rows),
        })
        return True

    user32.EnumWindows(callback, 0)
    return rows


def _capture_window_image(hwnd: int, left: int, top: int, width: int, height: int) -> Image.Image:
    """Capture a window even when another application visually covers it."""
    try:
        import win32gui
        import win32ui

        window_dc = win32gui.GetWindowDC(hwnd)
        source_dc = win32ui.CreateDCFromHandle(window_dc)
        memory_dc = source_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(source_dc, width, height)
        memory_dc.SelectObject(bitmap)
        rendered = bool(user32.PrintWindow(hwnd, memory_dc.GetSafeHdc(), 2))
        if rendered:
            bitmap_info = bitmap.GetInfo()
            bitmap_bytes = bitmap.GetBitmapBits(True)
            image = Image.frombuffer(
                "RGB",
                (bitmap_info["bmWidth"], bitmap_info["bmHeight"]),
                bitmap_bytes,
                "raw",
                "BGRX",
                0,
                1,
            ).copy()
        else:
            image = None
        win32gui.DeleteObject(bitmap.GetHandle())
        memory_dc.DeleteDC()
        source_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, window_dc)
        if image is not None and image.getbbox():
            return image
    except Exception:
        pass
    return ImageGrab.grab(
        bbox=(left, top, left + width, top + height),
        all_screens=True,
    ).convert("RGB")


class SzygWindowsComputerBackend(ComputerUseBackend):
    """Bounded Windows backend injected into Hermes without forking upstream."""

    def __init__(self) -> None:
        self._started = False
        self._active_window: Optional[Dict[str, Any]] = None
        self._elements: Dict[int, UIElement] = {}
        self._lock = threading.RLock()

    def start(self) -> None:
        if sys.platform != "win32":
            raise RuntimeError("Windows desktop control is unavailable on this operating system")
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass
        self._started = True

    def stop(self) -> None:
        self._started = False
        self._active_window = None
        self._elements.clear()

    def is_available(self) -> bool:
        return sys.platform == "win32"

    def _target(
        self,
        app: Optional[str] = None,
        pid: Optional[int] = None,
        window_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        windows = _visible_windows()
        if window_id:
            return next((row for row in windows if row["window_id"] == int(window_id)), None)
        if pid:
            return next((row for row in windows if row["pid"] == int(pid)), None)
        if app:
            needle = app.casefold().strip()
            return next((
                row for row in windows
                if needle in row["app_name"].casefold() or needle in row["title"].casefold()
            ), None)
        blocked = {"shellexperiencehost.exe", "searchhost.exe", "textinputhost.exe"}
        return next((row for row in windows if row["app_name"].casefold() not in blocked), windows[0] if windows else None)

    def _child_elements(self, target: Dict[str, Any]) -> List[UIElement]:
        elements: List[UIElement] = []
        parent_x = int(target["bounds"]["x"])
        parent_y = int(target["bounds"]["y"])
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @callback_type
        def callback(hwnd: int, _: int) -> bool:
            if len(elements) >= 120 or not user32.IsWindowVisible(hwnd):
                return len(elements) < 120
            x, y, width, height = _rect(hwnd)
            if width < 4 or height < 4:
                return True
            label = _window_text(hwnd) or _class_name(hwnd)
            index = len(elements) + 1
            elements.append(UIElement(
                index=index,
                role=_class_name(hwnd) or "Control",
                label=label[:180],
                bounds=(x - parent_x, y - parent_y, width, height),
                app=str(target["app_name"]),
                pid=int(target["pid"]),
                window_id=int(target["window_id"]),
                attributes={"hwnd": int(hwnd)},
            ))
            return True

        user32.EnumChildWindows(int(target["window_id"]), callback, 0)
        return elements

    def capture(
        self,
        mode: str = "som",
        app: Optional[str] = None,
        pid: Optional[int] = None,
        window_id: Optional[int] = None,
    ) -> CaptureResult:
        with self._lock:
            target = self._target(app=app, pid=pid, window_id=window_id)
            if target is None:
                return CaptureResult(mode=mode, width=0, height=0, window_title="未找到可见窗口")
            self._active_window = target
            bounds = target["bounds"]
            left, top = int(bounds["x"]), int(bounds["y"])
            width, height = int(bounds["width"]), int(bounds["height"])
            image = _capture_window_image(int(target["window_id"]), left, top, width, height)
            elements = [] if mode == "vision" else self._child_elements(target)
            self._elements = {item.index: item for item in elements}
            if mode == "som" and elements:
                draw = ImageDraw.Draw(image)
                for item in elements:
                    x, y, item_width, item_height = item.bounds
                    if item_width < 10 or item_height < 10:
                        continue
                    draw.rectangle((x, y, x + min(item_width, 28), y + 18), fill=(20, 184, 166))
                    draw.text((x + 3, y + 2), str(item.index), fill="white")
            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            raw = buffer.getvalue()
            return CaptureResult(
                mode=mode,
                width=image.width,
                height=image.height,
                png_b64=base64.b64encode(raw).decode("ascii"),
                elements=elements,
                app=str(target["app_name"]),
                window_title=str(target["title"]),
                png_bytes_len=len(raw),
                image_mime_type="image/png",
            )

    def _screen_point(self, element: Optional[int], x: Optional[int], y: Optional[int]) -> Tuple[int, int]:
        if element is not None:
            item = self._elements.get(int(element))
            if item is None:
                raise ValueError("元素已变化，请重新观察窗口")
            local_x, local_y = item.center()
        elif x is not None and y is not None:
            local_x, local_y = int(x), int(y)
        else:
            raise ValueError("请指定元素或坐标")
        if not self._active_window:
            return local_x, local_y
        bounds = self._active_window["bounds"]
        return int(bounds["x"]) + local_x, int(bounds["y"]) + local_y

    @staticmethod
    def _mouse(flags: int, data: int = 0) -> None:
        user32.mouse_event(flags, 0, 0, data, 0)

    def click(
        self,
        *,
        element: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = "left",
        click_count: int = 1,
        modifiers: Optional[List[str]] = None,
        delivery_mode: Optional[str] = None,
        bring_to_front: bool = False,
    ) -> ActionResult:
        screen_x, screen_y = self._screen_point(element, x, y)
        if bring_to_front and self._active_window:
            self.focus_app(str(self._active_window["app_name"]), raise_window=True)
        user32.SetCursorPos(screen_x, screen_y)
        down, up = {
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
        }.get(button, (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP))
        for _ in range(max(1, min(int(click_count), 3))):
            self._mouse(down)
            self._mouse(up)
        return ActionResult(ok=True, action="click", path="win32_foreground", delivery_mode="foreground")

    def drag(
        self,
        *,
        from_element: Optional[int] = None,
        to_element: Optional[int] = None,
        from_xy: Optional[Tuple[int, int]] = None,
        to_xy: Optional[Tuple[int, int]] = None,
        button: str = "left",
        modifiers: Optional[List[str]] = None,
        delivery_mode: Optional[str] = None,
        bring_to_front: bool = False,
    ) -> ActionResult:
        start = self._screen_point(from_element, *(from_xy or (None, None)))
        end = self._screen_point(to_element, *(to_xy or (None, None)))
        user32.SetCursorPos(*start)
        self._mouse(MOUSEEVENTF_LEFTDOWN)
        user32.SetCursorPos(*end)
        self._mouse(MOUSEEVENTF_LEFTUP)
        return ActionResult(ok=True, action="drag", path="win32_foreground", delivery_mode="foreground")

    def scroll(
        self,
        *,
        direction: str,
        amount: int = 3,
        element: Optional[int] = None,
        x: Optional[int] = None,
        y: Optional[int] = None,
        modifiers: Optional[List[str]] = None,
        delivery_mode: Optional[str] = None,
        bring_to_front: bool = False,
    ) -> ActionResult:
        if element is not None or (x is not None and y is not None):
            user32.SetCursorPos(*self._screen_point(element, x, y))
        horizontal = direction in {"left", "right"}
        sign = -1 if direction in {"down", "left"} else 1
        self._mouse(MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL, sign * max(1, amount) * 120)
        return ActionResult(ok=True, action="scroll", path="win32_foreground", delivery_mode="foreground")

    @staticmethod
    def _send_unicode(text: str) -> None:
        for char in text:
            unit = ord(char)
            down = INPUT(type=1, union=INPUTUNION(ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE, 0, None)))
            up = INPUT(type=1, union=INPUTUNION(ki=KEYBDINPUT(0, unit, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, None)))
            user32.SendInput(1, ctypes.byref(down), ctypes.sizeof(INPUT))
            user32.SendInput(1, ctypes.byref(up), ctypes.sizeof(INPUT))

    def type_text(self, text: str, *, delivery_mode: Optional[str] = None, bring_to_front: bool = False) -> ActionResult:
        if bring_to_front and self._active_window:
            self.focus_app(str(self._active_window["app_name"]), raise_window=True)
        self._send_unicode(str(text))
        return ActionResult(ok=True, action="type", path="win32_sendinput", delivery_mode="foreground")

    def key(self, keys: str, *, delivery_mode: Optional[str] = None, bring_to_front: bool = False) -> ActionResult:
        aliases = {
            "ctrl": 0x11, "control": 0x11, "alt": 0x12, "shift": 0x10,
            "win": 0x5B, "cmd": 0x5B, "enter": 0x0D, "return": 0x0D,
            "escape": 0x1B, "esc": 0x1B, "tab": 0x09, "space": 0x20,
            "backspace": 0x08, "delete": 0x2E, "up": 0x26, "down": 0x28,
            "left": 0x25, "right": 0x27, "home": 0x24, "end": 0x23,
        }
        virtual_keys: List[int] = []
        for part in str(keys).lower().replace("+", " ").split():
            virtual_keys.append(aliases.get(part, ord(part.upper()) if len(part) == 1 else 0))
        virtual_keys = [item for item in virtual_keys if item]
        for key in virtual_keys:
            user32.keybd_event(key, 0, 0, 0)
        for key in reversed(virtual_keys):
            user32.keybd_event(key, 0, KEYEVENTF_KEYUP, 0)
        return ActionResult(ok=bool(virtual_keys), action="key", path="win32_sendinput", delivery_mode="foreground")

    def list_windows(self) -> List[Dict[str, Any]]:
        return _visible_windows()

    def list_apps(self) -> List[Dict[str, Any]]:
        grouped: Dict[int, Dict[str, Any]] = {}
        for row in _visible_windows():
            item = grouped.setdefault(row["pid"], {
                "name": row["app_name"], "pid": row["pid"], "running": True, "windows": [],
            })
            item["windows"].append({"window_id": row["window_id"], "title": row["title"]})
        return list(grouped.values())

    def focus_app(self, app: str, raise_window: bool = False) -> ActionResult:
        target = self._target(app=app)
        if target is None:
            return ActionResult(ok=False, action="focus_app", message="未找到对应窗口")
        hwnd = int(target["window_id"])
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, SW_RESTORE)
        ok = bool(user32.SetForegroundWindow(hwnd)) if raise_window else True
        self._active_window = target
        return ActionResult(ok=ok, action="focus_app", path="win32_foreground")

    def set_value(self, value: str, element: Optional[int] = None) -> ActionResult:
        if element is not None:
            self.click(element=element)
        return self.type_text(value)


_installed = False
_instances: Dict[str, SzygWindowsComputerBackend] = {}


_DESKTOP_APP_ALIASES = {
    "notepad": "notepad",
    "notepad.exe": "notepad",
    "记事本": "notepad",
    "calculator": "calculator",
    "calculatorapp": "calculator",
    "calc": "calculator",
    "calc.exe": "calculator",
    "计算器": "calculator",
}

_PREVIEW_FEEDBACK_PROCESSES = {
    "chatgpt.exe",
    "szyg.exe",
    "领鹿员工.exe",
}
_PREVIEW_FEEDBACK_TITLES = (
    "领鹿员工 - 超级数字员工",
    "员工工作视窗",
    "工作现场",
)


def _desktop_app_name(value: str) -> str:
    return _DESKTOP_APP_ALIASES.get(str(value or "").strip().casefold(), "")


def _is_preview_feedback_target(target: Dict[str, Any]) -> bool:
    process_name = str(target.get("app_name") or "").strip().casefold()
    title = str(target.get("title") or "").strip().casefold()
    return process_name in _PREVIEW_FEEDBACK_PROCESSES or any(
        marker.casefold() in title for marker in _PREVIEW_FEEDBACK_TITLES
    )


def is_feedback_preview_summary(summary: str) -> bool:
    value = str(summary or "").casefold()
    return any(name.casefold() in value for name in _PREVIEW_FEEDBACK_PROCESSES) or any(
        marker.casefold() in value for marker in _PREVIEW_FEEDBACK_TITLES
    )


def _foreground_target() -> Optional[Dict[str, Any]]:
    hwnd = int(user32.GetForegroundWindow() or 0)
    if not hwnd:
        return None
    return next((item for item in _visible_windows() if int(item["window_id"]) == hwnd), None)


def _backend_for_session(session_id: str) -> SzygWindowsComputerBackend:
    from tools.computer_use import tool as upstream_tool

    backend = upstream_tool._get_backend(str(session_id or ""))
    if not isinstance(backend, SzygWindowsComputerBackend):
        raise RuntimeError("当前电脑操作能力暂时不可用")
    return backend


def open_desktop_app(app: str, session_id: str = "") -> Dict[str, Any]:
    """Open a supported Windows app and prime the session's visible frame."""
    canonical = _desktop_app_name(app)
    if not canonical:
        return {"ok": False, "error": "暂不支持打开这个应用"}

    if canonical == "notepad":
        subprocess.Popen(
            ["notepad.exe"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        target_hint = "notepad"
        display_name = "记事本"
    else:
        os.startfile("calculator:")
        target_hint = "计算器"
        display_name = "计算器"

    backend = _backend_for_session(session_id)
    target: Optional[Dict[str, Any]] = None
    for _ in range(20):
        target = backend._target(app=target_hint)
        if target is not None:
            break
        time.sleep(0.2)
    if target is None:
        return {"ok": False, "error": f"{display_name}已启动，但暂时没有找到它的窗口"}

    hwnd = int(target["window_id"])
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)
    backend._active_window = target
    capture = backend.capture(mode="vision", window_id=hwnd)
    return {
        "ok": True,
        "app": canonical,
        "display_name": display_name,
        "window_title": capture.window_title or str(target.get("title") or ""),
        "message": f"已打开{display_name}",
    }


def latest_computer_frame(session_id: str, stream: bool = False) -> Optional[Dict[str, Any]]:
    backend = _instances.get(str(session_id or ""))
    if backend is None:
        return None
    active = backend._active_window
    foreground = _foreground_target()
    if foreground is not None and not _is_preview_feedback_target(foreground):
        active = foreground
        backend._active_window = foreground
    if active is not None and _is_preview_feedback_target(active):
        return {
            "blocked": True,
            "content": "为避免画面重复，当前应用不提供实时预览",
        }
    if active is None:
        active = next((item for item in _visible_windows() if not _is_preview_feedback_target(item)), None)
    if active is None:
        return {
            "blocked": True,
            "content": "当前没有可安全预览的应用窗口",
        }
    capture = backend.capture(
        mode="vision",
        window_id=int(active["window_id"]),
    )
    if not capture.png_b64:
        return None
    image_url = f"data:{capture.image_mime_type or 'image/png'};base64,{capture.png_b64}"
    if stream:
        source = Image.open(io.BytesIO(base64.b64decode(capture.png_b64))).convert("RGB")
        source.thumbnail((1280, 800), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        source.save(output, format="JPEG", quality=72, optimize=True)
        image_url = "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode("ascii")
    return {
        "image_url": image_url,
        "content": f"{capture.app} · {capture.window_title}".strip(" ·"),
        "app_name": capture.app or str(active.get("app_name") or ""),
        "window_title": capture.window_title or str(active.get("title") or ""),
        "source_width": capture.width,
        "source_height": capture.height,
    }


def install_windows_computer_backend() -> bool:
    """Inject the Windows backend into upstream Hermes' session cache seam."""
    global _installed
    if _installed or sys.platform != "win32":
        return _installed
    from tools.computer_use import tool as upstream_tool

    original = upstream_tool._get_backend

    def get_backend(session_id: str = "") -> ComputerUseBackend:
        sid = str(session_id or "")
        with upstream_tool._backend_lock:
            cached = upstream_tool._backends.get(sid)
            if isinstance(cached, SzygWindowsComputerBackend):
                return cached
            if cached is not None:
                try:
                    cached.stop()
                except Exception:
                    pass
            backend = SzygWindowsComputerBackend()
            backend.start()
            _instances[sid] = backend
            upstream_tool._backends[sid] = backend
            upstream_tool._backend_call_locks[sid] = threading.RLock()
            upstream_tool._backend_permission_modes[sid] = "standard"
            if sid == "":
                upstream_tool._backend = backend
            return backend

    get_backend.__wrapped__ = original  # type: ignore[attr-defined]
    upstream_tool._get_backend = get_backend
    _installed = True
    return True
