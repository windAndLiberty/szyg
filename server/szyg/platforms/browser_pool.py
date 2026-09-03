"""
Browser Pool — Shared Playwright browser instance for all platform adapters.

Fixes: Playwright process leak (was launching 1 browser per publish → OOM)
       Now: 1 shared browser, per-platform contexts, auto-cleanup.

Usage:
    pool = get_browser_pool()
    context = await pool.get_context(Platform.DOUYIN)  # reuse or create
    page = await context.new_page()
    ...
    await pool.return_context(Platform.DOUYIN)  # keep alive for reuse
"""
import asyncio
import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────

IDLE_TIMEOUT = 600  # 10 minutes before auto-closing idle context
MAX_CONTEXTS = 8    # Max concurrent contexts across all platforms
CLEANUP_INTERVAL = 300  # Every 5 minutes

class BrowserPool:
    """Singleton shared browser pool. One browser, many contexts.

    Args:
        headless: If True, launch browser in headless mode (no visible window).
                  Used for background search/acquisition tasks.
    """

    def __init__(self, headless: bool = False):
        self._headless = headless
        self._playwright = None
        self._browser = None
        self._contexts: dict[str, dict] = {}  # platform_key → {context, last_used, lock}
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

    async def _ensure_browser(self):
        """Lazy-init the shared browser (once). Auto-restart if crashed."""
        if self._browser and self._browser.is_connected():
            return
        await self._restart_browser()

    async def _restart_browser(self):
        """关闭旧浏览器并重新启动（用于崩溃恢复）"""
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if not self._playwright:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
        from szyg.platforms.anti_detect import get_launch_config_native
        if self._headless and os.name == "nt":
            cfg = {
                "headless": True,
                "channel": "msedge",
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-proxy-server",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            }
        else:
            cfg = get_launch_config_native(headless=self._headless)
        try:
            self._browser = await self._playwright.chromium.launch(**cfg)
        except Exception as exc:
            if not self._headless:
                raise
            logger.warning(
                "BrowserPool: bundled headless Chromium failed (%s), falling back to system Edge",
                exc,
            )
            fallback_cfg = {
                "headless": True,
                "channel": "msedge",
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--no-proxy-server",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            }
            self._browser = await self._playwright.chromium.launch(**fallback_cfg)
        try:
            pid = self._browser._impl_obj._process.pid if hasattr(self._browser, '_impl_obj') and hasattr(self._browser._impl_obj, '_process') else '?'
        except Exception:
            pid = '?'
        logger.info(f"BrowserPool: shared browser started (PID={pid})")

    async def get_context(self, platform_key: str, storage_state: dict | None = None) -> object:
        """Get or create a browser context for a platform. Reuses existing if available."""
        async with self._lock:
            # Detect browser crash and auto-restart
            if self._browser and not self._browser.is_connected():
                logger.warning("BrowserPool: browser disconnected, restarting...")
                self._contexts.clear()
                await self._restart_browser()
            await self._ensure_browser()

            # Return existing context if still alive
            if platform_key in self._contexts:
                entry = self._contexts[platform_key]
                ctx = entry["context"]
                try:
                    # Quick health check — if context is closed, recreate
                    _ = ctx.pages
                    entry["last_used"] = time.time()
                    logger.debug(f"BrowserPool: reuse context for {platform_key}")
                    return ctx
                except Exception:
                    logger.info(f"BrowserPool: context for {platform_key} was closed, recreating")
                    del self._contexts[platform_key]

            # Enforce max contexts — close least recently used
            if len(self._contexts) >= MAX_CONTEXTS:
                oldest_key = min(self._contexts, key=lambda k: self._contexts[k]["last_used"])
                logger.info(f"BrowserPool: evicting idle context: {oldest_key}")
                try:
                    await self._contexts[oldest_key]["context"].close()
                except Exception:
                    pass
                del self._contexts[oldest_key]

            # Create new context (with retry on browser transient failure)
            from szyg.platforms.anti_detect import get_stealth_context_config
            config = get_stealth_context_config()
            if storage_state:
                config["storage_state"] = storage_state

            try:
                ctx = await self._browser.new_context(**config)
            except Exception as e:
                logger.warning(f"BrowserPool: new_context failed ({e}), restarting browser...")
                await self._restart_browser()
                ctx = await self._browser.new_context(**config)

            self._contexts[platform_key] = {
                "context": ctx,
                "last_used": time.time(),
            }
            logger.info(f"BrowserPool: new context for {platform_key} (total: {len(self._contexts)})")
            return ctx

    async def return_context(self, platform_key: str):
        """Mark context as returned (keep alive for reuse)."""
        if platform_key in self._contexts:
            self._contexts[platform_key]["last_used"] = time.time()

    async def invalidate_context(self, platform_key: str):
        """Force-close a platform's context (e.g., after logout)."""
        if platform_key in self._contexts:
            try:
                await self._contexts[platform_key]["context"].close()
            except Exception:
                pass
            del self._contexts[platform_key]
            logger.info(f"BrowserPool: invalidated context for {platform_key}")

    async def _cleanup_loop(self):
        """Periodically close idle contexts."""
        while self._running:
            await asyncio.sleep(CLEANUP_INTERVAL)
            now = time.time()
            async with self._lock:
                to_remove = []
                for key, entry in self._contexts.items():
                    if now - entry["last_used"] > IDLE_TIMEOUT:
                        to_remove.append(key)
                for key in to_remove:
                    try:
                        await self._contexts[key]["context"].close()
                    except Exception:
                        pass
                    del self._contexts[key]
                    logger.info(f"BrowserPool: auto-closed idle context: {key}")
                if to_remove:
                    logger.info(f"BrowserPool: cleaned {len(to_remove)} idle contexts, {len(self._contexts)} remaining")

    async def start(self):
        """Start the cleanup loop."""
        if not self._running:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("BrowserPool: cleanup loop started")

    async def stop(self):
        """Close all contexts and the shared browser."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        async with self._lock:
            for key, entry in list(self._contexts.items()):
                try:
                    await entry["context"].close()
                except Exception:
                    pass
            self._contexts.clear()

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
        logger.info("BrowserPool: stopped")

    @property
    def context_count(self) -> int:
        return len(self._contexts)

    @property
    def is_healthy(self) -> bool:
        return self._browser is not None and self._browser.is_connected()

    def __repr__(self) -> str:
        return f"<BrowserPool contexts={len(self._contexts)} healthy={self.is_healthy}>"


# ── Singleton ──────────────────────────────────────────

_pools: dict[bool, BrowserPool] = {}

def get_browser_pool(headless: bool = False) -> BrowserPool:
    """Get the shared browser pool.

    Args:
        headless: If True, returns a separate headless pool (no visible window).
                  If False, returns the standard headed pool for login/publish.
    """
    if headless not in _pools:
        _pools[headless] = BrowserPool(headless=headless)
    return _pools[headless]
