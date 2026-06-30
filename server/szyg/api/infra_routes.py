"""
Infrastructure Routes — Browser sandbox lifecycle, node telemetry.

GET  /api/infra/sandbox-status   →  { status: "missing"|"downloading"|"ready", progress: int }
POST /api/infra/sandbox-init     →  trigger playwright install chromium
"""
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/infra", tags=["infra"])


class CredentialLoginRequest(BaseModel):
    platform: str = Field(..., description="Platform key: douyin, xhs, kuaishou, bilibili, weibo")
    account_id: str = Field(default="default", description="Account identifier for profile isolation")
    username: str = Field(..., description="Phone number or account username")
    password: str = Field(..., description="Account password")

# ── In-memory sandbox state ──────────────────────────────
_sandbox_status: str = "missing"  # missing | downloading | ready
_sandbox_progress: int = 0        # 0–100
_sandbox_lock = asyncio.Lock()


def _resolve_chromium_dir() -> Path | None:
    """Resolve Chromium directory — checks bundled path first, then system cache."""
    # 1. Bundled: server/szyg/storage/chromium/ (packaged distribution)
    bundled = Path(__file__).resolve().parent.parent / "storage" / "chromium"
    if bundled.exists():
        for d in bundled.iterdir():
            if d.is_dir() and d.name.startswith("chromium-"):
                chrome_exe = d / "chrome-win" / "chrome.exe"
                chrome_exe64 = d / "chrome-win64" / "chrome.exe"
                chrome_linux = d / "chrome-linux" / "chrome"
                chrome_mac = d / "chrome-mac" / "Chromium.app"
                if chrome_exe.exists() or chrome_exe64.exists() or chrome_linux.exists() or chrome_mac.exists():
                    logger.info(f"Using bundled Chromium: {d}")
                    return d

    # 2. System: %LOCALAPPDATA%/ms-playwright/ (Playwright cache)
    home = Path.home()
    candidates = [
        home / "AppData" / "Local" / "ms-playwright" / "chromium-*",
        home / ".cache" / "ms-playwright" / "chromium-*",
        home / "Library" / "Caches" / "ms-playwright" / "chromium-*",
    ]
    for pattern in candidates:
        try:
            matches = sorted(Path(pattern.parent).glob(pattern.name), reverse=True)
            for m in matches:
                chrome_exe = m / "chrome-win" / "chrome.exe"
                chrome_exe64 = m / "chrome-win64" / "chrome.exe"
                chrome_linux = m / "chrome-linux" / "chrome"
                chrome_mac = m / "chrome-mac" / "Chromium.app"
                if chrome_exe.exists() or chrome_exe64.exists() or chrome_linux.exists() or chrome_mac.exists():
                    logger.info(f"Found system Chromium: {m}")
                    return m
        except Exception:
            continue
    return None


def _find_chromium() -> bool:
    """Check if Playwright-managed Chromium is available."""
    if _resolve_chromium_dir() is not None:
        return True

    # Last-resort: ask playwright CLI
    try:
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "--dry-run", "chromium"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and "already installed" in (result.stdout + result.stderr).lower():
            return True
    except Exception:
        pass

    return False


def get_chromium_executable_path() -> str | None:
    """
    Return the absolute path to the Chromium executable.
    Checks bundled distribution first, then system Playwright cache.
    Returns None if not found.
    """
    d = _resolve_chromium_dir()
    if d is None:
        return None

    # Platform-specific binary name
    if sys.platform == "win32":
        for sub in ["chrome-win64", "chrome-win"]:
            exe = d / sub / "chrome.exe"
            if exe.exists():
                return str(exe)
    elif sys.platform == "darwin":
        app = d / "chrome-mac" / "Chromium.app" / "Contents" / "MacOS" / "Chromium"
        if app.exists():
            return str(app)
    else:
        exe = d / "chrome-linux" / "chrome"
        if exe.exists():
            return str(exe)
    return None


async def _install_chromium():
    """Run playwright install chromium as a subprocess, updating progress."""
    global _sandbox_status, _sandbox_progress

    async with _sandbox_lock:
        if _sandbox_status == "ready":
            return
        if _sandbox_status == "downloading":
            return  # Already in progress
        _sandbox_status = "downloading"
        _sandbox_progress = 0

    try:
        # Run the install in a subprocess
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "playwright", "install", "chromium",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        # Playwright outputs progress lines like "Downloading Chromium 123.0... | 45%"
        # We parse these to update progress
        async for line in proc.stdout:
            decoded = line.decode("utf-8", errors="replace").strip()
            logger.info(f"[sandbox] {decoded}")

            # Try to extract percentage
            for token in decoded.split():
                if token.endswith("%"):
                    try:
                        pct = int(token.replace("%", ""))
                        _sandbox_progress = min(pct, 99)
                    except ValueError:
                        pass

        await proc.wait()

        if proc.returncode == 0:
            _sandbox_status = "ready"
            _sandbox_progress = 100
            logger.info("Sandbox: Chromium installed successfully")
        else:
            _sandbox_status = "missing"
            _sandbox_progress = 0
            logger.error(f"Sandbox: Chromium install failed with code {proc.returncode}")

    except Exception as e:
        _sandbox_status = "missing"
        _sandbox_progress = 0
        logger.error(f"Sandbox: install exception: {e}")


# ── Endpoints ────────────────────────────────────────────

@router.get("/sandbox-status")
async def sandbox_status():
    """Return current sandbox lifecycle state."""
    global _sandbox_status

    # On first call, auto-detect if Chromium is already installed
    if _sandbox_status == "missing" and _find_chromium():
        _sandbox_status = "ready"
        _sandbox_progress = 100

    return {
        "status": _sandbox_status,
        "progress": _sandbox_progress,
    }


@router.post("/sandbox-init")
async def sandbox_init():
    """Trigger Chromium sandbox download + installation."""
    global _sandbox_status

    if _sandbox_status == "ready":
        return {"status": "ready", "message": "Sandbox already initialized"}

    if _sandbox_status == "downloading":
        return {"status": "downloading", "progress": _sandbox_progress, "message": "Download in progress"}

    # Kick off install in background (don't block the response)
    asyncio.create_task(_install_chromium())

    return {"status": "downloading", "progress": 0, "message": "Sandbox initialization started"}


@router.post("/login/credentials")
async def login_credentials(req: CredentialLoginRequest):
    """
    凭证登录 — 使用账号密码在隔离沙箱中自动完成平台登录。

    启动后台 Playwright 任务:
      1. 打开平台登录页
      2. 切换到密码登录模式
      3. 模拟人类输入账号密码
      4. 提交并等待登录成功
      5. 持久化 session 到存储目录

    返回非阻塞响应，前端可通过 sandbox-status 轮询。
    """
    try:
        from szyg.core.browser_pool import get_browser_pool_v2
        pool = get_browser_pool_v2()

        # Kick off credential login in background
        async def _run():
            result = await pool.handle_credential_login(
                platform=req.platform,
                username=req.username,
                password=req.password,
                account_id=req.account_id,
            )
            logger.info(f"Credential login result ({req.platform}/{req.account_id}): {result}")

        asyncio.create_task(_run())

        return {
            "status": "processing",
            "message": "正在拉起隔离沙箱执行凭证登录…",
            "platform": req.platform,
            "account_id": req.account_id,
        }

    except Exception as e:
        logger.error(f"Credential login endpoint error: {e}")
        return {"status": "error", "message": str(e)}
