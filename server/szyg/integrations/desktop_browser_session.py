"""Desktop browser session launcher for real-user browser handoff.

This module intentionally launches the user's installed browser instead of a
managed Playwright browser. It is used for platforms that reject automation
browser contexts but can still be handled through desktop-assisted workflows.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from szyg.config.loader import load_config
from szyg.data_path import DATA_DIR


BROWSER_PROFILE_ROOT = DATA_DIR / "browser_profiles"


@dataclass
class DesktopBrowserLaunch:
    ok: bool
    url: str
    browser: str
    executable_path: str
    profile_dir: str
    remote_debugging_port: int
    cdp_url: str
    no_proxy: bool
    message: str
    process_id: int | None = None
    cdp_available: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "url": self.url,
            "browser": self.browser,
            "executable_path": self.executable_path,
            "profile_dir": self.profile_dir,
            "remote_debugging_port": self.remote_debugging_port,
            "cdp_url": self.cdp_url,
            "no_proxy": self.no_proxy,
            "message": self.message,
            "process_id": self.process_id,
            "cdp_available": self.cdp_available,
            "error": self.error,
        }


def _desktop_browser_config() -> dict:
    try:
        platforms = load_config().get("platforms", {}) or {}
        return platforms.get("desktop_browser", {}) or {}
    except Exception:
        return {}


def _profile_config(profile_key: str) -> dict:
    cfg = _desktop_browser_config()
    profiles = cfg.get("profiles") if isinstance(cfg.get("profiles"), dict) else {}
    return profiles.get(profile_key, {}) if isinstance(profiles.get(profile_key), dict) else {}


def _resolve_path(value: str | Path, base: Path = DATA_DIR.parent) -> Path:
    path = Path(str(value))
    if not path.is_absolute():
        path = base / path
    return path


def _edge_candidates() -> list[Path]:
    candidates = []
    for command in ("msedge", "msedge.exe"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))
    candidates.extend([
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ])
    return candidates


def _chrome_candidates() -> list[Path]:
    candidates = []
    for command in ("chrome", "chrome.exe"):
        found = shutil.which(command)
        if found:
            candidates.append(Path(found))
    candidates.extend([
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ])
    return candidates


def _find_browser_executable(browser: str, explicit_path: str = "") -> tuple[str, str]:
    if explicit_path:
        path = _resolve_path(explicit_path)
        if path.exists():
            return browser, str(path)
    browser_key = (browser or "msedge").strip().lower()
    candidates = _edge_candidates() if browser_key in {"edge", "msedge", "microsoft-edge"} else _chrome_candidates()
    for path in candidates:
        if path and path.exists():
            return browser_key, str(path)
    default = shutil.which(browser_key) or shutil.which("msedge") or shutil.which("chrome") or ""
    return browser_key, default


def _is_port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def _cdp_available(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=0.8) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
            return bool(data.get("webSocketDebuggerUrl") or data.get("Browser"))
    except Exception:
        return False


def _wait_for_cdp(port: int, timeout_seconds: float = 2.5) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if _cdp_available(port):
            return True
        time.sleep(0.2)
    return _is_port_open(port)


def _fallback_open_default_browser(url: str) -> None:
    if os.name == "nt":
        os.startfile(url)  # type: ignore[attr-defined]
        return
    import webbrowser

    webbrowser.open(url, new=2, autoraise=True)


class DesktopBrowserSession:
    """Launch and reuse real desktop browser profiles for assisted workflows."""

    def launch(
        self,
        url: str,
        *,
        profile_key: str,
        browser: str = "",
        executable_path: str = "",
        remote_debugging_port: int = 0,
        no_proxy: bool | None = None,
        new_window: bool = True,
    ) -> DesktopBrowserLaunch:
        cfg = _desktop_browser_config()
        profile_cfg = _profile_config(profile_key)
        browser = browser or str(profile_cfg.get("browser") or cfg.get("browser") or "msedge")
        executable_path = executable_path or str(profile_cfg.get("executable_path") or cfg.get("executable_path") or "")
        remote_debugging_port = int(
            remote_debugging_port
            or profile_cfg.get("remote_debugging_port")
            or cfg.get("remote_debugging_port")
            or 9223
        )
        if no_proxy is None:
            no_proxy = bool(profile_cfg.get("no_proxy", cfg.get("no_proxy", True)))
        profile_dir_raw = profile_cfg.get("profile_dir") or cfg.get("profile_root") or BROWSER_PROFILE_ROOT
        profile_dir = _resolve_path(profile_dir_raw)
        if profile_cfg.get("profile_dir") or cfg.get("profile_root"):
            if profile_dir.name != profile_key and not profile_cfg.get("profile_dir"):
                profile_dir = profile_dir / profile_key
        else:
            profile_dir = BROWSER_PROFILE_ROOT / profile_key
        profile_dir.mkdir(parents=True, exist_ok=True)
        browser_name, executable = _find_browser_executable(browser, executable_path)
        cdp_url = f"http://127.0.0.1:{remote_debugging_port}"

        if not executable:
            try:
                _fallback_open_default_browser(url)
                return DesktopBrowserLaunch(
                    ok=True,
                    url=url,
                    browser="system_default",
                    executable_path="",
                    profile_dir=str(profile_dir),
                    remote_debugging_port=0,
                    cdp_url="",
                    no_proxy=bool(no_proxy),
                    message="已用系统默认浏览器打开页面，但未启用桌面浏览器接管端口。",
                    cdp_available=False,
                )
            except Exception as exc:
                return DesktopBrowserLaunch(
                    ok=False,
                    url=url,
                    browser=browser_name,
                    executable_path="",
                    profile_dir=str(profile_dir),
                    remote_debugging_port=remote_debugging_port,
                    cdp_url=cdp_url,
                    no_proxy=bool(no_proxy),
                    message="打开浏览器失败",
                    error=str(exc),
                )

        args = [
            executable,
            f"--user-data-dir={profile_dir}",
            f"--remote-debugging-port={remote_debugging_port}",
            "--disable-features=Translate",
        ]
        if no_proxy:
            args.append("--no-proxy-server")
        if new_window:
            args.append("--new-window")
        args.append(url)

        try:
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            cdp_ready = _wait_for_cdp(remote_debugging_port)
            return DesktopBrowserLaunch(
                ok=True,
                url=url,
                browser=browser_name,
                executable_path=executable,
                profile_dir=str(profile_dir),
                remote_debugging_port=remote_debugging_port,
                cdp_url=cdp_url,
                no_proxy=bool(no_proxy),
                message="已启动真实桌面浏览器",
                process_id=process.pid,
                cdp_available=cdp_ready or _is_port_open(remote_debugging_port),
            )
        except Exception as exc:
            return DesktopBrowserLaunch(
                ok=False,
                url=url,
                browser=browser_name,
                executable_path=executable,
                profile_dir=str(profile_dir),
                remote_debugging_port=remote_debugging_port,
                cdp_url=cdp_url,
                no_proxy=bool(no_proxy),
                message="启动真实桌面浏览器失败",
                error=str(exc),
            )


_session: DesktopBrowserSession | None = None


def get_desktop_browser_session() -> DesktopBrowserSession:
    global _session
    if _session is None:
        _session = DesktopBrowserSession()
    return _session
