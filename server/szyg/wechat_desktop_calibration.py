"""Local calibration store for WeChat desktop automation."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from szyg.data_path import DATA_DIR
from szyg.integrations.weixin4_bridge import get_weixin4_bridge

CALIBRATION_FILE = DATA_DIR / "wechat_desktop_calibration.json"
_lock = threading.RLock()


def now_iso() -> str:
    return datetime.now().isoformat()


def read_calibration() -> dict:
    with _lock:
        if not CALIBRATION_FILE.exists():
            return {}
        try:
            data = json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}


def write_calibration(data: dict) -> dict:
    CALIBRATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with _lock:
        tmp = CALIBRATION_FILE.with_suffix(CALIBRATION_FILE.suffix + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, CALIBRATION_FILE)
    return data


def get_cursor_position() -> dict[str, int]:
    try:
        import win32api

        x, y = win32api.GetCursorPos()
        return {"x": int(x), "y": int(y)}
    except Exception:
        point = ctypes.wintypes.POINT()  # type: ignore[attr-defined]
        if ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):  # type: ignore[attr-defined]
            return {"x": int(point.x), "y": int(point.y)}
        raise RuntimeError("无法读取当前鼠标位置")


def get_dpi_scale(window_handle: int = 0) -> float:
    try:
        if window_handle:
            dpi = ctypes.windll.user32.GetDpiForWindow(int(window_handle))  # type: ignore[attr-defined]
            if dpi:
                return round(float(dpi) / 96.0, 3)
    except Exception:
        pass
    return 1.0


def _window_rect_bounds(rect: dict) -> tuple[int, int, int, int, int, int]:
    left = int(rect.get("left") or 0)
    top = int(rect.get("top") or 0)
    right = int(rect.get("right") or 0)
    bottom = int(rect.get("bottom") or 0)
    width = int(rect.get("width") or (right - left))
    height = int(rect.get("height") or (bottom - top))
    return left, top, right, bottom, width, height


def _point_in_rect(point: dict[str, int], rect: dict) -> bool:
    left, top, right, bottom, width, height = _window_rect_bounds(rect)
    if width <= 0 or height <= 0:
        return False
    x = int(point.get("x", 0))
    y = int(point.get("y", 0))
    return left <= x <= right and top <= y <= bottom


def _hint_position(rect: dict, hint_width: int, hint_height: int) -> tuple[int, int]:
    left, top, _right, _bottom, width, height = _window_rect_bounds(rect)
    x = left + int(width * 0.62)
    y = top + int(height * 0.70)
    max_x = left + max(0, width - hint_width - 12)
    max_y = top + max(0, height - hint_height - 12)
    return max(left + 12, min(x, max_x)), max(top + 12, min(y, max_y))


def show_calibration_hint(
    window_rect: dict,
    text: str = "请点击微信聊天输入框",
    duration_seconds: int = 12,
) -> None:
    left, top, _right, _bottom, width, height = _window_rect_bounds(window_rect)
    if width <= 0 or height <= 0:
        return

    def run_hint() -> None:
        try:
            import tkinter as tk

            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.configure(bg="#0F172A")
            try:
                root.attributes("-toolwindow", True)
            except Exception:
                pass

            label = tk.Label(
                root,
                text=text,
                bg="#0F172A",
                fg="#F8FAFC",
                font=("Microsoft YaHei UI", 11, "bold"),
                padx=16,
                pady=10,
            )
            label.pack()
            root.update_idletasks()
            hint_width = max(220, root.winfo_width())
            hint_height = max(46, root.winfo_height())
            x, y = _hint_position(window_rect, hint_width, hint_height)
            root.geometry(f"{hint_width}x{hint_height}+{x}+{y}")
            root.after(max(1, int(duration_seconds)) * 1000, root.destroy)
            root.mainloop()
        except Exception:
            return

    threading.Thread(target=run_hint, daemon=True).start()


def capture_next_left_click(timeout_seconds: int = 15) -> dict[str, int]:
    try:
        import win32api
        import win32con
    except Exception as exc:
        raise RuntimeError("当前环境无法监听鼠标点击，请确认 pywin32 可用") from exc

    deadline = time.time() + max(1, int(timeout_seconds))
    was_down = bool(win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000)
    while time.time() < deadline:
        is_down = bool(win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000)
        if is_down and not was_down:
            point = get_cursor_position()
            while time.time() < deadline and (win32api.GetAsyncKeyState(win32con.VK_LBUTTON) & 0x8000):
                time.sleep(0.03)
            return point
        was_down = is_down
        time.sleep(0.03)
    raise RuntimeError("未检测到点击，请重试")


def capture_input_click(timeout_seconds: int = 15) -> dict:
    bridge = get_weixin4_bridge()
    opened = bridge.open_or_focus(wait_seconds=12)
    if not opened.get("ok"):
        raise RuntimeError(opened.get("message") or "未能打开微信")

    window = opened.get("window") or bridge.status()
    rect = window.get("rect") if isinstance(window, dict) else {}
    if not isinstance(rect, dict):
        rect = {}
    _left, _top, _right, _bottom, width, height = _window_rect_bounds(rect)
    if width <= 0 or height <= 0:
        raise RuntimeError("微信窗口尺寸不可用，无法识别输入区")

    show_calibration_hint(rect, "请点击微信聊天输入框", duration_seconds=min(max(1, timeout_seconds), 20))
    time.sleep(0.2)
    try:
        bridge.open_or_focus(wait_seconds=1)
    except Exception:
        pass

    point = capture_next_left_click(timeout_seconds=timeout_seconds)
    if not _point_in_rect(point, rect):
        raise RuntimeError("未点击微信窗口，请点击微信聊天输入框后重试")

    calibration = create_input_calibration(point=point, label="input_box")
    validation = validate_calibration()
    return {
        "calibration": calibration,
        "validation": validation,
        "click": point,
        "window": window,
    }


def create_input_calibration(point: dict[str, int] | None = None, label: str = "input_box") -> dict:
    bridge = get_weixin4_bridge()
    window = bridge.status()
    if not window.get("found"):
        raise RuntimeError(window.get("message") or "未找到微信窗口")

    rect = window.get("rect") or {}
    width = int(rect.get("width") or 0)
    height = int(rect.get("height") or 0)
    if width <= 0 or height <= 0:
        raise RuntimeError("微信窗口尺寸不可用，无法校准")

    point = point or get_cursor_position()
    screen_x = int(point.get("x", 0))
    screen_y = int(point.get("y", 0))
    relative_x = screen_x - int(rect.get("left", 0))
    relative_y = screen_y - int(rect.get("top", 0))
    ratio_x = relative_x / width
    ratio_y = relative_y / height

    if not (0 <= ratio_x <= 1 and 0 <= ratio_y <= 1):
        raise RuntimeError("鼠标位置不在微信窗口内，请把鼠标移到微信聊天输入框后再校准")

    existing = read_calibration()
    created_at = existing.get("created_at") or now_iso()
    data = {
        "version": 1,
        "kind": "wechat_desktop_input",
        "label": label,
        "client": window.get("client", ""),
        "window_title": window.get("title", ""),
        "window_class": window.get("class_name", ""),
        "window_handle": window.get("handle", 0),
        "window_width": width,
        "window_height": height,
        "window_rect": rect,
        "dpi_scale": get_dpi_scale(int(window.get("handle") or 0)),
        "screen_point": {"x": screen_x, "y": screen_y},
        "window_point": {"x": int(relative_x), "y": int(relative_y)},
        "ratio": {"x": round(ratio_x, 6), "y": round(ratio_y, 6)},
        "created_at": created_at,
        "updated_at": now_iso(),
    }
    return write_calibration(data)


def validate_calibration(max_size_drift: float = 0.1) -> dict:
    calibration = read_calibration()
    if not calibration:
        return {
            "ok": False,
            "reason": "missing_calibration",
            "message": "尚未校准微信输入区",
            "calibration": {},
        }

    bridge = get_weixin4_bridge()
    window = bridge.status()
    if not window.get("found"):
        return {
            "ok": False,
            "reason": "window_missing",
            "message": window.get("message") or "未找到微信窗口",
            "calibration": calibration,
            "window": window,
        }

    rect = window.get("rect") or {}
    width = int(rect.get("width") or 0)
    height = int(rect.get("height") or 0)
    base_width = int(calibration.get("window_width") or 0)
    base_height = int(calibration.get("window_height") or 0)
    ratio = calibration.get("ratio") or {}

    if width <= 0 or height <= 0 or base_width <= 0 or base_height <= 0:
        return {
            "ok": False,
            "reason": "invalid_window_size",
            "message": "微信窗口尺寸不可用",
            "calibration": calibration,
            "window": window,
        }

    class_match = (calibration.get("window_class") or "") == (window.get("class_name") or "")
    width_drift = abs(width - base_width) / max(base_width, 1)
    height_drift = abs(height - base_height) / max(base_height, 1)
    size_drift = max(width_drift, height_drift)
    ratio_x = float(ratio.get("x", -1))
    ratio_y = float(ratio.get("y", -1))
    target = {
        "x": int(int(rect.get("left", 0)) + width * ratio_x),
        "y": int(int(rect.get("top", 0)) + height * ratio_y),
    }

    ok = bool(class_match and size_drift <= max_size_drift and 0 <= ratio_x <= 1 and 0 <= ratio_y <= 1)
    return {
        "ok": ok,
        "reason": "ok" if ok else "needs_recalibration",
        "message": "校准可用" if ok else "微信窗口变化较大，建议重新校准",
        "target_screen_point": target,
        "size_drift": round(size_drift, 4),
        "class_match": class_match,
        "max_size_drift": max_size_drift,
        "calibration": calibration,
        "window": window,
    }


def calibration_summary() -> dict:
    return {
        "calibration": read_calibration(),
        "validation": validate_calibration(),
    }
